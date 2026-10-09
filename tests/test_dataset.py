import json
from pathlib import Path
from typing import Any

import pytest

from bench.dataset import DatasetError, load_dataset
from bench.split import DEFAULT_SEED, SplitError, load_split, main, make_split

EXAMPLE = Path(__file__).parent.parent / "bench" / "datasets" / "example.jsonl"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def row(i: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"q{i:03d}",
        "question": f"pergunta {i}",
        "expected_answer": f"resposta {i}",
        **extra,
    }


def test_public_example_is_valid() -> None:
    questions = load_dataset(EXAMPLE)
    assert len(questions) == 6
    assert len({q.id for q in questions}) == 6


def test_blank_lines_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text(json.dumps(row(1)) + "\n\n" + json.dumps(row(2)) + "\n", encoding="utf-8")
    assert [q.id for q in load_dataset(path)] == ["q001", "q002"]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([row(1), row(1)], "duplicate id"),
        ([{"id": "q1", "question": "x"}], "expected_answer"),
        ([row(1, typo_field=True)], "typo_field"),
        ([row(1, id="bad id!")], "id"),
        ([row(1, citation_required=True)], "expected_sources"),
    ],
)
def test_invalid_rows_name_the_line(
    tmp_path: Path, rows: list[dict[str, Any]], message: str
) -> None:
    path = write_jsonl(tmp_path / "d.jsonl", rows)
    with pytest.raises(DatasetError, match=message):
        load_dataset(path)


def test_errors_do_not_echo_content(tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "d.jsonl", [row(1, question="TRECHO SECRETO", extra=1)])
    with pytest.raises(DatasetError) as info:
        load_dataset(path)
    assert "TRECHO SECRETO" not in str(info.value)
    assert "d.jsonl:1" in str(info.value)


def test_invalid_json_and_missing_or_empty_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="invalid JSON"):
        load_dataset(bad)
    with pytest.raises(DatasetError, match="not found"):
        load_dataset(tmp_path / "missing.jsonl")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="empty"):
        load_dataset(empty)


def test_split_58_is_29_29_disjoint_and_reproducible(tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "d.jsonl", [row(i) for i in range(1, 59)])
    questions = load_dataset(path)

    first = make_split(questions, seed=DEFAULT_SEED, dataset_sha256="x")
    second = make_split(list(reversed(questions)), seed=DEFAULT_SEED, dataset_sha256="x")

    assert len(first.tune) == len(first.test) == 29
    assert not set(first.tune) & set(first.test)
    assert first == second  # input order does not matter
    assert make_split(questions, seed=1, dataset_sha256="x") != first


def test_split_cli_freezes_and_detects_changes(tmp_path: Path) -> None:
    dataset = write_jsonl(tmp_path / "d.jsonl", [row(i) for i in range(1, 11)])
    out = tmp_path / "split.json"

    assert main(["--dataset", str(dataset), "--out", str(out)]) == 0
    split = load_split(out, dataset_path=dataset)
    assert len(split.tune) == len(split.test) == 5

    assert main(["--dataset", str(dataset), "--out", str(out)]) == 1  # frozen

    write_jsonl(dataset, [row(i) for i in range(1, 12)])
    with pytest.raises(SplitError, match="changed"):
        load_split(out, dataset_path=dataset)


def test_split_needs_two_questions(tmp_path: Path) -> None:
    questions = load_dataset(write_jsonl(tmp_path / "d.jsonl", [row(1)]))
    with pytest.raises(SplitError):
        make_split(questions, seed=DEFAULT_SEED, dataset_sha256="x")


def test_split_is_stratified_by_category(tmp_path: Path) -> None:
    sizes = {"comum": 15, "termo_exato": 10, "sem_resposta": 5, "extra": 8}
    rows = []
    i = 0
    for category, n in sizes.items():
        for _ in range(n):
            i += 1
            rows.append(row(i, category=category))
    questions = load_dataset(write_jsonl(tmp_path / "d.jsonl", rows))
    category_of = {q.id: q.category for q in questions}

    split = make_split(questions, seed=DEFAULT_SEED, dataset_sha256="x")

    assert len(split.tune) + len(split.test) == 38
    assert abs(len(split.tune) - len(split.test)) <= 1
    for category, n in sizes.items():
        in_tune = sum(category_of[i] == category for i in split.tune)
        assert in_tune in (n // 2, n - n // 2), category
