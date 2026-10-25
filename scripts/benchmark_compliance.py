"""
Sentinel — Benchmark Runner CLI

Usage:
    python scripts/benchmark_compliance.py
    python scripts/benchmark_compliance.py --samples 50
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.finetuning.benchmark import ComplianceBenchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Sentinel Compliance Model Benchmarks")
    parser.add_argument("--samples", type=int, default=None, help="Limit number of test samples")
    args = parser.parse_args()

    print("🛡️  Running Sentinel Compliance Benchmark...")
    benchmark = ComplianceBenchmark()
    print(f"Loaded {len(benchmark.examples)} test examples from test.jsonl")

    results = benchmark.run_benchmark(include_baselines=True, max_samples=args.samples)
    benchmark.save_reports(results)

    ft = results["qwen_finetuned"]
    gpt = results["gpt4o_mini"]
    base = results["qwen_base"]

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 60)
    print(f"{'Model':<35} | {'Macro F1':<8} | {'p50 (ms)':<8} | {'Cost/1k'}")
    ft_cost = ft.cost_per_query_usd * 1000
    gpt_cost = gpt.cost_per_query_usd * 1000
    base_cost = base.cost_per_query_usd * 1000

    def _fmt(name: str, f1: float, p50: float, cost: float) -> str:
        short_name = name[:32]
        return f"{short_name:<32} | {f1:<8.3f} | {p50:<8.0f} | ${cost:.2f}"

    print(_fmt(ft.model_name, ft.macro_f1, ft.p50_latency_ms, ft_cost))
    print(_fmt(gpt.model_name, gpt.macro_f1, gpt.p50_latency_ms, gpt_cost))
    print(_fmt(base.model_name, base.macro_f1, base.p50_latency_ms, base_cost))
    print("=" * 60)
    print("\nSaved benchmark reports to:")
    print("  - packages/finetuning/benchmark_results.json")
    print("  - docs/benchmarks/compliance_benchmark.md")


if __name__ == "__main__":
    main()
