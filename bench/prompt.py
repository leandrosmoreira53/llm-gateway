"""Prompt for benchmark answers. The template is versioned config: change it only on tune."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bench.dataset import Question

PROMPT_VERSION = "answer_v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md"


@dataclass(frozen=True)
class Passage:
    chunk_id: int
    document: str
    page: int | None
    heading: str | None
    text: str

    def render(self, n: int) -> str:
        where = f"{self.document}, p. {self.page}" if self.page is not None else self.document
        heading = f" — {self.heading}" if self.heading else ""
        return f"[{n}] Fonte: [{where}]{heading}\n{self.text.strip()}"


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_messages(
    question: Question, passages: list[Passage], session_block: str | None
) -> list[dict[str, Any]]:
    """System rules + one user message: NÚMEROS (session questions only), TRECHOS, PERGUNTA."""
    parts: list[str] = []
    if session_block:
        parts.append("NÚMEROS\n" + session_block.strip())
    if passages:
        parts.append(
            "TRECHOS\n" + "\n\n---\n\n".join(p.render(i) for i, p in enumerate(passages, 1))
        )
    else:
        parts.append("TRECHOS\n(nenhum trecho encontrado)")
    parts.append("PERGUNTA\n" + question.question)
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
