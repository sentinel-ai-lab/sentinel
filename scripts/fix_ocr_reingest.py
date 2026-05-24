"""
Re-ingest PDFs for companies whose raw_documents.raw_text is empty.

Downloads the PDF from the URL already stored in sentinel.filings,
re-parses with the OCR-enabled parser, and UPDATEs the existing
raw_documents row in-place — does NOT create duplicate filings.

Usage:
    uv run python scripts/fix_ocr_reingest.py              # all empty docs
    uv run python scripts/fix_ocr_reingest.py BAJFINANCE TITAN
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import typer
from sqlalchemy import create_engine, text

from packages.common.config import get_settings
from packages.ingestion.parsers import parse_pdf

app = typer.Typer()


def _get_engine():
    settings = get_settings()
    url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(url)


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


@app.command()
def main(tickers: list[str] = typer.Argument(default=None)) -> None:
    """
    Re-parse PDFs that yielded empty raw_text.
    Pass specific tickers, or omit to fix all empty rows.
    """
    engine = _get_engine()

    with engine.begin() as conn:
        if tickers:
            query = text("""
                SELECT c.ticker, f.pdf_url, rd.id AS doc_id
                FROM sentinel.companies c
                JOIN sentinel.filings f ON f.company_id = c.id
                JOIN sentinel.raw_documents rd ON rd.filing_id = f.id
                WHERE c.ticker = ANY(:tickers)
                  AND (rd.raw_text IS NULL OR rd.raw_text = '')
                ORDER BY c.ticker
            """)
            rows = conn.execute(query, {"tickers": list(tickers)}).fetchall()
        else:
            query = text("""
                SELECT c.ticker, f.pdf_url, rd.id AS doc_id
                FROM sentinel.companies c
                JOIN sentinel.filings f ON f.company_id = c.id
                JOIN sentinel.raw_documents rd ON rd.filing_id = f.id
                WHERE rd.raw_text IS NULL OR rd.raw_text = ''
                ORDER BY c.ticker
            """)
            rows = conn.execute(query).fetchall()

    if not rows:
        typer.echo("No empty raw_documents found — nothing to do.")
        raise typer.Exit(0)

    typer.echo(f"Found {len(rows)} document(s) to re-ingest: {[r.ticker for r in rows]}\n")

    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for row in rows:
            ticker, pdf_url, doc_id = row.ticker, row.pdf_url, row.doc_id
            typer.echo(f"=== {ticker} (raw_document id={doc_id}) ===")

            # ── Download ─────────────────────────────────────────────────────
            typer.echo(f"  Downloading: {pdf_url[:80]}...")
            try:
                resp = client.get(pdf_url, headers=_BROWSER_HEADERS)
                resp.raise_for_status()
                pdf_bytes = resp.content
            except Exception as exc:
                typer.echo(f"  ERROR downloading: {exc}", err=True)
                continue
            typer.echo(f"  Downloaded: {len(pdf_bytes) / 1_048_576:.1f} MB")

            # ── Parse (with OCR fallback) ─────────────────────────────────────
            typer.echo("  Parsing (OCR fallback active for scanned pages)...")
            try:
                parsed = parse_pdf(pdf_bytes)
            except Exception as exc:
                typer.echo(f"  ERROR parsing: {exc}", err=True)
                continue

            typer.echo(f"  Pages      : {parsed.page_count}")
            typer.echo(f"  Characters : {len(parsed.raw_text or ''):,}")
            typer.echo(f"  is_scanned : {parsed.is_scanned}")

            # ── Update raw_documents row in-place ─────────────────────────────
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE sentinel.raw_documents
                        SET raw_text        = :raw_text,
                            page_count      = :page_count,
                            file_size_bytes = :file_size_bytes,
                            is_scanned      = :is_scanned
                        WHERE id = :doc_id
                    """),
                    {
                        "raw_text": parsed.raw_text,
                        "page_count": parsed.page_count,
                        "file_size_bytes": parsed.file_size_bytes,
                        "is_scanned": parsed.is_scanned,
                    }
                    | {"doc_id": doc_id},
                )
            typer.echo(f"  ✅ Updated raw_document id={doc_id}\n")

    typer.echo("Done.")


if __name__ == "__main__":
    app()
