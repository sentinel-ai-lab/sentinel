"""
Sentinel — CI Quality Gate (PR Blocker)

Evaluates the regression QA benchmark set on pull requests and blocks merging
if core RAG metrics drop below required quality thresholds:
  - FAITHFULNESS_THRESHOLD: default 0.80
  - RECALL_THRESHOLD: default 0.85

Usage:
  python packages/evals/ci_gate.py --set 100
  python packages/evals/ci_gate.py --set 20 --strict
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from packages.evals.ragas_eval import run_ragas_eval


def load_eval_set(path: str = "packages/evals/data/eval_qa_pairs.json") -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Evaluation QA dataset not found at {path}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def run_ci_gate(
    n_queries: int = 100,
    faithfulness_threshold: float | None = None,
    recall_threshold: float | None = None,
    dataset_path: str = "packages/evals/data/eval_qa_pairs.json",
) -> int:
    """Runs the PR-blocking evaluation gate."""
    print("=" * 60)
    print("🛡️  SENTINEL — CI EVALUATION QUALITY GATE")
    print("=" * 60)

    qa_pairs = load_eval_set(dataset_path)[:n_queries]
    print(f"Loaded {len(qa_pairs)} regression test queries from {dataset_path}")

    f_thresh = (
        faithfulness_threshold
        if faithfulness_threshold is not None
        else float(os.getenv("FAITHFULNESS_THRESHOLD", "0.80"))
    )
    r_thresh = (
        recall_threshold
        if recall_threshold is not None
        else float(os.getenv("RECALL_THRESHOLD", "0.85"))
    )

    eval_result = run_ragas_eval(qa_pairs)
    scores = eval_result.to_dict()

    thresholds = {
        "faithfulness": f_thresh,
        "context_recall": r_thresh,
    }

    print("\nEvaluation Results:")
    print(f"  • Faithfulness:       {scores['faithfulness']:.3f} (Threshold: {f_thresh:.2f})")
    print(f"  • Context Recall:     {scores['context_recall']:.3f} (Threshold: {r_thresh:.2f})")
    print(f"  • Answer Relevancy:   {scores['answer_relevancy']:.3f}")
    print(f"  • Context Precision:  {scores['context_precision']:.3f}")

    failures = []
    for metric, threshold in thresholds.items():
        if scores[metric] < threshold:
            failures.append(f"{metric}: {scores[metric]:.3f} < {threshold:.2f}")

    print("-" * 60)
    if failures:
        print("❌ EVAL GATE FAILED — QUALITY DROP DETECTED:")
        for failure in failures:
            print(f"   ✖ {failure}")
        print("\nPR blocked from merging until quality regressions are resolved.")
        return 1

    print("✅ EVAL GATE PASSED — All quality metrics meet or exceed required thresholds.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentinel CI Evaluation Quality Gate")
    parser.add_argument("--set", type=int, default=100, help="Number of eval queries to run")
    parser.add_argument(
        "--faithfulness-threshold",
        type=float,
        default=None,
        help="Override faithfulness threshold",
    )
    parser.add_argument(
        "--recall-threshold",
        type=float,
        default=None,
        help="Override context recall threshold",
    )
    args = parser.parse_args()

    exit_code = run_ci_gate(
        n_queries=args.set,
        faithfulness_threshold=args.faithfulness_threshold,
        recall_threshold=args.recall_threshold,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
