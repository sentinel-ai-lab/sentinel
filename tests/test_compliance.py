"""
Tests for Sentinel Compliance Model Client, Node, and Parsing
"""

from __future__ import annotations

from packages.agents.nodes.compliance import compliance_node
from packages.agents.state import AgentState
from packages.finetuning.benchmark import calculate_classification_metrics
from packages.finetuning.client import (
    ComplianceModelClient,
    parse_compliance_output,
)


def test_parse_compliance_output_compliant():
    raw = "COMPLIANT: Statement contains verified Q2 financial results."
    res = parse_compliance_output(raw, original_input="TCS revenue grew 4% YoY.")
    assert res.label == "COMPLIANT"
    assert "verified" in res.explanation
    assert res.rewrite == "TCS revenue grew 4% YoY."


def test_parse_compliance_output_advice_violation():
    raw = (
        "ADVICE_VIOLATION: Direct recommendation to buy shares. "
        "Rewrite: Investors may review TCS quarterly earnings disclosures."
    )
    res = parse_compliance_output(raw, original_input="Buy TCS shares immediately for 20% gain.")
    assert res.label == "ADVICE_VIOLATION"
    assert "Direct recommendation" in res.explanation
    assert res.rewrite == "Investors may review TCS quarterly earnings disclosures."


def test_parse_compliance_output_needs_disclaimer():
    raw = "NEEDS_DISCLAIMER: Statement includes forward-looking forecast."
    res = parse_compliance_output(raw, original_input="Infosys expects margin expansion next year.")
    assert res.label == "NEEDS_DISCLAIMER"


def test_compliance_review_draft_with_violations():
    client = ComplianceModelClient()
    draft = (
        "Infosys reported steady Q3 revenue. "
        "Investors should buy Infosys immediately for a guaranteed multibagger return."
    )
    report = client.review_draft(draft, citations=[{"company": "INFY"}])
    assert report.has_violations is True
    assert (
        "buy" not in report.audited_text.lower() or "guaranteed" not in report.audited_text.lower()
    )
    assert report.claims_evaluated >= 1 or len(report.audit_trace) >= 1


def test_compliance_node_execution():
    state: AgentState = {
        "query": "What is the financial outlook for TCS?",
        "retrieved_chunks": [],
        "research_draft": "TCS generated strong operating cash flows in FY25. Buy TCS stock now.",
        "compliance_result": "",
        "final_brief": "",
        "citations": [{"company": "TCS", "page": 12}],
        "trace_id": "test-trace-123",
        "error": None,
        "metadata": {},
    }

    result_state = compliance_node(state)
    assert result_state["final_brief"] != ""
    assert result_state["compliance_result"] != ""
    assert "compliance" in result_state["metadata"]
    assert result_state["metadata"]["compliance"]["claims_evaluated"] >= 1


def test_compliance_node_empty_draft():
    state: AgentState = {
        "query": "Test query",
        "retrieved_chunks": [],
        "research_draft": "",
        "compliance_result": "",
        "final_brief": "",
        "citations": [],
        "trace_id": "test-trace-empty",
        "error": None,
        "metadata": {},
    }

    result_state = compliance_node(state)
    assert result_state["error"] is not None
    assert "empty" in result_state["error"]


def test_calculate_classification_metrics():
    y_true = ["COMPLIANT", "ADVICE_VIOLATION", "NEEDS_DISCLAIMER", "UNSUPPORTED"]
    y_pred = ["COMPLIANT", "ADVICE_VIOLATION", "NEEDS_DISCLAIMER", "COMPLIANT"]

    acc, mp, mr, mf1, per_class, conf = calculate_classification_metrics(y_true, y_pred)
    assert acc == 0.75
    assert mp > 0.0
    assert mr > 0.0
    assert 0.0 < mf1 < 1.0
    assert per_class["COMPLIANT"].precision == 0.5  # 1 TP, 1 FP from UNSUPPORTED
    assert per_class["ADVICE_VIOLATION"].f1 == 1.0
    assert conf["COMPLIANT"]["COMPLIANT"] == 1
