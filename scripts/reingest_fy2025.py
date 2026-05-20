"""
Sentinel — FY2025 Full Re-ingestion Pipeline
Usage: python scripts/reingest_fy2025.py [--pdf-dir DIR] [--dry-run]

For each PDF in tmp/fy2025/:
  1. Find or create sentinel.companies row
  2. Skip if FY2025 filing already exists (idempotent)
  3. Insert sentinel.filings row  (fiscal_year = "2024-25")
  4. Extract text via pymupdf → sentinel.raw_documents
  5. Chunk text (1800-char windows, 200-char overlap)
  6. Embed chunks with BAAI/bge-small-en-v1.5 (fastembed, batch=32)
  7. Insert sentinel.chunks + sentinel.embeddings
  8. Print: ✅ TICKER: X pages, Y chunks, Z embeddings

Existing FY2024 data is preserved — no DELETE statements.

Prerequisites:
  - Run alembic upgrade head first (adds chunks + embeddings tables)
  - Enable pgvector extension in the DB (Aiven Console or `CREATE EXTENSION vector`)
  - PDFs downloaded by scripts/download_fy2025.py into tmp/fy2025/
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.common.config import get_settings
from packages.ingestion.chunker import chunk_document
from packages.ingestion.embedder import embed_texts
from packages.ingestion.fetchers import _REGISTRY, CompanyInfo, lookup_company
from packages.ingestion.models import (
    Chunk,
    Company,
    Embedding,
    Filing,
    FilingType,
    RawDocument,
)
from packages.ingestion.parsers import parse_pdf

app = typer.Typer(name="reingest-fy2025", add_completion=False)

FISCAL_YEAR = "2024-25"
FISCAL_YEAR_TAG = "FY25"   # denormalized tag stored in chunks.fiscal_year
MODEL_NAME = "BAAI/bge-small-en-v1.5"

# URL mapping — same as download_fy2025.py
URLS: dict[str, str] = {
    "TCS":        "https://nsearchives.nseindia.com/annual_reports/AR_26456_TCS_2024_2025_A_27052025233502.pdf",
    "INFY":       "https://nsearchives.nseindia.com/annual_reports/AR_26481_INFY_2024_2025_A_02062025153945.pdf",
    "HDFCBANK":   "https://nsearchives.nseindia.com/annual_reports/AR_27115_HDFCBANK_2024_2025_U_25072025220054.pdf",
    "RELIANCE":   "https://nsearchives.nseindia.com/annual_reports/AR_27322_RELIANCE_2024_2025_A_07082025114457.pdf",
    "ICICIBANK":  "https://nsearchives.nseindia.com/annual_reports/AR_27289_ICICIBANK_2024_2025_A_05082025201317.pdf",
    "WIPRO":      "https://nsearchives.nseindia.com/annual_reports/AR_26582_WIPRO_2024_2025_A_21062025124943.pdf",
    "HCLTECH":    "https://nsearchives.nseindia.com/annual_reports/AR_27254_HCLTECH_2024_2025_A_02082025194851.pdf",
    "BAJFINANCE": "https://nsearchives.nseindia.com/annual_reports/AR_26674_BAJFINANCE_2024_2025_A_02072025000055.pdf",
    "ASIANPAINT": "https://nsearchives.nseindia.com/annual_reports/AR_26496_ASIANPAINT_2024_2025_A_03062025224818.pdf",
    "MARUTI":     "https://nsearchives.nseindia.com/annual_reports/AR_27293_MARUTI_2024_2025_A_05082025210558.pdf",
    "SUNPHARMA":  "https://nsearchives.nseindia.com/annual_reports/AR_26732_SUNPHARMA_2024_2025_A_04072025175058.pdf",
    "TITAN":      "https://nsearchives.nseindia.com/annual_reports/AR_26625_TITAN_2024_2025_A_27062025152121.pdf",
    "LT":         "https://nsearchives.nseindia.com/annual_reports/AR_26451_LT_2024_2025_A_26052025131455.pdf",
    "ULTRACEMCO": "http://nsearchives.nseindia.com/annual_reports/AR_27126_ULTRACEMCO_2024_2025_A_28072025142546.pdf",
    "NESTLEIND":  "https://nsearchives.nseindia.com/annual_reports/AR_26487_NESTLEIND_2024_2025_A_03062025002440.pdf",
    "POWERGRID":  "https://nsearchives.nseindia.com/annual_reports/AR_27256_POWERGRID_2024_2025_A_03082025200555.pdf",
    "NTPC":       "https://nsearchives.nseindia.com/annual_reports/AR_27336_NTPC_2024_2025_A_07082025183440.pdf",
    "ITC":        "https://nsearchives.nseindia.com/annual_reports/AR_26624_ITC_2024_2025_A_27062025150548.pdf",
    "AXISBANK":   "https://nsearchives.nseindia.com/annual_reports/AR_26622_AXISBANK_2024_2025_A_27062025104637.pdf",
}


def _get_engine():
    settings = get_settings()
    url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(url)


def _upsert_company(session: Session, ticker: str) -> Company:
    row = session.scalar(select(Company).where(Company.ticker == ticker))
    if row is None:
        info = _REGISTRY[ticker]
        row = Company(ticker=ticker, bse_code=info["bse"], name=info["name"])
        session.add(row)
        session.flush()
    return row


def _filing_exists(session: Session, company_id: int, fiscal_year: str) -> bool:
    return session.scalar(
        select(Filing).where(
            Filing.company_id == company_id,
            Filing.fiscal_year == fiscal_year,
            Filing.filing_type == FilingType.annual_report,
        )
    ) is not None


@app.command()
def reingest(
    pdf_dir: Path = typer.Option(
        Path("tmp/fy2025"),
        "--pdf-dir",
        help="Directory containing {TICKER}_2025.pdf files",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse and chunk but skip DB writes"),
    batch_size: int = typer.Option(32, "--batch-size", help="Embedding batch size"),
) -> None:
    """
    Full FY2025 ingestion: text extraction → chunking → embedding → DB.
    """
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        typer.echo(f"ERROR: PDF directory not found: {pdf_dir}", err=True)
        typer.echo("Run scripts/download_fy2025.py first.", err=True)
        raise typer.Exit(1)

    typer.echo(f"\n=== Sentinel FY2025 Re-ingestion ({FISCAL_YEAR}) ===\n")
    typer.echo(f"PDF dir : {pdf_dir.resolve()}")
    typer.echo(f"Dry run : {dry_run}")
    typer.echo(f"Model   : {MODEL_NAME}\n")

    if not dry_run:
        engine = _get_engine()

    results: list[tuple[str, int, int, int]] = []  # (ticker, pages, chunks, embeddings)

    typer.echo("Pre-loading embedding model (downloads ~60 MB on first run)...")
    embed_texts(["warmup"])  # trigger model download before the main loop
    typer.echo("  Model ready.\n")

    for ticker, pdf_url in URLS.items():
        pdf_path = pdf_dir / f"{ticker}_2025.pdf"
        if not pdf_path.exists():
            typer.echo(f"  SKIP {ticker}: PDF not found at {pdf_path}")
            continue

        t0 = time.perf_counter()
        typer.echo(f"[{ticker}] Reading PDF ({pdf_path.stat().st_size / 1_048_576:.1f} MB)...")

        pdf_bytes = pdf_path.read_bytes()

        # ── 1. Parse ───────────────────────────────────────────────────────
        try:
            parsed = parse_pdf(pdf_bytes)
        except Exception as exc:
            typer.echo(f"  ERROR {ticker}: parse failed — {exc}", err=True)
            continue

        typer.echo(
            f"  pages={parsed.page_count}  chars={len(parsed.raw_text or ''):,}"
            f"  scanned_pages={parsed.scanned_page_count}"
        )

        if parsed.is_likely_scanned:
            typer.echo(f"  WARN {ticker}: mostly scanned — OCR text may be poor")

        # ── 2. Chunk ───────────────────────────────────────────────────────
        text_chunks = chunk_document(parsed)
        typer.echo(f"  chunks={len(text_chunks)}")

        if not text_chunks:
            typer.echo(f"  SKIP {ticker}: no text extracted", err=True)
            continue

        # ── 3. Embed ───────────────────────────────────────────────────────
        chunk_texts = [c.text for c in text_chunks]
        embeddings = embed_texts(chunk_texts, batch_size=batch_size)
        typer.echo(f"  embeddings={len(embeddings)}")

        if dry_run:
            elapsed = time.perf_counter() - t0
            typer.echo(f"  DRY RUN — skipping DB write ({elapsed:.1f}s)\n")
            results.append((ticker, parsed.page_count, len(text_chunks), len(embeddings)))
            continue

        # ── 4. Store ───────────────────────────────────────────────────────
        with Session(engine) as session:
            company = _upsert_company(session, ticker)

            if _filing_exists(session, company.id, FISCAL_YEAR):
                typer.echo(f"  SKIP {ticker}: FY{FISCAL_YEAR} already in DB\n")
                continue

            filing = Filing(
                company_id=company.id,
                filing_type=FilingType.annual_report,
                fiscal_year=FISCAL_YEAR,
                pdf_url=pdf_url,
                ingested_at=datetime.now(timezone.utc),
            )
            session.add(filing)
            session.flush()

            raw_doc = RawDocument(
                filing_id=filing.id,
                raw_text=parsed.raw_text,
                page_count=parsed.page_count,
                file_size_bytes=parsed.file_size_bytes,
                is_scanned=parsed.is_likely_scanned,
            )
            session.add(raw_doc)
            session.flush()

            chunk_rows: list[Chunk] = []
            for tc in text_chunks:
                chunk_row = Chunk(
                    raw_document_id=raw_doc.id,
                    chunk_index=tc.chunk_index,
                    text=tc.text,
                    page_number=tc.page_number,
                    char_count=tc.char_count,
                    # Denormalized for faster search queries
                    company=ticker,
                    filing_type=FilingType.annual_report.value,
                    fiscal_year=FISCAL_YEAR_TAG,
                    is_table=False,
                )
                session.add(chunk_row)
                chunk_rows.append(chunk_row)
            session.flush()

            for chunk_row, vec in zip(chunk_rows, embeddings):
                session.add(
                    Embedding(
                        chunk_id=chunk_row.id,
                        model_name=MODEL_NAME,
                        vector=vec,
                    )
                )

            session.commit()

        elapsed = time.perf_counter() - t0
        typer.echo(
            f"  ✅ {ticker}: {parsed.page_count} pages, "
            f"{len(text_chunks)} chunks, {len(embeddings)} embeddings  ({elapsed:.0f}s)\n"
        )
        results.append((ticker, parsed.page_count, len(text_chunks), len(embeddings)))

    # ── Summary ────────────────────────────────────────────────────────────────
    typer.echo("=" * 60)
    typer.echo(f"{'TICKER':<12} {'PAGES':>6} {'CHUNKS':>7} {'EMBEDDINGS':>11}")
    typer.echo("-" * 60)
    for ticker, pages, chunks, embs in results:
        typer.echo(f"{ticker:<12} {pages:>6} {chunks:>7} {embs:>11}")
    typer.echo("=" * 60)
    typer.echo(f"Total companies ingested: {len(results)}")

    if not dry_run and results:
        typer.echo("\nRunning corpus verification query...")
        _print_corpus_state(_get_engine())


def _print_corpus_state(engine) -> None:
    sql = """
SELECT
    c.ticker,
    c.name,
    f.fiscal_year,
    rd.page_count,
    COUNT(DISTINCT ch.id)  AS chunks,
    COUNT(DISTINCT e.id)   AS embeddings,
    rd.is_scanned
FROM sentinel.companies c
JOIN sentinel.filings       f  ON f.company_id  = c.id
JOIN sentinel.raw_documents rd ON rd.filing_id  = f.id
LEFT JOIN sentinel.chunks      ch ON ch.raw_document_id = rd.id
LEFT JOIN sentinel.embeddings  e  ON e.chunk_id = ch.id
GROUP BY c.ticker, c.name, f.fiscal_year, rd.page_count, rd.is_scanned
ORDER BY f.fiscal_year DESC, chunks DESC;
"""
    with engine.connect() as conn:
        from sqlalchemy import text
        rows = conn.execute(text(sql)).fetchall()

    header = f"\n{'TICKER':<12} {'NAME':<30} {'FY':<8} {'PAGES':>6} {'CHUNKS':>7} {'EMBEDDINGS':>11} {'SCANNED'}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for row in rows:
        ticker, name, fy, pages, chunks, embs, scanned = row
        typer.echo(
            f"{ticker:<12} {name[:29]:<30} {fy:<8} {pages or 0:>6} "
            f"{chunks:>7} {embs:>11} {'Y' if scanned else 'N'}"
        )


if __name__ == "__main__":
    app()
