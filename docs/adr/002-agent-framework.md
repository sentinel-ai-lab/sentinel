# ADR-002: Agent Framework — LangGraph

**Status:** Accepted
**Date:** April 2026
**Authors:** Kishan K

---

## Context

Sentinel requires an agent orchestration framework to coordinate multiple LLM-powered agents (Research, Compliance), manage state across agent steps, handle retries and error recovery, and support streaming output to the client.

We evaluated four options.

---

## Options Evaluated

### Option 1: LangGraph ✅ (Selected)

LangGraph models agent workflows as **directed state graphs** — nodes are agent functions, edges are transitions, and a shared `State` TypedDict holds all data across steps.

**Pros:**
- Explicit, debuggable control flow — you can see exactly what state looks like at each node
- First-class streaming support (token streaming + step streaming)
- Built-in retry logic and interrupt/resume for human-in-the-loop
- Growing adoption — becoming the industry standard for production agents
- Strong integration with Langfuse for tracing

**Cons:**
- Steeper learning curve vs simpler tools
- Verbose for trivial workflows (not a concern here)

---

### Option 2: CrewAI

Role-based multi-agent framework where agents have personas and tasks are delegated sequentially.

**Pros:** Quick to get started, intuitive role model

**Cons:**
- Less control over exact execution flow
- Harder to debug intermediate state
- Streaming support is limited
- Does not model our Research → Compliance flow as naturally as a graph

**Rejected because:** We need explicit control over the handoff between Research and Compliance agents. CrewAI's role-based model obscures this.

---

### Option 3: AutoGen (Microsoft)

Conversation-based multi-agent framework where agents communicate via messages.

**Pros:** Flexible, strong for multi-agent debate patterns

**Cons:**
- Conversation model is heavier than needed for a 2-agent pipeline
- Less native streaming support
- More complex to integrate with Langfuse

**Rejected because:** Conversation overhead adds latency for a sequential pipeline.

---

### Option 4: Hand-rolled orchestration

Write a simple Python function that calls Research agent, then Compliance agent.

**Pros:** Zero dependencies, maximum control

**Cons:**
- No built-in retry logic, state management, or streaming
- Would need to rebuild what LangGraph provides
- No graph visualization for debugging

**Rejected because:** We'd be reinventing LangGraph. Not worth it for a 12-week project.

---

## Decision

**Use LangGraph** for the following reasons:

1. **Explicit state** — `AgentState` TypedDict is serializable, inspectable, and testable. We can write unit tests for individual nodes.
2. **Streaming** — LangGraph's `.astream()` integrates cleanly with FastAPI's SSE endpoint.
3. **MCP compatibility** — LangGraph nodes can wrap MCP tool servers directly.
4. **Langfuse tracing** — LangGraph + Langfuse integration is well-documented.
5. **Resume signal** — LangGraph is on the fastest-growing tools list for 2026 AI job postings. This is the right thing to learn.

---

## Implementation Plan

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    query: str
    research_draft: str
    citations: list[dict]
    compliance_result: str
    final_brief: str
    trace_id: str

# Nodes
def research_node(state: AgentState) -> AgentState: ...
def compliance_node(state: AgentState) -> AgentState: ...
def synthesize_node(state: AgentState) -> AgentState: ...

# Graph
graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("compliance", compliance_node)
graph.add_node("synthesize", synthesize_node)

graph.set_entry_point("research")
graph.add_edge("research", "compliance")
graph.add_edge("compliance", "synthesize")
graph.add_edge("synthesize", END)

sentinel_graph = graph.compile()
```

---

## Consequences

**Positive:**
- Testable nodes in isolation (unit tests per agent)
- Retry logic configurable per edge
- State is serializable — can checkpoint and resume

**Negative:**
- Adds `langgraph` + `langchain-core` as dependencies
- Team must learn LangGraph's state graph model (estimated 2–3 hrs onboarding)

---

## Review

Revisit this decision if:
- We need dynamic agent spawning (consider AutoGen at that point)
- LangGraph introduces a breaking change in a major version
