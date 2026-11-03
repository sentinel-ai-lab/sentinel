"""
Sentinel API — FastAPI application

Endpoints:
  GET  /health                  — liveness probe
  GET  /api/info                — compliance model metadata, benchmarks, and taxonomy
  POST /api/compliance/classify — classify single claim with fine-tuned Qwen-2.5-7B LoRA
  POST /api/compliance/review   — audit full draft with sentence breakdown & rewrites
  POST /chat or /api/chat       — invoke LangGraph multi-agent research copilot
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from packages.agents.graph import sentinel_graph
from packages.agents.state import AgentState
from packages.finetuning.client import ComplianceModelClient

app = FastAPI(title="Sentinel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

compliance_client = ComplianceModelClient()


# ── Request / response models ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    query: str
    stream: bool = False


class ClaimClassifyRequest(BaseModel):
    claim: str


class DraftReviewRequest(BaseModel):
    draft: str
    citations: list[dict[str, Any]] = []


# ── Routes ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sentinel-api"}


@app.get("/api/info")
def model_info() -> dict[str, Any]:
    return {
        "model_id": "kishanaik5/sentinel-compliance-qwen25-7b-lora",
        "huggingface_url": ("https://huggingface.co/kishanaik5/sentinel-compliance-qwen25-7b-lora"),
        "dataset_url": (
            "https://www.kaggle.com/datasets/kishanknaik/finetuning-banking-fy-25-26-dataset"
        ),
        "metrics": {
            "macro_f1": 0.9963,
            "accuracy": 0.9963,
            "latency_p50_ms": 240,
            "cost_per_query_usd": 0.0003,
        },
        "taxonomy": [
            {
                "label": "COMPLIANT",
                "description": "Factual, verified statements with appropriate citations.",
                "color": "#10b981",
            },
            {
                "label": "NEEDS_DISCLAIMER",
                "description": (
                    "Forward-looking statements requiring mandatory statutory risk disclaimers."
                ),
                "color": "#f59e0b",
            },
            {
                "label": "UNSUPPORTED",
                "description": "Assertions lacking factual backing in regulatory disclosures.",
                "color": "#8b5cf6",
            },
            {
                "label": "ADVICE_VIOLATION",
                "description": (
                    "Direct investment advice, buy/sell recommendations, or price targets."
                ),
                "color": "#ef4444",
            },
        ],
    }


@app.post("/api/compliance/classify")
def classify_claim(request: ClaimClassifyRequest) -> dict[str, Any]:
    res = compliance_client.classify_claim(request.claim)
    return {
        "label": res.label,
        "explanation": res.explanation,
        "rewrite": res.rewrite,
        "raw_output": res.raw_output,
        "latency_ms": round(res.latency_ms, 2),
        "model_used": res.model_used,
    }


@app.post("/api/compliance/review")
def review_draft(request: DraftReviewRequest) -> dict[str, Any]:
    report = compliance_client.review_draft(request.draft, citations=request.citations)
    return {
        "audited_text": report.audited_text,
        "compliance_summary": report.compliance_summary,
        "has_violations": report.has_violations,
        "needs_disclaimer": report.needs_disclaimer,
        "claims_evaluated": report.claims_evaluated,
        "model_used": report.model_used,
        "audit_trace": [
            {
                "label": c.label,
                "explanation": c.explanation,
                "rewrite": c.rewrite,
                "latency_ms": round(c.latency_ms, 2),
                "model_used": c.model_used,
            }
            for c in report.audit_trace
        ],
    }


@app.post("/chat")
@app.post("/api/chat")
async def chat(request: ChatRequest):
    initial_state: AgentState = {
        "query": request.query,
        "retrieved_chunks": [],
        "research_draft": "",
        "compliance_result": "",
        "final_brief": "",
        "citations": [],
        "trace_id": str(uuid.uuid4()),
        "error": None,
        "metadata": {},
    }

    if request.stream:

        async def event_stream():
            result = sentinel_graph.invoke(initial_state)
            answer = result.get("final_brief", "")
            # Stream word-by-word
            for word in answer.split():
                yield f"data: {word} \n\n"
            # Append citations as a final event
            citations = result.get("citations", [])
            yield f"data: [CITATIONS]{json.dumps(citations)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Non-streaming path
    result = sentinel_graph.invoke(initial_state)
    return {
        "answer": result.get("final_brief", ""),
        "citations": result.get("citations", []),
        "trace_id": initial_state["trace_id"],
    }
