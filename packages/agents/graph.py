"""
Sentinel — LangGraph Agent Graph

Flow:  research_node → compliance_node → END

research_node:   hybrid retrieval (BM25 + dense RRF) → rerank → Gemini synthesis
compliance_node: Gemini compliance review → final_brief
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from packages.agents.nodes.compliance import compliance_node
from packages.agents.nodes.research import research_node
from packages.agents.state import AgentState

graph = StateGraph(AgentState)

graph.add_node("research", research_node)
graph.add_node("compliance", compliance_node)

graph.set_entry_point("research")
graph.add_edge("research", "compliance")
graph.add_edge("compliance", END)

sentinel_graph = graph.compile()
