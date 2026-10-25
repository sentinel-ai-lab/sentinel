"""
Sentinel — Compliance Node

Runs the research draft through the fine-tuned Qwen-2.5-7B LoRA compliance classifier
(kishanaik5/sentinel-compliance-qwen25-7b-lora).

Key responsibilities:
  1. Detects and rewrites any statements violating SEBI investment-advice guidelines.
  2. Ensures forward-looking projections include mandatory risk disclaimers.
  3. Validates citations and flags unsupported claims.
  4. Preserves verified, factual equity research text.
  5. Provides full audit trace for compliance review and Langfuse observability.
"""

from __future__ import annotations

from packages.agents.state import AgentState
from packages.finetuning.client import ComplianceModelClient

_client = ComplianceModelClient()


def compliance_node(state: AgentState) -> AgentState:
    """
    LangGraph node: compliance review via fine-tuned Qwen-2.5-7B LoRA model.

    Reads state["research_draft"] and state["citations"].
    Populates:
      - state["compliance_result"]: textual audit summary of findings
      - state["final_brief"]: audited, compliant final text
      - state["metadata"]["compliance"]: structured audit metrics
    """
    draft = state.get("research_draft") or ""

    if not draft.strip():
        return {
            **state,
            "compliance_result": "",
            "final_brief": "",
            "error": "research_draft was empty — cannot run compliance check",
        }

    citations = state.get("citations") or []
    report = _client.review_draft(draft, citations=citations)

    existing_metadata = dict(state.get("metadata") or {})
    existing_metadata["compliance"] = {
        "model_used": report.model_used,
        "summary": report.compliance_summary,
        "has_violations": report.has_violations,
        "needs_disclaimer": report.needs_disclaimer,
        "claims_evaluated": len(report.audit_trace),
        "audit_trace": [
            {
                "label": c.label,
                "explanation": c.explanation,
                "latency_ms": round(c.latency_ms, 2),
            }
            for c in report.audit_trace
        ],
    }

    return {
        **state,
        "compliance_result": report.compliance_summary,
        "final_brief": report.audited_text,
        "metadata": existing_metadata,
    }
