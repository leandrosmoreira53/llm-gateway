"""Detects answers that say the information is not in the sources.

Used two ways: for questions with no answer in the sources this is the expected behavior; for
answerable questions it flags a missed answer. Phrase-based on purpose (cheap, auditable); the LLM
judge has the final word on correctness, and the two are compared in the report.
"""

import re
import unicodedata

_PATTERNS = [
    r"n[aã]o (est[aá]|consta|aparece|h[aá])\w* (nas|nos|em nenhum|entre os) "
    r"(fontes|trechos|manuais|dados)",
    r"(as fontes|os trechos|os manuais|os dados)( fornecid\w+)? n[aã]o "
    r"(trazem|tra[sz]|cont[eê]m|mencionam|"
    r"informam|cobrem|sustentam|respondem|t[eê]m|dizem|abordam|falam)",
    r"n[aã]o (h[aá]|encontrei|tenho|existe) (informa[cç][aã]o|dados?|trecho|base|men[cç][aã]o)",
    r"sem (trecho|fonte|informa[cç][aã]o) (que|para) (sustente|responda|confirme)",
    r"n[aã]o (sei|posso (afirmar|responder|confirmar))",
    r"informa[cç][aã]o n[aã]o (est[aá] dispon[ií]vel|consta|encontrada)",
    r"(not|isn't|is not) (in|covered by|available in) the (sources|passages|manuals)",
]
_REGEX = re.compile("|".join(f"(?:{p})" for p in _PATTERNS), re.IGNORECASE)


def says_not_in_sources(answer: str) -> bool:
    text = unicodedata.normalize("NFKC", answer or "").replace("\u202f", " ")
    return bool(_REGEX.search(text))
