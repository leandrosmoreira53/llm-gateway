"""Frozen benchmark context: retrieval snapshot (GW-2.0) and the session numbers block."""

import json
from pathlib import Path
from typing import Any

from bench.dataset import Question
from bench.prompt import Passage

MODES = ("hibrida", "rerank")


class Context:
    def __init__(self, snapshot: dict[str, Any], session_block: str | None) -> None:
        self._chunks: dict[str, dict[str, Any]] = snapshot["chunks"]
        self._hits: dict[str, dict[str, list[dict[str, Any]]]] = {
            q["id"]: q["modes"] for q in snapshot["questions"]
        }
        self.meta: dict[str, Any] = snapshot.get("meta", {})
        self.session_block = session_block

    @classmethod
    def load(cls, snapshot_path: Path, session_path: Path | None) -> "Context":
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        block = session_path.read_text(encoding="utf-8") if session_path else None
        return cls(snapshot, block)

    def passages(self, question_id: str, mode: str) -> list[Passage]:
        if mode not in MODES:
            raise ValueError(f"unknown retrieval mode {mode!r}")
        try:
            hits = self._hits[question_id][mode]
        except KeyError:
            raise KeyError(f"question {question_id} / mode {mode} not in snapshot") from None
        out: list[Passage] = []
        for hit in hits:
            chunk = self._chunks[str(hit["chunk_id"])]
            out.append(
                Passage(
                    chunk_id=int(hit["chunk_id"]),
                    document=Path(chunk["source"]).stem,
                    page=chunk.get("page"),
                    heading=chunk.get("heading"),
                    text=chunk["text"],
                )
            )
        return out

    def session_for(self, question: Question) -> str | None:
        """Session numbers only for questions tied to a session."""
        return self.session_block if "sessao" in question.filters else None
