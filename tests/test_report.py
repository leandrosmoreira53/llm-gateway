from typing import Any

import pytest

from bench.report import oracle, pick_ladder, simulate_ladder, single_rows, wilson


def answer(target: str, qid: str, cost: float) -> dict[str, Any]:
    return {"target": target, "id": qid, "cost_usd": cost, "latency_ms": 1000.0}


def grade(correct: bool, citation_ok: bool = True) -> dict[str, Any]:
    return {"correct": correct, "citation_ok": citation_ok, "not_in_sources": False}


ANSWERS = [
    answer("cheap/a", "Q1", 0.001),
    answer("cheap/a", "Q2", 0.001),
    answer("big/b", "Q1", 0.010),
    answer("big/b", "Q2", 0.010),
    answer("openrouter/auto", "Q1", 0.0001),
]
GRADES = {
    ("cheap/a", "Q1"): grade(True),
    ("cheap/a", "Q2"): grade(False, citation_ok=False),
    ("big/b", "Q1"): grade(True),
    ("big/b", "Q2"): grade(True),
    ("openrouter/auto", "Q1"): grade(True),
}


def test_wilson_interval() -> None:
    lo, hi = wilson(24, 29)
    assert lo == pytest.approx(0.655, abs=0.01)
    assert hi == pytest.approx(0.924, abs=0.01)
    assert wilson(0, 0) == (0.0, 0.0)


def test_single_rows() -> None:
    rows = {r.target: r for r in single_rows(ANSWERS, GRADES)}
    assert rows["cheap/a"].correct == 1
    assert rows["cheap/a"].cost_per_question == pytest.approx(0.001)
    assert rows["big/b"].cost_per_correct == pytest.approx(0.010)


def test_ladder_escalates_only_when_check_fails() -> None:
    row = simulate_ladder(["cheap/a", "big/b"], ANSWERS, GRADES, ["Q1", "Q2"])
    # Q1: cheap passes the check and is right. Q2: cheap fails the citation check -> big is right.
    assert row.correct == 2
    assert row.cost == pytest.approx(0.001 + 0.001 + 0.010)


def test_oracle_ignores_routers_and_takes_cheapest_right_model() -> None:
    row = oracle(ANSWERS, GRADES, ["Q1", "Q2"])
    assert row.correct == 2
    assert row.cost == pytest.approx(0.001 + 0.010)


def test_pick_ladder_needs_enough_graded_answers() -> None:
    with pytest.raises(ValueError, match="empty"):
        pick_ladder(single_rows(ANSWERS, GRADES))
