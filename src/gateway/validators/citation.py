"""Citation check: the answer cites its sources, and only sources it was actually given.

Accepted citation forms (as models really write them):
    [Doc, p. 12]   [Doc, p. 12, 14]   [Doc, pág. 12]   [3]   [3, p. 12]   [sessão]
Anything else in brackets (e.g. "[a]") is not treated as a citation.
"""

import re
import unicodedata
from dataclasses import dataclass, field

_BRACKET = re.compile(r"\[([^\[\]\n]{1,160})\]")
_SESSION = re.compile(r"^sess[aã]o$", re.IGNORECASE)
_INDEX = re.compile(r"^(\d{1,2})$")
_DOC_PAGES = re.compile(
    r"^(.+?),\s*(?:p\.|pp\.|pág\.?|página|pag\.?|p)\s*([\d\s,;e\u2013-]+)$", re.IGNORECASE
)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\u202f", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _doc_key(doc: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(doc).lower())


def _pages(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", text)]


@dataclass(frozen=True)
class Source:
    """A passage the model was given: document stem and page (None for page-less sources)."""

    document: str
    page: int | None


@dataclass
class CitationResult:
    citations: int = 0
    cited: set[tuple[str, int | None]] = field(default_factory=set)
    unknown: list[str] = field(default_factory=list)
    session_cited: bool = False

    @property
    def ok(self) -> bool:
        """At least one citation and none pointing outside the given context."""
        return self.citations > 0 and not self.unknown


def check_citations(
    answer: str, provided: list[Source], *, session_available: bool
) -> CitationResult:
    provided_pairs = {(_doc_key(s.document), s.page) for s in provided}
    provided_docs = {_doc_key(s.document) for s in provided}
    result = CitationResult()
    for raw in _BRACKET.findall(answer or ""):
        inner = _norm(raw)
        if _SESSION.match(inner):
            result.citations += 1
            result.session_cited = True
            if not session_available:
                result.unknown.append(inner)
            continue
        index = _INDEX.match(inner)
        if index:
            result.citations += 1
            n = int(index.group(1))
            if 1 <= n <= len(provided):
                src = provided[n - 1]
                result.cited.add((_doc_key(src.document), src.page))
            else:
                result.unknown.append(inner)
            continue
        doc_pages = _DOC_PAGES.match(inner)
        if not doc_pages:
            continue  # not a citation
        doc, pages = doc_pages.group(1).strip(), _pages(doc_pages.group(2))
        result.citations += 1
        if doc.isdigit() and 1 <= int(doc) <= len(provided):
            doc = provided[int(doc) - 1].document
        key = _doc_key(doc)
        if key not in provided_docs:
            result.unknown.append(inner)
            continue
        matched = [p for p in pages if (key, p) in provided_pairs]
        if matched:
            result.cited.update((key, p) for p in matched)
        else:
            result.unknown.append(inner)
    return result


def cites_any(result: CitationResult, gold: list[Source]) -> bool:
    """Whether any cited source is one the answer key points to."""
    return any((_doc_key(g.document), g.page) in result.cited for g in gold)
