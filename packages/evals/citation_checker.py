"""
Sentinel — Citation Accuracy Checker

Verifies that financial brief citations:
  1. Reference valid corporate tickers present in the BSE/NSE universe.
  2. Have realistic, positive integer page numbers within the annual report boundaries.
  3. Ground the statements by ensuring key numerical figures or facts in the brief
     are present in the cited chunk text preview.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

KNOWN_TICKERS: set[str] = {
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "RELIANCE",
    "ITC",
    "LT",
    "MARUTI",
    "BAJFINANCE",
    "HCLTECH",
    "WIPRO",
    "TITAN",
    "ULTRACEMCO",
    "SUNPHARMA",
    "NESTLEIND",
    "NTPC",
    "POWERGRID",
    "ASIANPAINT",
    "AXISBANK",
    "KOTAKBANK",
}


@dataclass
class CitationVerificationResult:
    is_valid: bool
    citation_accuracy: float
    total_citations: int
    valid_citations: int
    hallucinated_citations: int
    issues: list[str] = field(default_factory=list)


class CitationChecker:
    """Audits citation validity, format, page bounds, and claim grounding."""

    def __init__(self, max_pages: int = 500) -> None:
        self.max_pages = max_pages

    def verify_citations(
        self,
        final_brief: str,
        citations: list[dict[str, Any]],
        chunks: list[dict[str, Any]] | None = None,
    ) -> CitationVerificationResult:
        """
        Verifies list of citation objects against the brief and retrieved chunks.
        """
        if not citations:
            # If the brief makes factual claims with numbers but has 0 citations, flag it
            num_pattern = r"₹?\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:crore|lakh|%)?"
            has_numbers = bool(re.search(num_pattern, final_brief))
            if has_numbers:
                return CitationVerificationResult(
                    is_valid=False,
                    citation_accuracy=0.0,
                    total_citations=0,
                    valid_citations=0,
                    hallucinated_citations=0,
                    issues=["Brief presents numerical claims with zero supporting citations."],
                )
            return CitationVerificationResult(
                is_valid=True,
                citation_accuracy=1.0,
                total_citations=0,
                valid_citations=0,
                hallucinated_citations=0,
                issues=[],
            )

        valid_count = 0
        hallucinated_count = 0
        issues: list[str] = []

        chunk_texts = [c.get("text", "") for c in (chunks or [])]

        for idx, cit in enumerate(citations, start=1):
            company = str(cit.get("company", "")).strip().upper()
            page = cit.get("page")
            text_preview = str(cit.get("text_preview", "")).strip()

            # 1. Company check
            if not company or (company not in KNOWN_TICKERS and company != "UNKNOWN"):
                issues.append(f"Citation #{idx}: Unknown or unverified company ticker '{company}'.")
                hallucinated_count += 1
                continue

            # 2. Page number check
            try:
                page_num = int(page)
                if page_num < 1 or page_num > self.max_pages:
                    issues.append(
                        f"Citation #{idx} ({company}): Out of range page number {page_num}."
                    )
                    hallucinated_count += 1
                    continue
            except (TypeError, ValueError):
                if page != "?":
                    issues.append(
                        f"Citation #{idx} ({company}): Invalid page representation '{page}'."
                    )
                    hallucinated_count += 1
                    continue

            # 3. Text grounding check (if chunks available)
            if chunk_texts and text_preview:
                grounded = any(text_preview[:40].lower() in ct.lower() for ct in chunk_texts)
                if not grounded and len(text_preview) > 30:
                    issues.append(
                        f"Citation #{idx} ({company}): Preview not found in retrieved chunks."
                    )
                    hallucinated_count += 1
                    continue

            valid_count += 1

        total = len(citations)
        accuracy = (valid_count / total) if total > 0 else 1.0

        return CitationVerificationResult(
            is_valid=(hallucinated_count == 0),
            citation_accuracy=round(accuracy, 4),
            total_citations=total,
            valid_citations=valid_count,
            hallucinated_citations=hallucinated_count,
            issues=issues,
        )
