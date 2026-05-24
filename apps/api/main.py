"""
Sentinel API — FastAPI application

Endpoints:
  GET  /health  — liveness probe
  POST /chat    — invoke the LangGraph agent (streaming or JSON)

The sentinel_graph (research → compliance) is compiled at import time
so model loading happens once at server startup.
"""

from __future__ import annotations

import json
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from packages.agents.graph import sentinel_graph
from packages.agents.state import AgentState

app = FastAPI(title="Sentinel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response models ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    query: str
    stream: bool = False


# ── Routes ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sentinel-api"}


@app.post("/chat")
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
