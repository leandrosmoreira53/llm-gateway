import json
from pathlib import Path
from typing import Any

import pytest

from bench.dataset import DatasetError, load_dataset
from bench.split import SplitError, load_split, main


def iracingeng_row(i: int, **extra: Any) -> dict[str, Any]:
    """Synthetic row in iRacingEng's gabarito format (no real content)."""
    return {
        "id": f"G{i:02d}",
        "categoria": "comum",
        "pergunta": f"pergunta {i}",
        "pergunta_en": f"question {i}",
        "filtros": {"carro": "nextgen"},
        "resposta_esperada": f"resposta {i}",
        "fontes": [
            {
                "doc": "Manual X",
                "arquivo": "x.pdf",
                "serie": "cup",
                "pagina": 7,
                "trecho": "trecho de teste",
            }
        ],
        "armadilha": None,
        "sem_resposta": False,
        "autor": "claude",
        "revisao": {"leandro": "ok", "data": "2026-10-01", "engenheiro": None},
        **extra,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_iracingeng_row_maps_to_question(tmp_path: Path) -> None:
    [q] = load_dataset(write_jsonl(tmp_path / "g.jsonl", [iracingeng_row(1)]))

    assert q.id == "G01"
    assert q.question == "pergunta 1"
    assert q.question_en == "question 1"
    assert q.expected_answer == "resposta 1"
    assert q.category == "comum"
    assert q.filters == {"carro": "nextgen"}
    assert q.citation_required is True
    assert q.expected_sources == ["Manual X p.7"]
    assert q.source_passages == ["trecho de teste"]
    assert q.no_answer is False
    assert q.engineer_reviewed is False
    assert "trecho de teste" not in repr(q)  # private excerpts stay out of reprs


def test_no_answer_question_does_not_require_citation(tmp_path: Path) -> None:
    row = iracingeng_row(1, sem_resposta=True, fontes=[], categoria="sem_resposta")
    [q] = load_dataset(write_jsonl(tmp_path / "g.jsonl", [row]))

    assert q.no_answer is True
    assert q.citation_required is False


def test_session_source_and_trap(tmp_path: Path) -> None:
    row = iracingeng_row(
        1,
        armadilha="não confundir séries",
        fontes=[{"doc": "sessao", "sessao": "S1", "dado": "pressao_lf", "valor": "18 psi"}],
    )
    [q] = load_dataset(write_jsonl(tmp_path / "g.jsonl", [row]))

    assert q.trap == "não confundir séries"
    assert q.expected_sources == ["sessao"]
    assert q.source_passages == ["S1: pressao_lf = 18 psi"]


def test_engineer_review_is_detected(tmp_path: Path) -> None:
    row = iracingeng_row(1, revisao={"leandro": "ok", "data": "x", "engenheiro": "ok"})
    [q] = load_dataset(write_jsonl(tmp_path / "g.jsonl", [row]))
    assert q.engineer_reviewed is True


def test_unknown_iracingeng_field_is_rejected(tmp_path: Path) -> None:
    path = write_jsonl(tmp_path / "g.jsonl", [iracingeng_row(1, campo_novo=1)])
    with pytest.raises(DatasetError, match="campo_novo"):
        load_dataset(path)


def test_non_object_line_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "g.jsonl"
    path.write_text("[1, 2]\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="JSON object"):
        load_dataset(path)


def test_update_fingerprint_keeps_ids(tmp_path: Path) -> None:
    dataset = write_jsonl(tmp_path / "g.jsonl", [iracingeng_row(i) for i in range(1, 11)])
    out = tmp_path / "split.json"
    assert main(["--dataset", str(dataset), "--out", str(out)]) == 0
    before = load_split(out, dataset_path=dataset)

    # Engineer corrects an answer: same IDs, different content.
    rows = [iracingeng_row(i) for i in range(1, 11)]
    rows[0]["resposta_esperada"] = "resposta corrigida"
    write_jsonl(dataset, rows)
    with pytest.raises(SplitError, match="changed"):
        load_split(out, dataset_path=dataset)

    assert main(["--dataset", str(dataset), "--out", str(out), "--update-fingerprint"]) == 0
    after = load_split(out, dataset_path=dataset)
    assert (after.tune, after.test) == (before.tune, before.test)
    assert after.dataset_sha256 != before.dataset_sha256


def test_update_fingerprint_refuses_changed_ids(tmp_path: Path) -> None:
    dataset = write_jsonl(tmp_path / "g.jsonl", [iracingeng_row(i) for i in range(1, 11)])
    out = tmp_path / "split.json"
    assert main(["--dataset", str(dataset), "--out", str(out)]) == 0

    write_jsonl(dataset, [iracingeng_row(i) for i in range(1, 12)])
    with pytest.raises(SplitError, match="IDs"):
        main(["--dataset", str(dataset), "--out", str(out), "--update-fingerprint"])
