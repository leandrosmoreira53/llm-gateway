import pytest

from gateway.validators import Source, check_citations, cites_any, says_not_in_sources

PROVIDED = [
    Source("NASCAR-NextGen-Cars-Manual-V2", 12),
    Source("Shock-Tuning-User-Guide", 4),
    Source("cup_gen6_tips_for_setup", None),
]


@pytest.mark.parametrize(
    "answer",
    [
        "Aumente a cunha [NASCAR-NextGen-Cars-Manual-V2, p. 12].",
        "Ver [NASCAR-NextGen-Cars-Manual-V2, p.\u202f12].",
        "Ver [NASCAR NextGen Cars Manual V2, pág. 12].",
        "Ver [1].",
        "Ver [1, p. 12].",
        "Ver [NASCAR-NextGen-Cars-Manual-V2, p. 12, 13].",
    ],
)
def test_valid_citation_forms(answer: str) -> None:
    result = check_citations(answer, PROVIDED, session_available=False)
    assert result.ok
    assert ("nascarnextgencarsmanualv2", 12) in result.cited


def test_citation_outside_context_is_flagged() -> None:
    result = check_citations(
        "Isso [NASCAR-NextGen-Cars-Manual-V2, p. 99] e [Manual-Inventado, p. 1] e [9].",
        PROVIDED,
        session_available=False,
    )
    assert result.citations == 3
    assert not result.ok
    assert len(result.unknown) == 3


def test_no_citation_fails_and_format_markers_are_ignored() -> None:
    result = check_citations("(a) Resposta [a] sem fonte.", PROVIDED, session_available=False)
    assert result.citations == 0
    assert not result.ok


def test_session_citation_needs_session_context() -> None:
    assert check_citations("Média 15,3 s [sessão].", PROVIDED, session_available=True).ok
    without = check_citations("Média 15,3 s [sessão].", PROVIDED, session_available=False)
    assert not without.ok


def test_cites_any_gold() -> None:
    result = check_citations("x [2]", PROVIDED, session_available=False)
    assert cites_any(result, [Source("Shock-Tuning-User-Guide", 4)])
    assert not cites_any(result, [Source("NASCAR-NextGen-Cars-Manual-V2", 12)])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Essa informação não está nas fontes fornecidas.", True),
        ("Os trechos não trazem o valor de pressão recomendado.", True),
        ("Não há informação sobre isso nos manuais.", True),
        ("Não sei: sem trecho que sustente a resposta.", True),
        ("Aumente a cunha em 0,5% [1].", False),
    ],
)
def test_not_in_sources(text: str, expected: bool) -> None:
    assert says_not_in_sources(text) is expected
