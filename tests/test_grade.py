from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bench.context import Context
from bench.dataset import Question
from bench.grade import automatic_checks, grade, judge_messages, latest_answers, parse_verdict
from bench.run import read_records
from gateway.providers import ChatRequest, ChatResult, ResolvedRoute, Usage

SNAPSHOT: dict[str, Any] = {
    "questions": [
        {"id": "G01", "modes": {"hibrida": [{"chunk_id": 1, "score": 1.0}], "rerank": []}}
    ],
    "chunks": {"1": {"source": "Manual-A.pdf", "page": 7, "heading": None, "text": "t"}},
}
Q_CITE = Question(
    id="G01",
    question="Q?",
    expected_answer="mais preso",
    citation_required=True,
    expected_sources=["a p.7"],
    gold_sources=[("Manual-A", 7)],
    trap="não confundir com Gen 6",
)


def record(content: str, target: str = "m/one") -> dict[str, Any]:
    return {"id": "G01", "target": target, "mode": "hibrida", "content": content}


class FakeJudge:
    name = "fake"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    async def chat(self, request: ChatRequest, route: ResolvedRoute) -> ChatResult:
        self.calls += 1
        return ChatResult(
            id="j",
            model_requested=route.model,
            model_used=route.model,
            provider=None,
            content=self.reply,
            finish_reason="stop",
            usage=Usage(cost_usd=Decimal("0.001")),
            latency_ms=1.0,
            raw={},
        )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"correct": true, "reason": "ok"}', (True, "ok")),
        ('Claro.\n```json\n{"correct": false, "reason": "inverteu"}\n```', (False, "inverteu")),
        ("sem json", (None, "judge returned no JSON")),
        ('{"correct": "sim"}', (None, "judge JSON without boolean 'correct'")),
    ],
)
def test_parse_verdict(text: str, expected: tuple[bool | None, str]) -> None:
    assert parse_verdict(text) == expected


def test_judge_sees_trap_and_no_answer_note() -> None:
    no_answer = Q_CITE.model_copy(update={"no_answer": True})
    user = judge_messages(no_answer, "resp")[1]["content"]
    assert "ARMADILHA\nnão confundir com Gen 6" in user
    assert "NÃO está nas fontes" in user
    assert user.endswith("RESPOSTA DO MODELO\nresp")


def test_automatic_checks() -> None:
    ctx = Context(SNAPSHOT, session_block=None)
    good = automatic_checks(record("Mais preso [Manual-A, p. 7]."), Q_CITE, ctx)
    assert good["citation_ok"]
    assert good["gold_cited"] is True
    assert good["not_in_sources"] is False
    bad = automatic_checks(record("Mais preso [Manual-A, p. 8]."), Q_CITE, ctx)
    assert not bad["citation_ok"]
    assert bad["unknown_citations"] == ["Manual-A, p. 8"]


async def test_grade_combines_judge_and_citation_and_resumes(tmp_path: Path) -> None:
    out = tmp_path / "grades" / "j.jsonl"
    answers = [record("Mais preso [1].", "m/cited"), record("Mais preso.", "m/uncited")]
    judge = FakeJudge('{"correct": true, "reason": "ok"}')
    kwargs: dict[str, Any] = {
        "judge": "j/judge",
        "answers": answers,
        "questions": {"G01": Q_CITE},
        "context": Context(SNAPSHOT, session_block=None),
        "out_path": out,
        "max_cost_usd": Decimal("1"),
    }

    counts = await grade(provider=judge, **kwargs)

    assert counts["graded"] == 2
    rows = {r["target"]: r for r in read_records(out)}
    assert rows["m/cited"]["correct"] is True
    assert rows["m/uncited"]["correct"] is False  # judge said yes, but citation was required
    assert (await grade(provider=judge, **kwargs))["skipped"] == 2
    assert judge.calls == 2


def test_latest_answers_keeps_last_success(tmp_path: Path) -> None:
    path = tmp_path / "m__one.jsonl"
    path.write_text(
        '{"id": "G01", "target": "m/one", "error": "x"}\n'
        '{"id": "G01", "target": "m/one", "error": null, "content": "ok"}\n',
        encoding="utf-8",
    )
    [only] = latest_answers(tmp_path)
    assert only["content"] == "ok"
