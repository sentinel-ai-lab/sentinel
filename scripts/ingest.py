"""
Sentinel — Ingestion CLI
Usage: python scripts/ingest.py TICKER
Example: python scripts/ingest.py TCS

Phase 1 pipeline:
  NSE API → PDF URL → download → parse text → store in Postgres

Phase 2 (next): chunking, embedding, vector storage.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import typer
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.common.config import get_settings
from packages.ingestion.fetchers import (
    download_pdf,
    fetch_annual_report_url,
    init_nse_session,
    lookup_company,
)
from packages.ingestion.models import Company, Filing, FilingType, RawDocument
from packages.ingestion.parsers import parse_pdf

app = typer.Typer(
    name="sentinel-ingest",
    help="Sentinel ingestion CLI — download and store BSE/NSE filings.",
)


def _get_engine():
    settings = get_settings()
    # Aiven emits postgres://, SQLAlchemy 2.0 + psycopg v3 needs postgresql+psycopg://
    url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(url)


def _upsert_company(session: Session, company_info) -> Company:
    """Insert company if not present, return the row either way."""
    row = session.scalar(select(Company).where(Company.ticker == company_info.ticker))
    if row is None:
        row = Company(
            ticker=company_info.ticker,
            bse_code=company_info.bse_code,
            name=company_info.name,
        )
        session.add(row)
        session.flush()  # get row.id without committing
        typer.echo(f"  + Created company row  : {company_info.ticker}")
    else:
        typer.echo(f"  ~ Company already exists: {company_info.ticker}")
    return row


def _filing_exists(session: Session, company_id: int, fiscal_year: str) -> bool:
    row = session.scalar(
        select(Filing).where(
            Filing.company_id == company_id,
            Filing.fiscal_year == fiscal_year,
            Filing.filing_type == FilingType.annual_report,
        )
    )
    return row is not None


@app.command()
def ingest(
    ticker: str = typer.Argument(..., help="NSE ticker symbol, e.g. TCS or INFY"),
    fiscal_year: str = typer.Option("2024-25", help="Fiscal year, e.g. 2024-25"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Fetch and parse but do not store"),
) -> None:
    """
    Ingest the annual report for TICKER into Postgres.

    Steps: NSE API → PDF download → text extraction → DB store.
    """
    typer.echo(f"\n=== Sentinel Ingestion: {ticker.upper()} ===\n")

    # ── 1. Lookup ────────────────────────────────────────────────────────
    typer.echo("[1/5] Looking up company...")
    try:
        company_info = lookup_company(ticker)
    except ValueError as exc:
        typer.echo(f"  ERROR: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"  Name    : {company_info.name}")
    typer.echo(f"  BSE     : {company_info.bse_code}")
    typer.echo(f"  NSE sym : {company_info.nse_symbol}")

    with httpx.Client(follow_redirects=True) as client:

        # ── 2. Fetch PDF URL ─────────────────────────────────────────────
        typer.echo("\n[2/5] Fetching annual report URL from NSE...")
        init_nse_session(client)
        try:
            pdf_url = fetch_annual_report_url(ticker, client)
        except Exception as exc:
            typer.echo(f"  ERROR: {exc}", err=True)
            raise typer.Exit(1)
        typer.echo(f"  URL: {pdf_url}")

        # ── 3. Download PDF ──────────────────────────────────────────────
        typer.echo("\n[3/5] Downloading PDF...")
        try:
            pdf_bytes = download_pdf(pdf_url, client)
        except Exception as exc:
            typer.echo(f"  ERROR: {exc}", err=True)
            raise typer.Exit(1)
        typer.echo(f"  Size: {len(pdf_bytes) / 1_048_576:.1f} MB")

    # ── 4. Parse PDF ─────────────────────────────────────────────────────
    typer.echo("\n[4/5] Extracting text with pymupdf...")
    try:
        parsed = parse_pdf(pdf_bytes)
    except Exception as exc:
        typer.echo(f"  ERROR: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"  Pages          : {parsed.page_count}")
    typer.echo(f"  Characters     : {len(parsed.raw_text):,}")
    typer.echo(f"  Scanned pages  : {parsed.scanned_page_count}")
    if parsed.is_likely_scanned:
        typer.echo("  WARNING: document appears mostly scanned — OCR needed (Phase 2)")

    if dry_run:
        typer.echo("\n[5/5] Dry run — skipping database write.")
        typer.echo("\nDone.")
        return

    # ── 5. Store in Postgres ─────────────────────────────────────────────
    typer.echo("\n[5/5] Storing in Postgres (sentinel schema)...")
    engine = _get_engine()

    with Session(engine) as session:
        company_row = _upsert_company(session, company_info)

        if _filing_exists(session, company_row.id, fiscal_year):
            typer.echo(f"  ~ Filing already ingested for {ticker} FY{fiscal_year} — skipping.")
            typer.echo("\nDone (no-op).")
            return

        filing = Filing(
            company_id=company_row.id,
            filing_type=FilingType.annual_report,
            fiscal_year=fiscal_year,
            pdf_url=pdf_url,
            source="NSE",
            ingested_at=datetime.now(timezone.utc),
        )
        session.add(filing)
        session.flush()
        typer.echo(f"  + Created filing row   : FY{fiscal_year} annual report")

        raw_doc = RawDocument(
            filing_id=filing.id,
            raw_text=parsed.raw_text,
            page_count=parsed.page_count,
            file_size_bytes=parsed.file_size_bytes,
        )
        session.add(raw_doc)
        session.commit()
        typer.echo(f"  + Created raw_document : {len(parsed.raw_text):,} chars stored")

    typer.echo(f"\nDone. {ticker.upper()} FY{fiscal_year} annual report ingested successfully.")


if __name__ == "__main__":
    app()
