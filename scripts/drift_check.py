"""
Sentinel — Evaluation Drift Detection Runner

Compares current evaluation metrics against the Phase 5 benchmark baseline
(docs/benchmarks/phase5_baseline.json). If core metrics (e.g. faithfulness or
context recall) experience negative drift exceeding the tolerance (default: -0.05),
the script flags an alert and exits with code 1 to guard against regression.

Usage:
    python scripts/drift_check.py
    python scripts/drift_check.py --samples 50 --tolerance 0.05
    python scripts/drift_check.py --output docs/benchmarks/drift_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.evals.citation_checker import CitationChecker
from packages.evals.ragas_eval import run_ragas_eval


def load_baseline(baseline_path: str) -> dict[str, Any]:
    p = Path(baseline_path)
    if not p.exists():
        raise FileNotFoundError(f"Baseline file not found at {baseline_path}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_eval_data(eval_path: str) -> list[dict[str, Any]]:
    p = Path(eval_path)
    if not p.exists():
        raise FileNotFoundError(f"Eval dataset not found at {eval_path}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def run_drift_check(
    baseline_path: str = "docs/benchmarks/phase5_baseline.json",
    eval_dataset_path: str = "packages/evals/data/eval_qa_pairs.json",
    sample_limit: int | None = None,
    tolerance: float = 0.05,
    output_path: str | None = None,
) -> int:
    """Runs drift check against baseline metrics and returns exit code."""
    print("=" * 68)
    print("📈 SENTINEL — EVALUATION DRIFT MONITOR")
    print("=" * 68)

    baseline = load_baseline(baseline_path)
    base_rag = baseline.get("ragas_metrics", {})
    qa_pairs = load_eval_data(eval_dataset_path)

    if sample_limit:
        qa_pairs = qa_pairs[:sample_limit]

    print(f"Loaded baseline from: {baseline_path}")
    print(f"Evaluating {len(qa_pairs)} queries against baseline targets...")

    eval_result = run_ragas_eval(qa_pairs)
    current_rag = eval_result.to_dict()

    # Citation check audit on sample
    checker = CitationChecker()
    citations_sample: list[dict[str, Any]] = []
    for qa in qa_pairs:
        citations_sample.extend(qa.get("expected_citations", []))

    cit_result = checker.verify_citations(
        final_brief=" ".join(qa.get("expected_answer", "") for qa in qa_pairs[:5]),
        citations=citations_sample,
    )

    print("\n" + "=" * 68)
    print(f"{'Metric':<22} | {'Baseline':<10} | {'Current':<10} | {'Delta':<10} | {'Status'}")
    print("-" * 68)

    drift_failures: list[str] = []
    report_data: dict[str, Any] = {
        "samples_evaluated": len(qa_pairs),
        "tolerance": tolerance,
        "metrics": {},
        "citation_verification": {
            "total_citations": cit_result.total_citations,
            "accuracy": cit_result.citation_accuracy,
            "valid": cit_result.is_valid,
        },
    }

    critical_metrics = {"faithfulness", "context_recall"}

    for metric, base_val in base_rag.items():
        curr_val = current_rag.get(metric, 0.0)
        delta = curr_val - base_val

        status = "✅ STABLE"
        # Negative drift exceeds allowed drop
        if delta < -tolerance:
            status = "❌ REGRESSED"
            if metric in critical_metrics:
                drift_failures.append(
                    f"{metric}: dropped {abs(delta):.3f} "
                    f"(baseline: {base_val:.3f}, current: {curr_val:.3f})"
                )
        elif delta > 0.02:
            status = "🚀 IMPROVED"

        report_data["metrics"][metric] = {
            "baseline": base_val,
            "current": round(curr_val, 4),
            "delta": round(delta, 4),
            "status": status,
        }

        sign = "+" if delta >= 0 else ""
        delta_str = f"{sign}{delta:.3f}"
        print(f"{metric:<22} | {base_val:<10.3f} | {curr_val:<10.3f} | {delta_str:<10} | {status}")

    print("=" * 68)
    print(
        f"Citation Accuracy: {cit_result.citation_accuracy * 100:.1f}% "
        f"({cit_result.valid_citations}/{cit_result.total_citations} valid citations)"
    )

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"\nDrift report saved to: {output_path}")

    if drift_failures:
        print("\n❌ CRITICAL EVALUATION DRIFT DETECTED:")
        for failure in drift_failures:
            print(f"   ✖ {failure}")
        print(f"\nMetric regression exceeded maximum tolerance (-{tolerance:.2f}).")
        return 1

    print("\n✅ NO UNEXPECTED DRIFT — All core evaluation metrics remain within tolerance.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentinel Evaluation Drift Detector")
    parser.add_argument(
        "--baseline",
        type=str,
        default="docs/benchmarks/phase5_baseline.json",
        help="Path to baseline benchmark JSON",
    )
    parser.add_argument(
        "--eval-set",
        type=str,
        default="packages/evals/data/eval_qa_pairs.json",
        help="Path to evaluation QA dataset",
    )
    parser.add_argument("--samples", type=int, default=None, help="Limit number of queries to test")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Maximum allowed negative drift before alerting (default: 0.05)",
    )
    parser.add_argument("--output", type=str, default=None, help="Save drift report JSON to path")
    args = parser.parse_args()

    exit_code = run_drift_check(
        baseline_path=args.baseline,
        eval_dataset_path=args.eval_set,
        sample_limit=args.samples,
        tolerance=args.tolerance,
        output_path=args.output,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
