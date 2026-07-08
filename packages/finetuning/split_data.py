"""
Sentinel — Train/val/test split for the compliance fine-tuning data.

Reads packages/finetuning/data/raw_synthetic.jsonl (produced by
data_generator.py) and writes an 80/10/10 split:

    packages/finetuning/data/train.jsonl
    packages/finetuning/data/val.jsonl
    packages/finetuning/data/test.jsonl

The split is STRATIFIED by label — each of the 4 classes is split 80/10/10
independently, so train/val/test all preserve the ~30/25/25/20 distribution.
It is deterministic (fixed seed) and idempotent (overwrites on re-run), so you
can run it again after the full generation finishes.

Run:
    python -u packages/finetuning/split_data.py
"""

from __future__ import annotations

import json
import os
import random
from collections import Counter, defaultdict

DATA_DIR = "packages/finetuning/data"
RAW_PATH = os.path.join(DATA_DIR, "raw_synthetic.jsonl")
SPLITS = {
    "train": os.path.join(DATA_DIR, "train.jsonl"),
    "val": os.path.join(DATA_DIR, "val.jsonl"),
    "test": os.path.join(DATA_DIR, "test.jsonl"),
}

VAL_FRAC = 0.10
TEST_FRAC = 0.10          # train gets the remaining 0.80
SEED = 42


def _load(path: str) -> list[dict]:
    """Load JSONL, skipping blank/corrupt lines."""
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _dedupe(rows: list[dict]) -> list[dict]:
    """Drop exact-duplicate inputs (models occasionally repeat a claim)."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        key = (r.get("input") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _stratified_split(rows: list[dict]) -> dict[str, list[dict]]:
    """Split each label group 80/10/10, then shuffle the combined splits."""
    rng = random.Random(SEED)
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_label[r.get("label", "?")].append(r)

    result: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for label in sorted(by_label):
        group = by_label[label]
        rng.shuffle(group)
        n = len(group)
        n_test = round(n * TEST_FRAC)
        n_val = round(n * VAL_FRAC)
        # guarantee at least 1 in val/test when a class has enough samples
        if n >= 10:
            n_test = max(1, n_test)
            n_val = max(1, n_val)
        result["test"].extend(group[:n_test])
        result["val"].extend(group[n_test:n_test + n_val])
        result["train"].extend(group[n_test + n_val:])

    for split in result.values():
        rng.shuffle(split)
    return result


def _write(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _fmt_dist(rows: list[dict]) -> str:
    c = Counter(r.get("label", "?") for r in rows)
    total = sum(c.values()) or 1
    parts = [f"{lbl} {c[lbl]} ({100 * c[lbl] / total:.0f}%)" for lbl in sorted(c)]
    return ", ".join(parts)


def main() -> None:
    if not os.path.exists(RAW_PATH):
        raise SystemExit(f"{RAW_PATH} not found — run data_generator.py first.")

    rows = _load(RAW_PATH)
    deduped = _dedupe(rows)
    dropped = len(rows) - len(deduped)
    print(f"Loaded {len(rows)} rows ({dropped} duplicate inputs dropped).")

    splits = _stratified_split(deduped)

    for name, path in SPLITS.items():
        _write(path, splits[name])

    total = sum(len(v) for v in splits.values()) or 1
    print("\nSplit summary:")
    for name in ("train", "val", "test"):
        rows_ = splits[name]
        print(f"  {name:<5} {len(rows_):>5}  ({100 * len(rows_) / total:4.1f}%)  "
              f"→ {SPLITS[name]}")
        print(f"        {_fmt_dist(rows_)}")


if __name__ == "__main__":
    main()
