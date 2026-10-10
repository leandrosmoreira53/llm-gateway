"""Results table: single targets, simulated ladder and oracle (GW-2.5, GW-2.7).

    uv run python -m bench.report --run-name v0-tune --judge mistralai/mistral-large-4-0

Metrics (docs/BENCHMARK.md):
- accuracy = correct / graded, with a 95% Wilson interval
- cost per question = total usage.cost / answered; cost per correct = total cost / correct
- latency p50/p95 over answered questions
Ladder (simulated on recorded answers, no new calls): try each step in order; move up when the
answer fails the runtime check (no valid citation); cost and latency add up over the steps tried.
Oracle: per question, the cheapest single model that got it right (theoretical bound).
"""

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bench.grade import grades_path, latest_answers
from bench.run import DATA_DIR, read_records

ROUTERS = {"openrouter/auto", "typesafe/jev-router"}


def wilson(correct: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = correct / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def pct(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]


@dataclass
class Row:
    target: str
    answered: int
    graded: int
    correct: int
    cost: float
    latencies: list[float]
    reasoning: list[int]

    @property
    def accuracy(self) -> float:
        return self.correct / self.graded if self.graded else 0.0

    @property
    def cost_per_question(self) -> float:
        return self.cost / self.answered if self.answered else 0.0

    @property
    def cost_per_correct(self) -> float | None:
        return self.cost / self.correct if self.correct else None


def load(
    run_dir: Path, judge: str
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    answers = latest_answers(run_dir)
    grades: dict[tuple[str, str], dict[str, Any]] = {}
    for g in read_records(grades_path(run_dir, judge)):
        grades[(g["target"], g["id"])] = g
    return answers, grades


def single_rows(
    answers: list[dict[str, Any]], grades: dict[tuple[str, str], dict[str, Any]]
) -> list[Row]:
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in answers:
        by_target[a["target"]].append(a)
    rows = []
    for target, items in by_target.items():
        verdicts = [grades.get((target, a["id"]), {}).get("correct") for a in items]
        rows.append(
            Row(
                target=target,
                answered=len(items),
                graded=sum(v is not None for v in verdicts),
                correct=sum(v is True for v in verdicts),
                cost=sum(a.get("cost_usd") or 0.0 for a in items),
                latencies=[a["latency_ms"] for a in items if a.get("latency_ms") is not None],
                reasoning=[a["reasoning_tokens"] for a in items if a.get("reasoning_tokens")],
            )
        )
    return rows


def simulate_ladder(
    steps: list[str],
    answers: list[dict[str, Any]],
    grades: dict[tuple[str, str], dict[str, Any]],
    question_ids: list[str],
) -> Row:
    index = {(a["target"], a["id"]): a for a in answers}
    cost = 0.0
    latencies: list[float] = []
    graded = correct = 0
    for qid in question_ids:
        spent = latency = 0.0
        final: dict[str, Any] | None = None
        for step in steps:
            answer = index.get((step, qid))
            grade = grades.get((step, qid))
            if answer is None or grade is None:
                continue
            spent += answer.get("cost_usd") or 0.0
            latency += answer.get("latency_ms") or 0.0
            final = grade
            if grade.get("citation_ok") or grade.get("not_in_sources"):
                break  # passes the runtime check: stop climbing
        cost += spent
        latencies.append(latency)
        if final is not None and final.get("correct") is not None:
            graded += 1
            correct += bool(final["correct"])
    return Row(
        " → ".join(s.split("/")[-1] for s in steps),
        len(question_ids),
        graded,
        correct,
        cost,
        latencies,
        [],
    )


def oracle(
    answers: list[dict[str, Any]],
    grades: dict[tuple[str, str], dict[str, Any]],
    question_ids: list[str],
) -> Row:
    cost = 0.0
    correct = 0
    for qid in question_ids:
        options = [
            a.get("cost_usd") or 0.0
            for a in answers
            if a["id"] == qid
            and a["target"] not in ROUTERS
            and grades.get((a["target"], qid), {}).get("correct") is True
        ]
        if options:
            correct += 1
            cost += min(options)
    return Row(
        "Oráculo (mais barato que acertou)",
        len(question_ids),
        len(question_ids),
        correct,
        cost,
        [],
        [],
    )


def pick_ladder(rows: list[Row], max_gap: float = 0.10) -> list[str]:
    """Tune-set rule: step 1 = cheapest model within `max_gap` of the best; step 2 = best."""
    models = [r for r in rows if r.target not in ROUTERS and r.graded >= 20]
    best = max(models, key=lambda r: (r.accuracy, -r.cost_per_question))
    cheap = min(
        (r for r in models if r.accuracy >= best.accuracy - max_gap),
        key=lambda r: r.cost_per_question,
    )
    return [cheap.target] if cheap.target == best.target else [cheap.target, best.target]


def render(rows: list[Row], title: str) -> str:
    lines = [
        f"### {title}",
        "",
        "| Alvo | Acerto | IC 95% | Custo/pergunta | Custo/resp. correta | Latência p50 / p95 |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (-r.accuracy, r.cost_per_question)):
        lo, hi = wilson(r.correct, r.graded)
        cpc = f"${r.cost_per_correct:.4f}" if r.cost_per_correct else "—"
        lat = (
            f"{pct(r.latencies, 0.5) / 1000:.1f}s / {pct(r.latencies, 0.95) / 1000:.1f}s"
            if r.latencies
            else "—"
        )
        note = f" ({r.answered} resp.)" if r.answered < max(x.answered for x in rows) else ""
        lines.append(
            f"| {r.target}{note} | {r.correct}/{r.graded} = {r.accuracy:.0%} | {lo:.0%}-{hi:.0%} "
            f"| ${r.cost_per_question:.4f} | {cpc} | {lat} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark results table.")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--judge", required=True)
    parser.add_argument("--ladder", help="comma-separated steps; default: picked from the rows")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    run_dir = DATA_DIR / "runs" / args.run_name
    answers, grades = load(run_dir, args.judge)
    rows = single_rows(answers, grades)
    qids = sorted({a["id"] for a in answers})
    steps = args.ladder.split(",") if args.ladder else pick_ladder(rows)
    ladder = simulate_ladder(steps, answers, grades, qids)
    ladder.target = f"Escada: {ladder.target}"
    table = render([*rows, ladder, oracle(answers, grades, qids)], f"Resultados — {args.run_name}")
    print(table)
    print(f"\nEscada: {json.dumps(steps)}")
    if args.out:
        args.out.write_text(table + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
