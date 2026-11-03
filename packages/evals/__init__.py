"""
Sentinel — Evals and Observability Package (Phase 5)

Contains:
  - citation_checker: Validates corporate citation accuracy, page existence, and claim grounding.
  - llm_judge: 5-dimension qualitative judge for financial research briefs.
  - ragas_eval: Faithfulness, relevancy, and context recall evaluation engine.
  - ci_gate: PR-blocking regression gate enforcing quality thresholds.
  - langfuse_tracer: Observability and evaluation metrics export to Langfuse.
"""

from __future__ import annotations

from packages.evals.citation_checker import CitationChecker, CitationVerificationResult
from packages.evals.llm_judge import LLMJudge, LLMJudgeResult
from packages.evals.ragas_eval import RAGEvalResult, run_ragas_eval

__all__ = [
    "CitationChecker",
    "CitationVerificationResult",
    "LLMJudge",
    "LLMJudgeResult",
    "RAGEvalResult",
    "run_ragas_eval",
]
