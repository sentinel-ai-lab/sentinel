"""
Sentinel — Ingestion CLI
Usage: python scripts/ingest.py TICKER
Example: python scripts/ingest.py TCS

Phase 1: Downloads annual report PDF → extracts text → stores raw doc in Postgres.
Phase 2 (next): Chunking, embedding, and vector storage will be added here.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer

app = typer.Typer(
    name="sentinel-ingest",
    help="Sentinel ingestion CLI — download and store BSE/NSE filings.",
)


@app.command()
def ingest(
    ticker: str = typer.Argument(..., help="NSE ticker symbol (e.g. TCS, INFY)"),
    filing_type: str = typer.Option("annual_report", help="Filing type to ingest"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Fetch but do not store"),
) -> None:
    """
    Ingest filings for a given ticker.

    Phase 1 milestone: downloads annual report PDF, extracts text,
    stores a RawDocument row in Postgres.
    """
    typer.echo(f"📥 Starting ingestion for: {ticker.upper()}")
    typer.echo(f"   Filing type : {filing_type}")
    typer.echo(f"   Dry run     : {dry_run}")
    typer.echo("")

    # ------------------------------------------------------------------
    # TODO (Phase 1, Week 2): implement below
    # 1. Look up BSE code from ticker
    # 2. Fetch annual report PDF URL from BSE API
    # 3. Download PDF with httpx + tenacity retry
    # 4. Extract text with pdfplumber (preserve page numbers)
    # 5. Store RawDocument row in Postgres
    # ------------------------------------------------------------------

    typer.echo("⚠️  Ingestion logic not yet implemented (Phase 1, Week 2).")
    typer.echo("   See: packages/ingestion/fetchers.py")
    typer.echo("   See: packages/ingestion/parsers.py")
    typer.echo("   See: packages/ingestion/models.py")


if __name__ == "__main__":
    app()
