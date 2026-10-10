"""Grade answers: automatic checks + a binary LLM judge against the answer key (GW-2.2, GW-2.3).

    uv run python -m bench.grade --run-name v0-tune --judge <slug> --dry-run
    uv run python -m bench.grade --run-name v0-tune --judge <slug> --max-cost 2

Per answer it records:
- citation_ok: cites at least once and never a source outside its context (automatic)
- gold_cited: cites a page the answer key points to (automatic, informative)
- not_in_sources: says the information is not in the sources (automatic, phrase-based)
- judge_correct / judge_reason: binary judge comparing with the answer key (paid)
- correct = judge_correct and (citation_ok when the question requires a citation)

Grades go to bench/data/runs/<run>/grades/<judge>.jsonl; resumable and capped like bench.run.
"""

import argparse
import asyncio
import json
import re
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from bench.catalog import fetch_catalog, prices
from bench.context import Context
from bench.dataset import Question, load_dataset
from bench.run import CHARS_PER_TOKEN, DATA_DIR, DEFAULT_SESSION, DEFAULT_SNAPSHOT, read_records
from gateway.config import Settings
from gateway.providers import ChatRequest, OpenRouterProvider, Provider, ResolvedRoute
from gateway.providers.errors import ProviderError
from gateway.validators import Source, check_citations, cites_any, says_not_in_sources

JUDGE_PROMPT_VERSION = "judge_v1"  # prompt file; reasoning=low since 2026-10-10
JUDGE_PROMPT = Path(__file__).parent / "prompts" / f"{JUDGE_PROMPT_VERSION}.md"
JUDGE_MAX_TOKENS = 4000
# The judge answers a yes/no question: low reasoning keeps it cheap and stops long reasoning from
# eating the token budget before the JSON verdict. Competitors keep their default reasoning.
JUDGE_REASONING = {"effort": "low"}
MAX_ATTEMPTS = 3


def latest_answers(run_dir: Path) -> list[dict[str, Any]]:
    """Last successful record per (target, question) across the run."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(run_dir.glob("*.jsonl")):
        for record in read_records(path):
            if not record.get("error"):
                out[(record["target"], record["id"])] = record
    return list(out.values())


def automatic_checks(
    record: dict[str, Any], question: Question, context: Context
) -> dict[str, Any]:
    passages = context.passages(question.id, record["mode"])
    provided = [Source(p.document, p.page) for p in passages]
    result = check_citations(
        record.get("content") or "",
        provided,
        session_available=context.session_for(question) is not None,
    )
    gold = [Source(doc, page) for doc, page in question.gold_sources if page is not None]
    return {
        "citations": result.citations,
        "citation_ok": result.ok,
        "unknown_citations": result.unknown,
        "gold_cited": cites_any(result, gold) if gold else None,
        "not_in_sources": says_not_in_sources(record.get("content") or ""),
    }


def judge_messages(question: Question, answer: str) -> list[dict[str, str]]:
    parts = [
        f"PERGUNTA\n{question.question}",
        f"RESPOSTA ESPERADA (gabarito)\n{question.expected_answer}",
    ]
    if question.no_answer:
        parts.append("OBSERVAÇÃO\nO gabarito indica que a informação NÃO está nas fontes.")
    if question.trap:
        parts.append(f"ARMADILHA\n{question.trap}")
    parts.append(f"RESPOSTA DO MODELO\n{answer}")
    return [
        {"role": "system", "content": JUDGE_PROMPT.read_text(encoding="utf-8").strip()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(text: str | None) -> tuple[bool | None, str]:
    match = _JSON_OBJECT.search(text or "")
    if not match:
        return None, "judge returned no JSON"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None, "judge returned invalid JSON"
    correct = data.get("correct")
    if not isinstance(correct, bool):
        return None, "judge JSON without boolean 'correct'"
    return correct, str(data.get("reason") or "")


async def judge_one(
    provider: Provider, judge: str, question: Question, answer: str
) -> dict[str, Any]:
    request = ChatRequest.model_validate(
        {
            "messages": judge_messages(question, answer),
            "max_tokens": JUDGE_MAX_TOKENS,
            "reasoning": JUDGE_REASONING,
        }
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = await provider.chat(request, ResolvedRoute(model=judge))
        except ProviderError as exc:
            if exc.retryable and attempt < MAX_ATTEMPTS:
                await asyncio.sleep(2**attempt)
                continue
            return {
                "judge_correct": None,
                "judge_reason": f"{type(exc).__name__}: {exc}",
                "judge_error": True,
            }
        correct, reason = parse_verdict(result.content)
        if correct is None:
            chars = len(result.content or "")
            reason += f" (finish_reason={result.finish_reason}, content_chars={chars})"
        return {
            "judge_correct": correct,
            "judge_reason": reason,
            "judge_error": correct is None,
            "judge_cost_usd": float(result.usage.cost_usd)
            if result.usage.cost_usd is not None
            else None,
        }
    raise AssertionError("unreachable")


def grades_path(run_dir: Path, judge: str) -> Path:
    return run_dir / "grades" / (judge.replace("/", "__") + ".jsonl")


async def grade(
    *,
    provider: Provider,
    judge: str,
    answers: Sequence[dict[str, Any]],
    questions: dict[str, Question],
    context: Context,
    out_path: Path,
    max_cost_usd: Decimal,
    concurrency: int = 4,
) -> dict[str, int]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["target"], r["id"]) for r in read_records(out_path) if not r.get("judge_error")}
    spent = sum(
        (
            Decimal(str(r["judge_cost_usd"]))
            for r in read_records(out_path)
            if r.get("judge_cost_usd")
        ),
        Decimal(0),
    )
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(concurrency)
    counts = {"graded": 0, "judge_errors": 0, "skipped": 0, "stopped_by_cap": 0}

    async def worker(record: dict[str, Any]) -> None:
        nonlocal spent
        if (record["target"], record["id"]) in done:
            counts["skipped"] += 1
            return
        async with semaphore:
            if spent >= max_cost_usd:
                counts["stopped_by_cap"] += 1
                return
            question = questions[record["id"]]
            row = {"id": record["id"], "target": record["target"], "judge": judge}
            row |= automatic_checks(record, question, context)
            row |= await judge_one(provider, judge, question, record.get("content") or "")
            required = question.citation_required
            row["correct"] = (
                None
                if row["judge_correct"] is None
                else bool(row["judge_correct"] and (row["citation_ok"] or not required))
            )
            row["judge_prompt_version"] = JUDGE_PROMPT_VERSION
            async with lock:
                with out_path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                if row.get("judge_cost_usd"):
                    spent += Decimal(str(row["judge_cost_usd"]))
                counts["judge_errors" if row["judge_error"] else "graded"] += 1
                print(
                    f"{record['target']} {record['id']} correct={row['correct']} | ${spent:.4f}",
                    file=sys.stderr,
                )

    await asyncio.gather(*(worker(r) for r in answers))
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grade benchmark answers.")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--judge", required=True, help="OpenRouter slug of the judge model")
    parser.add_argument("--max-cost", type=Decimal, default=Decimal("2"))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings()
    if settings.bench_dataset_path is None:
        parser.error("BENCH_DATASET_PATH is not set")
    questions = {q.id: q for q in load_dataset(settings.bench_dataset_path)}
    context = Context.load(DEFAULT_SNAPSHOT, DEFAULT_SESSION)
    run_dir = DATA_DIR / "runs" / args.run_name
    answers = latest_answers(run_dir)
    out_path = grades_path(run_dir, args.judge)

    price = prices(fetch_catalog(run_dir / "catalog.json")).get(args.judge)
    in_tokens = (
        sum(
            sum(
                len(m["content"])
                for m in judge_messages(questions[a["id"]], a.get("content") or "")
            )
            for a in answers
        )
        / CHARS_PER_TOKEN
    )
    if price is None or not price.known:
        print(f"{args.judge}: no catalog price; estimate unavailable")
    else:
        low = in_tokens * price.prompt_per_token + 150 * len(answers) * price.completion_per_token
        high = in_tokens * price.prompt_per_token + 1000 * len(answers) * price.completion_per_token
        print(
            f"{len(answers)} answers, ~{int(in_tokens)} input tokens"
            f" -> ${low:.2f}-{high:.2f} (cap ${args.max_cost})"
        )
    if args.dry_run:
        return 0

    print(f"OpenRouter key in use: {settings.key_hint()}")

    async def go() -> dict[str, int]:
        async with OpenRouterProvider(settings) as provider:
            return await grade(
                provider=provider,
                judge=args.judge,
                answers=answers,
                questions=questions,
                context=context,
                out_path=out_path,
                max_cost_usd=args.max_cost,
                concurrency=args.concurrency,
            )

    print(f"done: {asyncio.run(go())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
