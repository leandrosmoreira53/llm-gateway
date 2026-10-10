"""Human review of the judge (GW-2.4): blind sample graded by hand, then agreement with judge.

    uv run python -m bench.review sample --run-name v0-tune --size 30
    uv run python -m bench.review agreement --run-name v0-tune --judge <slug>

`sample` writes bench/data/runs/<run>/review/revisao.csv (opens in Excel: UTF-8 with BOM, ";"
separator) and a separate key file. The sheet hides which model wrote each answer, so the reviewer
is not biased. Fill the column "veredito" with "certo" or "errado". Files stay outside git: they
quote private sources.
"""

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from bench.dataset import Question, load_dataset
from bench.grade import grades_path, latest_answers
from bench.run import DATA_DIR, read_records
from gateway.config import Settings

SEED = 20261010
FIELDS = [
    "n",
    "pergunta",
    "resposta_esperada",
    "observacao",
    "resposta_do_modelo",
    "veredito",
    "comentario",
]


def pick_sample(
    answers: list[dict[str, Any]], questions: dict[str, Question], size: int, seed: int = SEED
) -> list[dict[str, Any]]:
    """Round-robin over targets, preferring categories not yet in the sample. Deterministic."""
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling, not security
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for answer in sorted(answers, key=lambda a: (a["target"], a["id"])):
        by_target[answer["target"]].append(answer)
    for pool in by_target.values():
        rng.shuffle(pool)
    targets = sorted(by_target)
    rng.shuffle(targets)

    chosen: list[dict[str, Any]] = []
    seen_categories: dict[str | None, int] = defaultdict(int)
    while len(chosen) < size and any(by_target.values()):
        for target in targets:
            pool = by_target[target]
            if not pool or len(chosen) >= size:
                continue
            pool.sort(key=lambda a: seen_categories[questions[a["id"]].category])
            answer = pool.pop(0)
            seen_categories[questions[answer["id"]].category] += 1
            chosen.append(answer)
    rng.shuffle(chosen)
    return chosen


def observation(question: Question) -> str:
    notes = []
    if question.no_answer:
        notes.append("Gabarito: a informação NÃO está nas fontes.")
    if question.trap:
        notes.append(f"Armadilha: {question.trap}")
    return " ".join(notes)


def write_sample(
    sample: list[dict[str, Any]], questions: dict[str, Question], out_dir: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    sheet = out_dir / "revisao.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        for n, answer in enumerate(sample, 1):
            q = questions[answer["id"]]
            writer.writerow(
                {
                    "n": n,
                    "pergunta": q.question,
                    "resposta_esperada": q.expected_answer,
                    "observacao": observation(q),
                    "resposta_do_modelo": answer.get("content") or "",
                    "veredito": "",
                    "comentario": "",
                }
            )
    key = [{"n": n, "id": a["id"], "target": a["target"]} for n, a in enumerate(sample, 1)]
    (out_dir / "chave.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    return sheet


def parse_verdict(text: str) -> bool | None:
    value = text.strip().lower()
    if value in {"certo", "c", "correto", "sim", "s", "1", "ok"}:
        return True
    if value in {"errado", "e", "incorreto", "não", "nao", "n", "0"}:
        return False
    return None


def agreement(out_dir: Path, grades: list[dict[str, Any]]) -> dict[str, Any]:
    key = {
        row["n"]: row for row in json.loads((out_dir / "chave.json").read_text(encoding="utf-8"))
    }
    judge = {(g["target"], g["id"]): g.get("judge_correct") for g in grades}
    total = agree = 0
    disagreements: list[dict[str, Any]] = []
    with (out_dir / "revisao.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            human = parse_verdict(row.get("veredito", ""))
            meta = key[int(row["n"])]
            machine = judge.get((meta["target"], meta["id"]))
            if human is None or machine is None:
                continue
            total += 1
            if human == machine:
                agree += 1
            else:
                disagreements.append({**meta, "human": human, "judge": machine})
    return {
        "reviewed": total,
        "agree": agree,
        "agreement": agree / total if total else None,
        "disagreements": disagreements,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Human review of the judge.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--run-name", required=True)
    s.add_argument("--size", type=int, default=30)
    a = sub.add_parser("agreement")
    a.add_argument("--run-name", required=True)
    a.add_argument("--judge", required=True)
    args = parser.parse_args(argv)

    run_dir = DATA_DIR / "runs" / args.run_name
    out_dir = run_dir / "review"
    if args.cmd == "sample":
        settings = Settings()
        if settings.bench_dataset_path is None:
            parser.error("BENCH_DATASET_PATH is not set")
        questions = {q.id: q for q in load_dataset(settings.bench_dataset_path)}
        sample = pick_sample(latest_answers(run_dir), questions, args.size)
        print(f"{len(sample)} answers -> {write_sample(sample, questions, out_dir)}")
        return 0

    result = agreement(out_dir, read_records(grades_path(run_dir, args.judge)))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
