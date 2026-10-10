from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bench.catalog import Price
from bench.context import Context
from bench.dataset import Question
from bench.prompt import build_messages
from bench.run import estimate, read_records, run, spent_usd, target_file
from gateway.providers import ChatRequest, ChatResult, ResolvedRoute, Usage
from gateway.providers.errors import ProviderAuthError, ProviderUnavailableError

SNAPSHOT: dict[str, Any] = {
    "meta": {"k": 2},
    "questions": [
        {"id": "G01", "modes": {"hibrida": [{"chunk_id": 1, "score": 0.9}], "rerank": []}},
        {"id": "G02", "modes": {"hibrida": [{"chunk_id": 2, "score": 0.5}], "rerank": []}},
    ],
    "chunks": {
        "1": {
            "source": "docs/Manual-A.pdf",
            "series": "nextgen",
            "page": 7,
            "heading": "Molas",
            "text": "texto A",
        },
        "2": {
            "source": "Manual-B.pdf",
            "series": "cup",
            "page": None,
            "heading": None,
            "text": "texto B",
        },
    },
}
Q1 = Question(id="G01", question="Pergunta um?", expected_answer="x", filters={"carro": "nextgen"})
Q2 = Question(
    id="G02",
    question="Pergunta dois?",
    expected_answer="y",
    filters={"carro": "nextgen", "sessao": "s1"},
)


def make_context() -> Context:
    return Context(SNAPSHOT, session_block="voltas: 10")


class FakeProvider:
    name = "fake"

    def __init__(
        self, failures: dict[str, list[Exception]] | None = None, cost: str = "0.01"
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self.failures = failures or {}
        self.cost = Decimal(cost)

    async def chat(self, request: ChatRequest, route: ResolvedRoute) -> ChatResult:
        user = request.messages[-1].content
        assert isinstance(user, str)
        qid = "G01" if "Pergunta um" in user else "G02"
        self.calls.append((route.model, qid))
        pending = self.failures.get(f"{route.model}:{qid}")
        if pending:
            raise pending.pop(0)
        return ChatResult(
            id="gen-1",
            model_requested=route.model,
            model_used=route.model + "-picked",
            provider="P",
            content=f"resposta {qid}",
            finish_reason="stop",
            usage=Usage(
                prompt_tokens=100, completion_tokens=20, total_tokens=120, cost_usd=self.cost
            ),
            latency_ms=12.3,
            raw={"usage": {"completion_tokens_details": {"reasoning_tokens": 7}}},
        )


def test_messages_label_sources_and_add_numbers_only_for_session_questions() -> None:
    ctx = make_context()
    m1 = build_messages(Q1, ctx.passages("G01", "hibrida"), ctx.session_for(Q1))
    m2 = build_messages(Q2, ctx.passages("G02", "hibrida"), ctx.session_for(Q2))

    assert m1[0]["role"] == "system"
    assert "engenheiro de corrida" in m1[0]["content"]
    assert "[1] Fonte: [Manual-A, p. 7] — Molas\ntexto A" in m1[1]["content"]
    assert "NÚMEROS" not in m1[1]["content"]
    assert m2[1]["content"].startswith("NÚMEROS\nvoltas: 10")
    assert "[1] Fonte: [Manual-B]\ntexto B" in m2[1]["content"]
    assert m2[1]["content"].endswith("PERGUNTA\nPergunta dois?")


def test_empty_retrieval_is_explicit() -> None:
    ctx = make_context()
    messages = build_messages(Q1, ctx.passages("G01", "rerank"), None)
    assert "TRECHOS\n(nenhum trecho encontrado)" in messages[1]["content"]


def test_estimate_prices_routers_with_proxy() -> None:
    table = {
        "a/cheap": Price(1e-6, 2e-6, reasoning=False),
        "a/think": Price(1e-6, 2e-6, reasoning=True),
        "anthropic/claude-sonnet-5.5": Price(2e-6, 10e-6, reasoning=True),
        "openrouter/auto": Price(-1, -1, reasoning=False),
    }
    rows = {
        r.target: r for r in estimate([Q1], make_context(), "hibrida", [*table, "x/missing"], table)
    }

    assert rows["a/cheap"].low_usd == rows["a/cheap"].high_usd
    assert rows["a/think"].high_usd is not None
    assert rows["a/think"].low_usd is not None
    assert rows["a/think"].high_usd > rows["a/think"].low_usd
    assert rows["openrouter/auto"].low_usd == rows["anthropic/claude-sonnet-5.5"].low_usd
    assert "router" in rows["openrouter/auto"].note
    assert rows["x/missing"].low_usd is None


async def test_run_records_answers_and_resumes(tmp_path: Path) -> None:
    provider = FakeProvider()
    kwargs: dict[str, Any] = {
        "questions": [Q1, Q2],
        "context": make_context(),
        "mode": "hibrida",
        "targets": ["m/one", "m/two"],
        "run_dir": tmp_path,
        "max_cost_usd": Decimal("1"),
        "subset": "tune",
    }

    counts = await run(provider=provider, **kwargs)

    assert counts == {"answered": 4, "errors": 0, "skipped": 0}
    [first, *_] = read_records(target_file(tmp_path, "m/one"))
    assert first["model_used"] == "m/one-picked"
    assert first["reasoning_tokens"] == 7
    assert first["prompt_version"] == "answer_v1"
    assert spent_usd(tmp_path) == Decimal("0.04")

    again = await run(provider=provider, **kwargs)
    assert again == {"answered": 0, "errors": 0, "skipped": 4}
    assert len(provider.calls) == 4


async def test_retryable_errors_retry_and_fatal_errors_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("bench.run.asyncio.sleep", no_sleep)
    provider = FakeProvider(
        failures={
            "m/one:G01": [ProviderUnavailableError("down")],
            "m/one:G02": [ProviderAuthError("bad key")],
        }
    )

    counts = await run(
        provider=provider,
        questions=[Q1, Q2],
        context=make_context(),
        mode="hibrida",
        targets=["m/one"],
        run_dir=tmp_path,
        max_cost_usd=Decimal("1"),
        subset="tune",
    )

    assert counts == {"answered": 1, "errors": 1, "skipped": 0}
    records = {r["id"]: r for r in read_records(target_file(tmp_path, "m/one"))}
    assert records["G01"]["attempts"] == 2
    assert records["G02"]["error"].startswith("ProviderAuthError")

    # A failed answer is retried on the next run.
    await run(
        provider=provider,
        questions=[Q1, Q2],
        context=make_context(),
        mode="hibrida",
        targets=["m/one"],
        run_dir=tmp_path,
        max_cost_usd=Decimal("1"),
        subset="tune",
    )
    assert provider.calls.count(("m/one", "G02")) == 2


async def test_cost_cap_stops_the_run(tmp_path: Path) -> None:
    provider = FakeProvider(cost="0.6")

    counts = await run(
        provider=provider,
        questions=[Q1, Q2],
        context=make_context(),
        mode="hibrida",
        targets=["m/one", "m/two"],
        run_dir=tmp_path,
        max_cost_usd=Decimal("1"),
        subset="tune",
        concurrency=1,
    )

    assert counts["answered"] == 2  # 0.6 + 0.6 crosses the cap; the rest is not called
    assert counts["stopped_by_cap"] == 2
    assert len(provider.calls) == 2
