"""Tune/test split with a fixed seed. Only question IDs are versioned, never content.

Usage:
    uv run python -m bench.split --dataset PATH --out bench/datasets/split.json [--seed N]

An existing split is frozen: the command refuses to overwrite it.
"""

import argparse
import json
import random
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from bench.dataset import Question, dataset_fingerprint, load_dataset

DEFAULT_SEED = 20261012  # Sprint 1 start date


class Split(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int
    dataset_sha256: str
    tune: list[str]
    test: list[str]


class SplitError(ValueError):
    pass


def make_split(questions: list[Question], *, seed: int, dataset_sha256: str) -> Split:
    """Shuffle sorted IDs with `seed`; the first half (rounded down) is tune, the rest is test."""
    ids = sorted(q.id for q in questions)
    if len(ids) < 2:
        raise SplitError("Need at least 2 questions to split")
    random.Random(seed).shuffle(ids)  # noqa: S311 - reproducible shuffle, not security
    half = len(ids) // 2
    return Split(
        seed=seed,
        dataset_sha256=dataset_sha256,
        tune=sorted(ids[:half]),
        test=sorted(ids[half:]),
    )


def load_split(path: Path, *, dataset_path: Path) -> Split:
    """Load a frozen split and check it still matches the dataset."""
    split = Split.model_validate_json(path.read_text(encoding="utf-8"))
    if split.dataset_sha256 != dataset_fingerprint(dataset_path):
        raise SplitError(
            "Dataset changed since the split was frozen; review the change before re-splitting"
        )
    ids = {q.id for q in load_dataset(dataset_path)}
    split_ids = set(split.tune) | set(split.test)
    if set(split.tune) & set(split.test):
        raise SplitError("Split has IDs in both tune and test")
    if split_ids != ids:
        raise SplitError("Split IDs do not match dataset IDs")
    return split


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a frozen tune/test split.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    if args.out.exists():
        print(f"{args.out} already exists; the split is frozen.", file=sys.stderr)
        return 1
    questions = load_dataset(args.dataset)
    split = make_split(questions, seed=args.seed, dataset_sha256=dataset_fingerprint(args.dataset))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(split.model_dump(), indent=2) + "\n", encoding="utf-8")
    print(f"tune={len(split.tune)} test={len(split.test)} seed={split.seed} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
