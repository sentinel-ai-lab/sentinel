"""
Sentinel — Neural Reranker

Uses BAAI/bge-reranker-base via fastembed (ONNX Runtime — no PyTorch needed).
fastembed 0.8+ ships a TextCrossEncoder with ONNX inference, so it works on
Intel Mac and any platform where fastembed already runs.

API: TextCrossEncoder.rerank(query, documents) → list[float] in input order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

RERANKER_MODEL = "BAAI/bge-reranker-base"

_model: TextCrossEncoder | None = None


def _get_model() -> TextCrossEncoder:
    global _model
    if _model is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _model = TextCrossEncoder(model_name=RERANKER_MODEL)
    return _model


class Reranker:
    """
    Neural cross-encoder reranker (ONNX via fastembed).

    Usage:
        reranker = Reranker()
        top5 = reranker.rerank(query, chunks, top_n=5)
    """

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_n: int = 5,
    ) -> list[dict]:
        """
        Score each (query, chunk_text) pair and return the top_n chunks
        sorted by reranker score descending.

        Each returned dict retains all original fields plus `reranker_score`.
        TextCrossEncoder.rerank() returns one float per document, in input order.
        """
        if not chunks:
            return []

        model = _get_model()
        documents = [c["text"] for c in chunks]

        # Returns list[float], same order as documents
        scores = list(model.rerank(query, documents))

        ranked = sorted(
            zip(chunks, scores),
            key=lambda x: float(x[1]),
            reverse=True,
        )

        return [
            {**chunk, "reranker_score": float(score)}
            for chunk, score in ranked[:top_n]
        ]
