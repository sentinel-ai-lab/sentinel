# ADR-001: Architecture Overview

**Status:** Accepted
**Date:** April 2026
**Authors:** Kishan K

---

## Context

We are building Sentinel — a production-grade multi-agent LLM system that answers natural-language questions about Indian-listed equities using grounded retrieval over BSE/NSE filings, with a compliance layer that validates every response before it reaches the user.

The system must be:
- **Auditable** — every claim traceable to a source document
- **Production-grade** — observable, testable, CI-gated
- **Cost-efficient** — dev work on free-tier LLMs; fine-tuned small model for compliance
- **Extensible** — new agents and data sources can be added without re-architecting

---

## Decision

We adopt a **layered, agent-first architecture** with the following boundaries:

```
┌─────────────────────────────────────────────────────────┐
│                     Client Layer                        │
│              FastAPI + SSE streaming                    │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                 Orchestration Layer                     │
│            LangGraph state machine                      │
│     (planner → research → compliance → synthesize)      │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
┌──────────▼──────────┐  ┌────────────▼──────────────────┐
│    Research Agent   │  │      Compliance Agent          │
│  (Gemini Flash /    │  │  (fine-tuned Qwen-2.5-7B)     │
│   GPT-4o-mini)      │  │                               │
│                     │  │  classifies: compliant /      │
│  MCP tools:         │  │  needs-disclaimer /           │
│  - filing_search    │  │  unsupported-claim /          │
│  - news_search      │  │  advice-violation             │
│  - get_price        │  └────────────────────────────────┘
└──────────┬──────────┘
           │
┌──────────▼──────────────────────────────────────────────┐
│                   Retrieval Layer                       │
│    BM25 (tsvector) + Dense (pgvector) + BGE reranker    │
│           Corpus: 1,200+ BSE/NSE filings                │
└──────────┬──────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────┐
│                     Data Layer                          │
│         PostgreSQL + pgvector  |  Redis                 │
│    Companies, Filings, Chunks, Embeddings, Cache        │
└─────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────┐
│                 Observability Layer                     │
│         Langfuse — traces, costs, evals, alerts         │
└─────────────────────────────────────────────────────────┘
```

---

## Goals

- **G1:** Answer equity research questions with grounded citations (no hallucinated numbers)
- **G2:** Every response passes compliance classification before delivery
- **G3:** All agent steps are traced and observable in Langfuse
- **G4:** CI pipeline enforces quality — PRs blocked if RAGAS faithfulness drops >5%
- **G5:** Fine-tuned compliance model reduces per-query cost by >8x vs GPT-4o

## Non-Goals

- Real-time price streaming (we use cached daily prices)
- Portfolio management or trade execution
- Multi-language output (English only in v1)
- Support for global equities (India-listed only in v1)

---

## Alternatives Considered

| Option | Reason rejected |
|---|---|
| Single monolithic LLM call | No auditability, compliance mixed with research |
| Separate microservices per agent | Overkill for 2-agent system; adds network latency |
| ChromaDB / Weaviate for vectors | pgvector eliminates a separate vector DB service |
| Pinecone / Qdrant | External paid service; pgvector is free and sufficient |

---

## Consequences

**Positive:**
- Clear separation of concerns — research and compliance are independently testable
- pgvector inside Postgres means one DB for structured data + vectors
- LangGraph gives us explicit state management and easy debugging

**Negative:**
- Two LLM calls per query (research + compliance) increases latency
- Fine-tuning Qwen requires GPU rental (~₹1,200) and curation effort
- Langfuse self-hosting adds initial setup complexity

---

## Review

This ADR will be revisited if:
- Latency consistently exceeds 4s p95 (may need to merge agents)
- Corpus grows beyond 10,000 documents (may need dedicated vector DB)
- Team grows beyond 3 (may need microservices boundary)
