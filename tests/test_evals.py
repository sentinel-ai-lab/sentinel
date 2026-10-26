"""
Sentinel — Tests for Evals & Observability Package (Phase 5)

Covers:
  - CitationChecker (valid ticker, page boundaries, claim grounding, numerical detection)
  - LLMJudge (empty responses, deterministic scoring, advice violation penalties)
  - RAGAS Evaluator (hermetic evaluation, metric extraction, to_dict serialization)
  - CI Quality Gate (passing thresholds, blocking regressions)
  - Drift Detector (baseline comparisons, regression alert triggers)
  - LangfuseEvaluationsExporter (offline fallback, metric dispatch)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from packages.evals.ci_gate import run_ci_gate
from packages.evals.citation_checker import CitationChecker
from packages.evals.langfuse_tracer import LangfuseEvaluationsExporter
from packages.evals.llm_judge import LLMJudge
from packages.evals.ragas_eval import (
    _extract_key_tokens,
    evaluate_sample_hermetic,
    run_ragas_eval,
)
from scripts.drift_check import run_drift_check

# ---------------------------------------------------------------------------
# 1. CitationChecker Tests
# ---------------------------------------------------------------------------


def test_citation_checker_valid_citations():
    checker = CitationChecker(max_pages=500)
    brief = "TCS reported consolidated revenue of ₹255,324 crore [TCS, FY2025, p.17]."
    citations = [
        {
            "company": "TCS",
            "page": 17,
            "text_preview": "consolidated revenue of ₹255,324 crore",
        }
    ]
    chunks = [{"text": "In FY2025, TCS achieved consolidated revenue of ₹255,324 crore."}]

    result = checker.verify_citations(final_brief=brief, citations=citations, chunks=chunks)
    assert result.is_valid is True
    assert result.citation_accuracy == 1.0
    assert result.total_citations == 1
    assert result.valid_citations == 1
    assert result.hallucinated_citations == 0
    assert len(result.issues) == 0


def test_citation_checker_unknown_ticker():
    checker = CitationChecker()
    brief = "UnknownCo reported Q3 profits."
    citations = [{"company": "UNKNOWN_TICKER_XYZ", "page": 10}]

    result = checker.verify_citations(final_brief=brief, citations=citations)
    assert result.is_valid is False
    assert result.citation_accuracy == 0.0
    assert result.hallucinated_citations == 1
    assert "Unknown or unverified company ticker" in result.issues[0]


def test_citation_checker_out_of_bounds_page():
    checker = CitationChecker(max_pages=400)
    brief = "Infosys expanded digital services."
    citations = [{"company": "INFY", "page": 850}]

    result = checker.verify_citations(final_brief=brief, citations=citations)
    assert result.is_valid is False
    assert result.citation_accuracy == 0.0
    assert result.hallucinated_citations == 1
    assert "Out of range page number" in result.issues[0]


def test_citation_checker_numerical_claim_without_citations():
    checker = CitationChecker()
    brief = "HDFC Bank net profit grew 33.5% YoY to ₹16,373 crore in Q3 FY24."
    citations: list[dict] = []

    result = checker.verify_citations(final_brief=brief, citations=citations)
    assert result.is_valid is False
    assert result.citation_accuracy == 0.0
    assert "zero supporting citations" in result.issues[0]


def test_citation_checker_non_numerical_brief_without_citations():
    checker = CitationChecker()
    brief = "The management discussed long term governance policies and employee training."
    citations: list[dict] = []

    result = checker.verify_citations(final_brief=brief, citations=citations)
    assert result.is_valid is True
    assert result.citation_accuracy == 1.0
    assert len(result.issues) == 0


# ---------------------------------------------------------------------------
# 2. LLMJudge Tests
# ---------------------------------------------------------------------------


def test_llm_judge_empty_response():
    judge = LLMJudge(backend="deterministic")
    res = judge.evaluate(question="What was TCS revenue?", response="")
    assert res.composite_score == 1.0
    assert res.accuracy == 1
    assert res.judge_model == "fallback"


def test_llm_judge_deterministic_compliant_response():
    judge = LLMJudge(backend="deterministic")
    question = "What is the capital expenditure of Reliance?"
    response = (
        "Reliance Industries capex stood at ₹131,769 crore in FY2025. "
        "Disclaimer: This summary is for informational purposes only. [RELIANCE, FY2025, p.44]"
    )
    res = judge.evaluate(question=question, response=response)
    assert res.compliance == 5
    assert res.citation_quality == 5
    assert res.composite_score >= 4.0
    assert res.judge_model == "deterministic-judge"


def test_llm_judge_deterministic_advice_violation_penalty():
    judge = LLMJudge(backend="deterministic")
    question = "Should I invest in TCS?"
    response = "Buy now immediately for massive gains! Target price ₹5000."
    res = judge.evaluate(question=question, response=response)
    assert res.compliance == 1
    assert res.composite_score < 4.0


# ---------------------------------------------------------------------------
# 3. RAGAS Evaluator Tests
# ---------------------------------------------------------------------------


def test_extract_key_tokens():
    tokens = _extract_key_tokens("TCS reported ₹255,324 crore in FY2025!")
    assert "tcs" in tokens
    assert "reported" in tokens
    assert "255" in tokens or "324" in tokens
    assert "fy2025" in tokens


def test_evaluate_sample_hermetic_empty_answer():
    metric = evaluate_sample_hermetic(
        question="What is the net profit?",
        answer="",
        contexts=["Some context"],
        ground_truth="Net profit was ₹100 crore",
    )
    assert metric.faithfulness == 0.0
    assert metric.answer_relevancy == 0.0


def test_evaluate_sample_hermetic_perfect_grounding():
    gt = "TCS reported revenue of ₹255,324 crore in FY2025."
    metric = evaluate_sample_hermetic(
        question="What was TCS revenue in FY2025?",
        answer=gt,
        contexts=[gt],
        ground_truth=gt,
    )
    assert metric.faithfulness == 1.0
    assert metric.context_recall == 1.0
    assert metric.context_precision == 1.0
    assert metric.answer_relevancy >= 0.85


def test_run_ragas_eval_batch():
    qa_pairs = [
        {
            "query": "What was TCS revenue in FY2025?",
            "expected_answer": "TCS revenue was ₹255,324 crore in FY2025.",
            "answer": "TCS revenue was ₹255,324 crore in FY2025.",
            "contexts": ["TCS revenue was ₹255,324 crore in FY2025."],
        },
        {
            "query": "What was Infosys revenue in FY2025?",
            "expected_answer": "Infosys revenue was ₹153,670 crore in FY2025.",
            "answer": "Infosys revenue was ₹153,670 crore in FY2025.",
            "contexts": ["Infosys revenue was ₹153,670 crore in FY2025."],
        },
    ]

    res = run_ragas_eval(qa_pairs)
    assert res.sample_count == 2
    assert res.faithfulness == 1.0
    assert res.context_recall == 1.0
    d = res.to_dict()
    assert "faithfulness" in d
    assert "context_recall" in d
    assert "answer_relevancy" in d
    assert "context_precision" in d


# ---------------------------------------------------------------------------
# 4. CI Quality Gate Tests
# ---------------------------------------------------------------------------


def test_ci_gate_passing():
    code = run_ci_gate(
        n_queries=10,
        faithfulness_threshold=0.75,
        recall_threshold=0.80,
    )
    assert code == 0


def test_ci_gate_failing_threshold():
    # An unattainable threshold of 1.05 should trigger a CI gate failure (exit code 1)
    code = run_ci_gate(
        n_queries=5,
        faithfulness_threshold=1.05,
    )
    assert code == 1


# ---------------------------------------------------------------------------
# 5. Drift Check Runner Tests
# ---------------------------------------------------------------------------


def test_drift_check_passing(tmp_path):
    report_file = tmp_path / "drift_report.json"
    code = run_drift_check(
        sample_limit=10,
        tolerance=0.10,
        output_path=str(report_file),
    )
    assert code == 0
    assert report_file.exists()
    with open(report_file) as f:
        data = json.load(f)
    assert "metrics" in data
    assert "citation_verification" in data


def test_drift_check_regression_trigger(tmp_path):
    # Create an artificial baseline where expected faithfulness is 1.20
    fake_baseline = tmp_path / "fake_baseline.json"
    fake_baseline.write_text(
        json.dumps(
            {
                "ragas_metrics": {
                    "faithfulness": 1.20,
                    "context_recall": 1.20,
                }
            }
        )
    )

    code = run_drift_check(
        baseline_path=str(fake_baseline),
        sample_limit=5,
        tolerance=0.02,
    )
    # Must alert with exit code 1
    assert code == 1


# ---------------------------------------------------------------------------
# 6. Langfuse Observability Exporter Tests
# ---------------------------------------------------------------------------


def test_langfuse_exporter_offline():
    exporter = LangfuseEvaluationsExporter()
    # When keys are absent, records return False safely
    success = exporter.record_eval_scores(
        trace_id="test-offline-trace",
        rag_scores={"faithfulness": 0.95},
    )
    assert success is False


def test_langfuse_exporter_with_mock_client():
    exporter = LangfuseEvaluationsExporter()
    mock_client = MagicMock()
    exporter._client = mock_client

    success = exporter.record_eval_scores(
        trace_id="trace-123",
        rag_scores={"faithfulness": 0.92, "context_recall": 0.88},
        judge_scores={"accuracy": 5, "compliance": 5},
        latency_ms=120.5,
    )
    assert success is True
    # Verify score was called for each metric
    assert mock_client.score.call_count == 5
