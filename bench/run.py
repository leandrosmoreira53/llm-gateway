"""Run benchmark targets over the frozen context and record raw answers (GW-2.1).

    uv run python -m bench.run --subset tune --mode hibrida --run-name v0-tune --dry-run
    uv run python -m bench.run --subset tune --mode hibrida --run-name v0-tune --max-cost 8

- Answers go to bench/data/runs/<run-name>/<target>.jsonl (git-ignored: they quote private manuals).
- Resumable: questions already answered without error are skipped; failed ones are retried.
- Cost cap: real `usage.cost` is summed over the whole run directory and checked before every call.
  In-flight calls can overshoot by at most `concurrency` answers.
- `--dry-run` prints the estimate and spends nothing.
"""

import argparse
import asyncio
import datetime as dt
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from bench.catalog import Price, fetch_catalog, prices
from bench.context import MODES, Context
from bench.dataset import Question, load_dataset
from bench.prompt import PROMPT_VERSION, build_messages
from bench.split import load_split
from gateway.config import Settings
from gateway.providers import ChatRequest, OpenRouterProvider, Provider, ResolvedRoute
from gateway.providers.errors import ProviderError, ProviderRateLimitError

TARGETS_PATH = Path(__file__).parent / "config" / "targets.json"
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_SNAPSHOT = DATA_DIR / "retrieval" / "snapshot-staging-2026-10-10.json"
DEFAULT_SESSION = DATA_DIR / "session" / "numeros-bristol.txt"
SPLIT_PATH = Path(__file__).parent / "datasets" / "split.json"

MAX_TOKENS = 8000  # bounds a runaway answer (reasoning included for most providers)
MAX_ATTEMPTS = 3
CHARS_PER_TOKEN = 3.5  # rough, for estimates only
ESTIMATE_OUTPUT_TOKENS = 600
REASONING_FACTOR = 4  # pessimistic multiplier on output for reasoning models
ROUTER_PRICE_PROXY = (
    "anthropic/claude-sonnet-5.5"  # routers publish no price; assume a strong model
)


class CostCapReachedError(Exception):
    pass


def load_targets(path: Path = TARGETS_PATH) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [m["slug"] for m in data["models"]]


def target_file(run_dir: Path, slug: str) -> Path:
    return run_dir / (slug.replace("/", "__") + ".jsonl")


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def spent_usd(run_dir: Path) -> Decimal:
    total = Decimal(0)
    for path in run_dir.glob("*.jsonl"):
        for record in read_records(path):
            if record.get("cost_usd") is not None:
                total += Decimal(str(record["cost_usd"]))
    return total


@dataclass(frozen=True)
class Estimate:
    target: str
    questions: int
    input_tokens: int
    low_usd: float | None
    high_usd: float | None
    note: str


def estimate(
    questions: Sequence[Question],
    context: Context,
    mode: str,
    targets: Sequence[str],
    price_table: dict[str, Price],
) -> list[Estimate]:
    input_tokens = sum(
        int(
            sum(
                len(m["content"])
                for m in build_messages(q, context.passages(q.id, mode), context.session_for(q))
            )
            / CHARS_PER_TOKEN
        )
        for q in questions
    )
    out: list[Estimate] = []
    for target in targets:
        price = price_table.get(target)
        note = ""
        if price is not None and not price.known:
            price, note = (
                price_table.get(ROUTER_PRICE_PROXY),
                f"router: priced as {ROUTER_PRICE_PROXY}",
            )
        if price is None:
            out.append(Estimate(target, len(questions), input_tokens, None, None, "not in catalog"))
            continue
        out_tokens = ESTIMATE_OUTPUT_TOKENS * len(questions)
        low = input_tokens * price.prompt_per_token + out_tokens * price.completion_per_token
        factor = REASONING_FACTOR if price.reasoning else 1
        high = (
            input_tokens * price.prompt_per_token + out_tokens * factor * price.completion_per_token
        )
        out.append(Estimate(target, len(questions), input_tokens, low, high, note))
    return out


def reasoning_tokens(raw: dict[str, Any]) -> int | None:
    details = (raw.get("usage") or {}).get("completion_tokens_details") or {}
    value = details.get("reasoning_tokens")
    return int(value) if isinstance(value, int) else None


async def answer_one(
    provider: Provider, target: str, question: Question, messages: list[dict[str, Any]]
) -> dict[str, Any]:
    request = ChatRequest.model_validate({"messages": messages, "max_tokens": MAX_TOKENS})
    record: dict[str, Any] = {"id": question.id, "target": target}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = await provider.chat(request, ResolvedRoute(model=target))
        except ProviderError as exc:
            if exc.retryable and attempt < MAX_ATTEMPTS:
                wait = (
                    exc.retry_after_seconds
                    if isinstance(exc, ProviderRateLimitError) and exc.retry_after_seconds
                    else 2**attempt
                )
                await asyncio.sleep(wait)
                continue
            record.update(error=f"{type(exc).__name__}: {exc}", attempts=attempt)
            return record
        record.update(
            model_used=result.model_used,
            provider=result.provider,
            content=result.content,
            finish_reason=result.finish_reason,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            reasoning_tokens=reasoning_tokens(result.raw),
            cost_usd=float(result.usage.cost_usd) if result.usage.cost_usd is not None else None,
            latency_ms=round(result.latency_ms, 1),
            attempts=attempt,
            error=None,
        )
        return record
    raise AssertionError("unreachable")


async def run(
    *,
    provider: Provider,
    questions: Sequence[Question],
    context: Context,
    mode: str,
    targets: Sequence[str],
    run_dir: Path,
    max_cost_usd: Decimal,
    subset: str,
    concurrency: int = 4,
) -> dict[str, int]:
    """Answer every (target, question) not yet answered. Returns counts per outcome."""
    # Small local files on a CLI run; blocking I/O here is fine.
    run_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(concurrency)
    counts = {"answered": 0, "errors": 0, "skipped": 0}
    spent = spent_usd(run_dir)

    jobs: list[tuple[str, Question]] = []
    for target in targets:
        done = {r["id"] for r in read_records(target_file(run_dir, target)) if not r.get("error")}
        for q in questions:
            if q.id in done:
                counts["skipped"] += 1
            else:
                jobs.append((target, q))

    async def worker(target: str, question: Question) -> None:
        nonlocal spent
        async with semaphore:
            if spent >= max_cost_usd:
                raise CostCapReachedError(
                    f"cost cap US$ {max_cost_usd} reached (spent US$ {spent:.4f})"
                )
            messages = build_messages(
                question, context.passages(question.id, mode), context.session_for(question)
            )
            record = await answer_one(provider, target, question, messages)
            record.update(
                subset=subset,
                mode=mode,
                prompt_version=PROMPT_VERSION,
                created_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            )
            async with lock:
                with target_file(run_dir, target).open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                if record.get("cost_usd"):
                    spent += Decimal(str(record["cost_usd"]))
                counts["errors" if record.get("error") else "answered"] += 1
                print(
                    f"{target} {question.id} "
                    + (
                        f"ERROR {record['error']}"
                        if record.get("error")
                        else f"${record.get('cost_usd')}"
                    )
                    + f" | total ${spent:.4f}",
                    file=sys.stderr,
                )

    results = await asyncio.gather(*(worker(t, q) for t, q in jobs), return_exceptions=True)
    capped = [r for r in results if isinstance(r, CostCapReachedError)]
    unexpected = [
        r
        for r in results
        if isinstance(r, BaseException) and not isinstance(r, CostCapReachedError)
    ]
    if unexpected:
        raise unexpected[0]
    if capped:
        print(str(capped[0]), file=sys.stderr)
        counts["stopped_by_cap"] = len(capped)
    return counts


def select_questions(dataset: Path, subset: str) -> list[Question]:
    questions = load_dataset(dataset)
    if subset == "all":
        return questions
    split = load_split(SPLIT_PATH, dataset_path=dataset)
    ids = set(split.tune if subset == "tune" else split.test)
    return [q for q in questions if q.id in ids]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run benchmark targets on the frozen context.")
    parser.add_argument("--subset", choices=["tune", "test", "all"], required=True)
    parser.add_argument("--mode", choices=MODES, default="hibrida")
    parser.add_argument("--run-name", required=True)
    parser.add_argument(
        "--models", help="comma-separated slugs (default: bench/config/targets.json)"
    )
    parser.add_argument("--max-cost", type=Decimal, default=Decimal("8"))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--session", type=Path, default=DEFAULT_SESSION)
    parser.add_argument("--ids", help="comma-separated question IDs within the subset (smoke test)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings()
    if settings.bench_dataset_path is None:
        parser.error("BENCH_DATASET_PATH is not set")
    questions = select_questions(settings.bench_dataset_path, args.subset)
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q.id in wanted]
        if {q.id for q in questions} != wanted:
            parser.error("some --ids are not in the chosen subset")
    context = Context.load(args.snapshot, args.session)
    targets = args.models.split(",") if args.models else load_targets()
    run_dir = DATA_DIR / "runs" / args.run_name

    table = prices(fetch_catalog(run_dir / "catalog.json"))
    rows = estimate(questions, context, args.mode, targets, table)
    low = sum(r.low_usd or 0 for r in rows)
    high = sum(r.high_usd or 0 for r in rows)
    for r in rows:
        cost = f"${r.low_usd:.3f}-{r.high_usd:.3f}" if r.low_usd is not None else "?"
        print(f"{r.target:<40} {r.questions:>3}q  ~{r.input_tokens:>7} in-tok  {cost:<16} {r.note}")
    print(
        f"TOTAL estimate: ${low:.2f}-{high:.2f} | cap ${args.max_cost} "
        f"| spent so far ${spent_usd(run_dir):.4f}"
    )
    if args.dry_run:
        return 0

    async def go() -> dict[str, int]:
        async with OpenRouterProvider(settings) as provider:
            return await run(
                provider=provider,
                questions=questions,
                context=context,
                mode=args.mode,
                targets=targets,
                run_dir=run_dir,
                max_cost_usd=args.max_cost,
                subset=args.subset,
                concurrency=args.concurrency,
            )

    counts = asyncio.run(go())
    print(f"done: {counts} | spent ${spent_usd(run_dir):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
