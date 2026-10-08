"""Benchmark dataset: JSONL format, validation and loading.

The real answer key lives outside the repository (BENCH_DATASET_PATH); see bench/datasets/README.md.
"""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    # Optional extra context sent with the question (car, track, setup values...).
    context: str | None = None
    citation_required: bool = False
    # Sources the answer should cite when citation_required is true.
    expected_sources: list[str] = Field(default_factory=list)
    category: str | None = None


class DatasetError(ValueError):
    pass


def load_dataset(path: Path) -> list[Question]:
    """Load and validate a JSONL dataset. Errors name the line, never echo its content."""
    if not path.is_file():
        raise DatasetError(f"Dataset file not found: {path}")
    questions: list[Question] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                question = Question.model_validate(json.loads(line))
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{path.name}:{line_no}: invalid JSON ({exc.msg})") from exc
            except ValidationError as exc:
                fields = ", ".join(".".join(map(str, e["loc"])) for e in exc.errors())
                raise DatasetError(f"{path.name}:{line_no}: invalid fields: {fields}") from exc
            if question.id in seen:
                raise DatasetError(f"{path.name}:{line_no}: duplicate id {question.id!r}")
            if question.citation_required and not question.expected_sources:
                raise DatasetError(
                    f"{path.name}:{line_no}: citation_required without expected_sources"
                )
            seen.add(question.id)
            questions.append(question)
    if not questions:
        raise DatasetError(f"Dataset is empty: {path}")
    return questions


def dataset_fingerprint(path: Path) -> str:
    """SHA-256 of the file, used to detect that the answer key changed after the split."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
