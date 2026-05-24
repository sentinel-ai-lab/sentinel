"""
Sentinel — Hybrid Retrieval (BM25 + Dense + RRF)

Uses the denormalized sentinel.chunks schema:
  - chunks.company / fiscal_year are stored directly (no joins needed)
  - BM25 uses to_tsvector() inline (no precomputed ts_vector column)
  - Dense search uses sentinel.embeddings.vector (pgvector IVFFlat)
  - Results merged with Reciprocal Rank Fusion (k=60)
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from packages.ingestion.embedder import embed_texts

load_dotenv("infra/.env")

# ---------------------------------------------------------------------------
# BM25 — full-text search over chunks.text (inline tsvector)
# ---------------------------------------------------------------------------
_BM25_SQL = """
SELECT
    c.id                                                  AS chunk_id,
    c.text,
    c.page_number,
    c.company                                             AS company_ticker,
    c.fiscal_year,
    ts_rank_cd(
        to_tsvector('english', c.text),
        plainto_tsquery('english', %(query)s)
    )                                                     AS score
FROM sentinel.chunks c
WHERE to_tsvector('english', c.text)
      @@ plainto_tsquery('english', %(query)s)
ORDER BY score DESC
LIMIT %(top_k)s
"""

# ---------------------------------------------------------------------------
# Dense — cosine similarity via pgvector IVFFlat index
# embeddings.vector uses cosine ops; 1 - distance = similarity
# ---------------------------------------------------------------------------
_DENSE_SQL = """
SELECT
    c.id                                                  AS chunk_id,
    c.text,
    c.page_number,
    c.company                                             AS company_ticker,
    c.fiscal_year,
    1 - (e.vector <=> %(vec)s::vector)                    AS score
FROM sentinel.embeddings e
JOIN sentinel.chunks c ON c.id = e.chunk_id
ORDER BY score DESC
LIMIT %(top_k)s
"""


class HybridSearcher:
    """
    BM25 + dense retrieval merged with Reciprocal Rank Fusion.

    Usage:
        searcher = HybridSearcher()
        results = searcher.hybrid_search("TCS revenue FY2025", top_k=20)
    """

    def __init__(self) -> None:
        raw_url = os.getenv("DATABASE_URL", "")
        if not raw_url:
            raise RuntimeError("DATABASE_URL not set — load infra/.env first")
        # psycopg3 wants postgresql://, Aiven ships postgres://
        self._conn_str = raw_url.replace("postgres://", "postgresql://", 1)

    # ------------------------------------------------------------------
    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._conn_str)

    # ------------------------------------------------------------------
    def bm25_search(self, query: str, top_k: int = 20) -> list[dict]:
        """Full-text BM25 search via PostgreSQL ts_rank_cd."""
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(_BM25_SQL, {"query": query, "top_k": top_k})
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    def dense_search(self, query: str, top_k: int = 20) -> list[dict]:
        """Cosine-similarity dense search via bge-small-en-v1.5 + pgvector."""
        vecs = embed_texts([query])
        if not vecs:
            return []
        # Format vector as '[x1,x2,...]' — Postgres casts text → vector
        vec_str = "[" + ",".join(str(x) for x in vecs[0]) + "]"
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(_DENSE_SQL, {"vec": vec_str, "top_k": top_k})
                rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    def hybrid_search(self, query: str, top_k: int = 20) -> list[dict]:
        """
        Reciprocal Rank Fusion over BM25 + dense results.

        RRF score = Σ 1 / (k + rank)   k=60, rank is 1-based
        """
        bm25_hits = self.bm25_search(query, top_k=top_k)
        dense_hits = self.dense_search(query, top_k=top_k)

        K = 60
        rrf_scores: dict[int, float] = {}
        by_id: dict[int, dict] = {}

        for rank, hit in enumerate(bm25_hits, start=1):
            cid = hit["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (K + rank)
            by_id[cid] = hit

        for rank, hit in enumerate(dense_hits, start=1):
            cid = hit["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (K + rank)
            by_id[cid] = hit

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

        results: list[dict] = []
        for cid in sorted_ids[:top_k]:
            item = dict(by_id[cid])
            item["score"] = rrf_scores[cid]
            results.append(item)

        return results
