"""
Sentinel — PDF Parsers

Public API:
  parse_pdf(pdf_bytes) → ParsedDocument

ParsedDocument holds:
  - pages: list of (page_number, text) — used by Phase 2 chunker for citations
  - raw_text: full concatenated text — stored in raw_documents.raw_text
  - page_count, file_size_bytes — stored as metadata

Scanned PDF detection: if a page yields < 20 chars of text it is likely a
scanned image. We flag the document rather than silently returning empty text.
OCR support is deferred to Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import fitz  # pymupdf


_MIN_CHARS_PER_PAGE = 20  # below this → page is probably a scanned image


@dataclass
class PageText:
    page_number: int   # 1-indexed, matches the printed page number in the PDF
    text: str


@dataclass
class ParsedDocument:
    pages: list[PageText]
    page_count: int
    file_size_bytes: int
    scanned_page_count: int = field(default=0)

    @property
    def raw_text(self) -> str:
        """Full text with page markers — used for raw_documents.raw_text storage."""
        parts = []
        for p in self.pages:
            parts.append(f"[PAGE {p.page_number}]\n{p.text.strip()}")
        return "\n\n".join(parts)

    @property
    def is_likely_scanned(self) -> bool:
        """True if more than half the pages appear to be scanned images."""
        return self.scanned_page_count > self.page_count // 2


def parse_pdf(pdf_bytes: bytes) -> ParsedDocument:
    """
    Extract text from *pdf_bytes* using pymupdf.

    Returns a ParsedDocument. Raises ValueError if the bytes are not a valid PDF.
    """
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Input is not a valid PDF (missing %PDF- header)")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages: list[PageText] = []
    scanned_count = 0

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        if len(text.strip()) < _MIN_CHARS_PER_PAGE:
            scanned_count += 1
        pages.append(PageText(page_number=i, text=text))

    doc.close()

    return ParsedDocument(
        pages=pages,
        page_count=len(pages),
        file_size_bytes=len(pdf_bytes),
        scanned_page_count=scanned_count,
    )
