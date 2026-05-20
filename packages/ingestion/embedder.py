"""
Sentinel — Embedder

Generates 384-dim L2-normalised embeddings using BAAI/bge-small-en-v1.5
via fastembed (ONNX Runtime — no PyTorch needed).

The model is downloaded from HuggingFace on first call (~60 MB) and cached
in ~/.cache/fastembed.

Install note: fastembed requires onnxruntime.  On Intel Mac + Python 3.13
run the one-time manual install (uv can't auto-resolve the right wheel):

  uv pip install "onnxruntime==1.23.2" --python-platform x86_64-apple-darwin
  uv pip install "fastembed>=0.7.0"    --python-platform x86_64-apple-darwin
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BATCH_SIZE = 32

_model: "TextEmbedding | None" = None


def _get_model() -> "TextEmbedding":
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def embed_texts(texts: list[str], batch_size: int = BATCH_SIZE) -> list[list[float]]:
    """
    Return one 384-dim embedding per text, L2-normalised.

    bge models expect normalised embeddings for cosine similarity.
    Returns an empty list when texts is empty.
    """
    if not texts:
        return []
    model = _get_model()
    embeddings = list(model.embed(texts, batch_size=batch_size))
    return [e.tolist() for e in embeddings]
