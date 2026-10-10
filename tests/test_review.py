import csv
import json
from pathlib import Path
from typing import Any

from bench.dataset import Question
from bench.review import agreement, parse_verdict, pick_sample, write_sample

QUESTIONS = {
    f"G{i:02d}": Question(
        id=f"G{i:02d}",
        question=f"pergunta {i}",
        expected_answer=f"resp {i}",
        category=["comum", "sessao", "sem_resposta"][i % 3],
        no_answer=i % 3 == 2,
    )
    for i in range(1, 13)
}


def answers() -> list[dict[str, Any]]:
    return [
        {"id": qid, "target": t, "content": f"{t} diz {qid}"}
        for t in ("m/a", "m/b", "m/c")
        for qid in QUESTIONS
    ]


def test_sample_is_balanced_across_targets_and_deterministic() -> None:
    first = pick_sample(answers(), QUESTIONS, 9)
    second = pick_sample(list(reversed(answers())), QUESTIONS, 9)

    assert [(a["target"], a["id"]) for a in first] == [(a["target"], a["id"]) for a in second]
    per_target = {t: sum(a["target"] == t for a in first) for t in ("m/a", "m/b", "m/c")}
    assert per_target == {"m/a": 3, "m/b": 3, "m/c": 3}
    assert {QUESTIONS[a["id"]].category for a in first} == {"comum", "sessao", "sem_resposta"}


def test_sheet_is_blind_and_agreement_is_computed(tmp_path: Path) -> None:
    sample = pick_sample(answers(), QUESTIONS, 4)
    sheet = write_sample(sample, QUESTIONS, tmp_path)

    text = sheet.read_text(encoding="utf-8-sig")
    assert "m/a" not in text.split("\n")[0]
    assert "target" not in text

    rows = list(csv.DictReader(sheet.open(encoding="utf-8-sig"), delimiter=";"))
    for row, verdict in zip(rows, ["certo", "errado", "C", ""], strict=True):
        row["veredito"] = verdict
    with sheet.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    key = json.loads((tmp_path / "chave.json").read_text(encoding="utf-8"))
    grades = [{"target": k["target"], "id": k["id"], "judge_correct": True} for k in key]
    result = agreement(tmp_path, grades)

    assert result["reviewed"] == 3  # empty verdict skipped
    assert result["agree"] == 2
    assert len(result["disagreements"]) == 1


def test_parse_verdict() -> None:
    assert parse_verdict(" Certo ") is True
    assert parse_verdict("errado") is False
    assert parse_verdict("talvez") is None
