"""
Sentinel — Text Chunker

Splits a ParsedDocument into overlapping character-window chunks suitable
for bge-small-en-v1.5 (512-token BERT context window).

Sizes:
  CHUNK_CHARS   = 1800  ≈ 450 BERT tokens (leaves headroom under the 512 limit)
  OVERLAP_CHARS = 200   ≈ 50  BERT tokens

Each chunk records the starting page number extracted from [PAGE N] markers
that parse_pdf inserts into the raw_text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from packages.ingestion.parsers import ParsedDocument

CHUNK_CHARS = 1800
OVERLAP_CHARS = 200


@dataclass
class TextChunk:
    chunk_index: int
    text: str
    page_number: int
    char_count: int


def chunk_document(doc: ParsedDocument) -> list[TextChunk]:
    """
    Slide a CHUNK_CHARS window with OVERLAP_CHARS overlap over doc.raw_text.

    Returns an empty list for empty or all-scanned documents.
    """
    raw = doc.raw_text
    if not raw:
        return []

    # Precompute (char_offset, page_number) pairs from [PAGE N] markers.
    page_positions: list[tuple[int, int]] = [
        (m.start(), int(m.group(1)))
        for m in re.finditer(r"\[PAGE (\d+)\]", raw)
    ]

    def _page_at(pos: int) -> int:
        page = 1
        for offset, pnum in page_positions:
            if offset <= pos:
                page = pnum
            else:
                break
        return page

    chunks: list[TextChunk] = []
    start = 0
    step = CHUNK_CHARS - OVERLAP_CHARS

    while start < len(raw):
        end = min(start + CHUNK_CHARS, len(raw))
        text = raw[start:end].strip()
        if text:
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    text=text,
                    page_number=_page_at(start),
                    char_count=len(text),
                )
            )
        start += step

    return chunks
