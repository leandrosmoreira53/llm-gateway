"""Tune/test split with a fixed seed. Only question IDs are versioned, never content.

Usage:
    uv run python -m bench.split --dataset PATH --out bench/datasets/split.json [--seed N]

An existing split is frozen: the command refuses to overwrite it. If answers are corrected later
(e.g. engineer review) but the IDs stay the same, record the new dataset hash explicitly with
`--update-fingerprint`; the change shows up in git history.
"""

import argparse
import json
import random
import sys
from collections import defaultdict
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
    """Stratified by category: each category is shuffled with `seed` and split in half.

    Odd-sized categories alternate (in category-name order) which side gets the extra question,
    so the overall split stays balanced (58 -> 29/29). Input order does not matter.
    """
    if len(questions) < 2:
        raise SplitError("Need at least 2 questions to split")
    by_category: dict[str, list[str]] = defaultdict(list)
    for q in questions:
        by_category[q.category or ""].append(q.id)

    rng = random.Random(seed)  # noqa: S311 - reproducible shuffle, not security
    tune: list[str] = []
    test: list[str] = []
    extra_to_test = True
    for category in sorted(by_category):
        ids = sorted(by_category[category])
        rng.shuffle(ids)
        half = len(ids) // 2
        if len(ids) % 2:
            half += 0 if extra_to_test else 1
            extra_to_test = not extra_to_test
        tune.extend(ids[:half])
        test.extend(ids[half:])
    return Split(seed=seed, dataset_sha256=dataset_sha256, tune=sorted(tune), test=sorted(test))


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


def update_fingerprint(path: Path, *, dataset_path: Path) -> Split:
    """Keep the frozen IDs and record the current dataset hash. Fails if the IDs changed."""
    split = Split.model_validate_json(path.read_text(encoding="utf-8"))
    ids = {q.id for q in load_dataset(dataset_path)}
    if set(split.tune) | set(split.test) != ids:
        raise SplitError("Split IDs do not match dataset IDs; the split cannot be kept")
    updated = split.model_copy(update={"dataset_sha256": dataset_fingerprint(dataset_path)})
    path.write_text(json.dumps(updated.model_dump(), indent=2) + "\n", encoding="utf-8")
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a frozen tune/test split.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--update-fingerprint",
        action="store_true",
        help="Keep the existing split and record the current dataset hash (IDs must match).",
    )
    args = parser.parse_args(argv)

    if args.update_fingerprint:
        split = update_fingerprint(args.out, dataset_path=args.dataset)
        print(f"fingerprint updated -> {split.dataset_sha256[:12]}")
        return 0
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
