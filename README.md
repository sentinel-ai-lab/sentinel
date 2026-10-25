<div align="center">

# 🛡️ Sentinel

### Agentic Research Copilot for Indian Equities

[![CI](https://github.com/sentinel-ai-lab/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/sentinel-ai-lab/sentinel/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent%20framework-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![pgvector](https://img.shields.io/badge/pgvector-hybrid%20search-336791?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **production-grade multi-agent LLM system** that ingests BSE/NSE filings and earnings transcripts to generate auditable equity research briefs — with a fine-tuned compliance agent that validates every claim before it reaches the user.

[Features](#features) · [Architecture](#architecture) · [Quick Start](#quick-start) · [Team](#team) · [Roadmap](#roadmap)

---

![Demo placeholder](docs/img/demo-placeholder.png)
> *Demo GIF will be added at Week 12*

</div>

---

## Features

- **Multi-agent orchestration** — LangGraph state machine coordinating Research and Compliance agents via MCP tools
- **Hybrid RAG retrieval** — BM25 + dense vectors (bge-small) + BGE reranker over 1,200+ BSE/NSE filings
- **Fine-tuned compliance layer** — Qwen-2.5-7B with QLoRA, achieving +18% F1 over GPT-4o-mini baseline
- **Full observability** — Langfuse tracing on every agent step, cost tracking, latency monitoring
- **Eval-gated CI** — RAGAS + LLM-as-judge regression suite runs on every PR; quality drops block merges
- **Streaming responses** — token-by-token output via Server-Sent Events

---

## Architecture

```
User Query
    │
    ▼
FastAPI + SSE ──────────────────────────────────────────────────────────┐
    │                                                                    │
    ▼                                                                    │
LangGraph Orchestrator                                                   │
    │                                                                    │
    ├──▶ Research Agent                                                  │
    │       │                                                            │
    │       ├──▶ MCP: filing_search   ──▶ Hybrid RAG (BM25 + pgvector)  │
    │       ├──▶ MCP: news_search     ──▶ NewsAPI                        │
    │       └──▶ MCP: get_price       ──▶ Yahoo Finance                  │
    │                                                                    │
    └──▶ Compliance Agent (fine-tuned Qwen-2.5-7B)                       │
            │                                                            │
            └──▶ Classify + rewrite + add citations                      │
                                                                         │
Synthesizer ──▶ Final brief + audit trace ──────────────────────────────┘
    │
    ▼
Langfuse (traces, costs, evals)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | LangGraph + MCP |
| LLM (dev) | Gemini 2.5 Flash |
| LLM (fine-tuned) | Qwen-2.5-7B + QLoRA (Unsloth) |
| Embeddings | bge-small-en-v1.5 |
| Reranker | BAAI/bge-reranker-base |
| Vector DB | pgvector (Postgres) |
| Lexical search | Postgres tsvector |
| API | FastAPI + Uvicorn |
| Cache | Redis |
| Observability | Langfuse (self-hosted) |
| Evals | RAGAS + custom harness |
| CI/CD | GitHub Actions |
| Containers | Docker + Docker Compose |

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### 1. Clone and install

```bash
git clone https://github.com/sentinel-ai-lab/sentinel.git
cd sentinel
uv sync
```

### 2. Configure environment

```bash
cp infra/.env.example infra/.env
# Edit infra/.env and add your API keys
```

### 3. Boot the local stack

```bash
make up       # starts Postgres, Redis, Langfuse
make ps       # verify all services are healthy
```

> **Windows Note**
>
> If `make` is unavailable on Windows, run:
>
> ```bash
> docker compose -f infra/docker-compose.dev.yml up -d
> docker ps
> ```
>
> To stop services:
>
> ```bash
> docker compose -f infra/docker-compose.dev.yml down
> ```

### Local Services

| Service | Endpoint |
|---|---|
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| Langfuse | http://localhost:3000 |

### Connection Strings (Local Development)

```env
DATABASE_URL=postgresql://sentinel:sentinel@localhost:5432/sentinel
REDIS_URL=redis://localhost:6379
```

> **Note:** Inside Docker containers, use:
>
> ```env
> DATABASE_URL=postgresql://sentinel:sentinel@postgres:5432/sentinel
> REDIS_URL=redis://redis:6379
> ```

> **Dev Note:** Langfuse is pinned to v2 in local development due to v3 ClickHouse dependency requirements.
```

### 4. Run ingestion (Phase 1 milestone)

```bash
python scripts/ingest.py TCS
# Downloads latest TCS annual report → extracts text → stores in Postgres
```

### 5. Run tests

```bash
make test
```

### 6. View Langfuse dashboard

Open [http://localhost:3000](http://localhost:3000)

---

## Project Structure

```
sentinel/
├── apps/
│   └── api/                  # FastAPI service (Phase 3)
├── packages/
│   ├── ingestion/            # Filing fetchers, PDF parsers, DB models
│   ├── retrieval/            # Hybrid search, reranker (Phase 2)
│   ├── agents/               # LangGraph orchestration, MCP tools (Phase 3)
│   ├── evals/                # RAGAS + custom eval harness (Phase 5)
│   └── common/               # Shared models, config, logging
├── infra/
│   ├── docker-compose.dev.yml
│   └── .env.example
├── scripts/
│   └── ingest.py             # CLI: python scripts/ingest.py TICKER
├── docs/
│   ├── adr/                  # Architecture Decision Records
│   │   ├── 001-overview.md
│   │   └── 002-agent-framework.md
│   └── data-sources.md       # BSE/NSE data source documentation
├── tests/
├── .github/
│   └── workflows/
│       └── ci.yml
├── pyproject.toml
├── Makefile
└── README.md
```

---

## Development Workflow

```bash
make up          # start all services
make down        # stop all services
make logs        # tail all service logs
make lint        # ruff check + format check
make typecheck   # mypy
make test        # pytest with coverage
make ingest T=TCS  # ingest a ticker
```

All PRs must:
1. Pass lint + typecheck + tests (CI enforced)
2. Have at least 1 reviewer approval
3. Target `main` branch only via PR — no direct pushes

---

## Roadmap

| Phase | Weeks | Status | Deliverables |
|---|---|---|---|
| 1. Foundation | 1–2 | ✅ Completed | Aiven pgvector, Redis, Docker, CI/CD pipeline |
| 2. RAG Core | 3–4 | ✅ Completed | FY25 filings, chunker, BGE embedding, hybrid search |
| 3. Agent Framework | 5–6 | ✅ Completed | LangGraph orchestrator, research node, FastAPI API |
| 4. Fine-Tuning | 7–9 | ✅ Completed | [Qwen-2.5-7B LoRA Adapter](https://huggingface.co/kishanaik5/sentinel-compliance-qwen25-7b-lora) (+18% F1 over GPT-4o-mini), [Benchmark Report](docs/benchmarks/compliance_benchmark.md) |
| 5. Evals + Observability | 10–11 | 🔄 Next Up | RAGAS regression suite, Langfuse traces, PR-gating |
| 6. Launch | 12 | ⏳ Planned | Demo UI, production deployment, release notes |

---

## Team

| Name | Role | GitHub |
|---|---|---|
| Kishan K | Lead / AI Platform Engineer | [@kishanaik5](https://github.com/kishanaik5) |
| TBD | Data & Retrieval Engineer | — |
| Aishwarya H R | DevOps & Infrastructure Engineer | [@18Aishwarya14](https://github.com/18Aishwarya14) |

---

## Publications

- [Performance Evaluation of DL Models for Predicting Alzheimer's Disease](https://ieeexplore.ieee.org) — IEEE Bangalore, 2024
- [Enhancing Predictive Maintenance with SHAP and LIME](https://arxiv.org) — ICAI–ARSSS, 2025

---

<div align="center">
Built with ☕ by <a href="https://kishan-k.pages.dev">Kishan K</a> and the Sentinel team · <a href="LICENSE">MIT License</a>
</div>
