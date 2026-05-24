"""
Sentinel — Research Node

Retrieves relevant chunks via HybridSearcher → reranks with CrossEncoder
→ synthesises an answer with inline citations using Gemini 1.5 Flash.

Uses google.genai (new SDK) — google.generativeai is deprecated.
"""

from __future__ import annotations

import os

import google.genai as genai
from dotenv import load_dotenv

from packages.agents.state import AgentState
from packages.retrieval.reranker import Reranker
from packages.retrieval.searcher import HybridSearcher

load_dotenv("infra/.env")


def research_node(state: AgentState) -> AgentState:
    """
    LangGraph node: retrieval + Gemini synthesis.

    Retrieval pipeline:
      1. HybridSearcher.hybrid_search(query, top_k=20) — BM25 + dense RRF
      2. Reranker.rerank(query, results, top_n=5)   — bge-reranker-base

    Generation:
      Gemini 1.5 Flash with strict context-only prompt.
    """
    searcher = HybridSearcher()
    reranker = Reranker()

    # ── Retrieve ──────────────────────────────────────────────────────────
    raw_results = searcher.hybrid_search(state["query"], top_k=20)
    top_chunks = reranker.rerank(state["query"], raw_results, top_n=5)

    # ── Build context + citations ─────────────────────────────────────────
    context_parts: list[str] = []
    citations: list[dict] = []

    for i, chunk in enumerate(top_chunks):
        ticker = chunk.get("company_ticker", "Unknown")
        page = chunk.get("page_number", "?")
        fy = chunk.get("fiscal_year", "FY2025")
        context_parts.append(
            f"[{ticker}, {fy}, p.{page}]:\n{chunk['text']}"
        )
        citations.append(
            {
                "index": i + 1,
                "company": ticker,
                "page": page,
                "fiscal_year": fy,
                "text_preview": chunk["text"][:120],
            }
        )

    context = "\n\n".join(context_parts)

    # ── Generate with Gemini ──────────────────────────────────────────────
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""You are a financial research analyst for Indian equities.
Answer using ONLY the provided context from annual reports.
Cite every claim with [Company, p.X].

Context:
{context}

Question: {state["query"]}

Provide a clear, structured answer with inline citations."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return {
        **state,
        "research_draft": response.text,
        "retrieved_chunks": top_chunks,
        "citations": citations,
    }
