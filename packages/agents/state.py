"""
Sentinel — Agent State

Shared TypedDict that flows through every LangGraph node.
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    query: str
    retrieved_chunks: list[dict]
    research_draft: str
    compliance_result: str
    final_brief: str
    citations: list[dict]
    trace_id: str
    error: str | None
    metadata: dict
