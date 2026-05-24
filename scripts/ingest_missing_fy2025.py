"""
Sentinel — Ingest the 3 remaining FY2025 companies:
  AXISBANK, ITC — full pipeline (parse → chunk → embed → DB)
  POWERGRID     — scanned PDF: insert filing + raw_doc only (no chunks)

BAJFINANCE and KOTAKBANK are intentionally excluded:
  BAJFINANCE — corrupt PDF (skip for now)
  KOTAKBANK  — no direct URL available

Usage:
    uv run python scripts/ingest_missing_fy2025.py
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packages.common.config import get_settings
from packages.ingestion.chunker import chunk_document
from packages.ingestion.embedder import embed_texts
from packages.ingestion.fetchers import _REGISTRY
from packages.ingestion.models import (
    Chunk,
    Company,
    Embedding,
    Filing,
    FilingType,
    RawDocument,
)
from packages.ingestion.parsers import parse_pdf

FISCAL_YEAR = "2024-25"
FISCAL_YEAR_TAG = "FY25"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 32

TARGETS: dict[str, str] = {
    "AXISBANK": "https://nsearchives.nseindia.com/annual_reports/AR_26622_AXISBANK_2024_2025_A_27062025104637.pdf",
    "ITC": "https://nsearchives.nseindia.com/annual_reports/AR_26624_ITC_2024_2025_A_27062025150548.pdf",
    "POWERGRID": "https://nsearchives.nseindia.com/annual_reports/AR_27256_POWERGRID_2024_2025_A_03082025200555.pdf",
    # BAJFINANCE — corrupt PDF, intentionally skipped
    # KOTAKBANK  — no direct URL, intentionally skipped
}


def get_engine():
    settings = get_settings()
    url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(url)


def upsert_company(session: Session, ticker: str) -> Company:
    row = session.scalar(select(Company).where(Company.ticker == ticker))
    if row is None:
        info = _REGISTRY[ticker]
        row = Company(ticker=ticker, bse_code=info["bse"], name=info["name"])
        session.add(row)
        session.flush()
    return row


def filing_exists(session: Session, company_id: int) -> bool:
    return (
        session.scalar(
            select(Filing).where(
                Filing.company_id == company_id,
                Filing.fiscal_year == FISCAL_YEAR,
                Filing.filing_type == FilingType.annual_report,
            )
        )
        is not None
    )


def main() -> None:
    pdf_dir = Path("tmp/fy2025")
    engine = get_engine()

    print("\n=== Sentinel FY2025 — Missing Companies Ingestion ===\n")
    print(f"Targets: {', '.join(TARGETS)}\n")

    print("Pre-loading embedding model...")
    embed_texts(["warmup"])
    print("  Model ready.\n")

    results = []

    for ticker, pdf_url in TARGETS.items():
        pdf_path = pdf_dir / f"{ticker}_2025.pdf"
        if not pdf_path.exists():
            print(f"  SKIP {ticker}: PDF not found at {pdf_path}")
            continue

        t0 = time.perf_counter()
        size_mb = pdf_path.stat().st_size / 1_048_576
        print(f"[{ticker}] Parsing ({size_mb:.1f} MB)...")

        pdf_bytes = pdf_path.read_bytes()
        try:
            parsed = parse_pdf(pdf_bytes)
        except Exception as exc:
            print(f"  ERROR {ticker}: parse failed — {exc}")
            continue

        chars = len(parsed.raw_text or "")
        print(f"  pages={parsed.page_count}  chars={chars:,}  scanned={parsed.is_likely_scanned}")

        # ── Check idempotency ──────────────────────────────────────────────
        with Session(engine) as session:
            company = upsert_company(session, ticker)
            if filing_exists(session, company.id):
                print(f"  SKIP {ticker}: FY{FISCAL_YEAR} already in DB\n")
                continue
            session.commit()

        # ── Scanned-only PDF: insert filing + raw_doc, no chunks ──────────
        if not parsed.raw_text or chars < 500:
            print(f"  WARN {ticker}: no extractable text — inserting as scanned (no chunks)")
            with Session(engine) as session:
                company = upsert_company(session, ticker)
                filing = Filing(
                    company_id=company.id,
                    filing_type=FilingType.annual_report,
                    fiscal_year=FISCAL_YEAR,
                    pdf_url=pdf_url,
                    ingested_at=datetime.now(UTC),
                )
                session.add(filing)
                session.flush()
                raw_doc = RawDocument(
                    filing_id=filing.id,
                    raw_text="",
                    page_count=parsed.page_count,
                    file_size_bytes=parsed.file_size_bytes,
                    is_scanned=True,
                )
                session.add(raw_doc)
                session.commit()
            elapsed = time.perf_counter() - t0
            print(f"  ⚠️  {ticker}: scanned PDF inserted (0 chunks) ({elapsed:.0f}s)\n")
            results.append((ticker, parsed.page_count, 0, 0))
            continue

        # ── Chunk ─────────────────────────────────────────────────────────
        text_chunks = chunk_document(parsed)
        print(f"  chunks={len(text_chunks)}")

        # ── Embed ─────────────────────────────────────────────────────────
        chunk_texts = [c.text for c in text_chunks]
        embeddings = embed_texts(chunk_texts, batch_size=BATCH_SIZE)
        print(f"  embeddings={len(embeddings)}")

        # ── Store ─────────────────────────────────────────────────────────
        with Session(engine) as session:
            company = upsert_company(session, ticker)
            filing = Filing(
                company_id=company.id,
                filing_type=FilingType.annual_report,
                fiscal_year=FISCAL_YEAR,
                pdf_url=pdf_url,
                ingested_at=datetime.now(UTC),
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
                    company=ticker,
                    filing_type=FilingType.annual_report.value,
                    fiscal_year=FISCAL_YEAR_TAG,
                    is_table=False,
                )
                session.add(chunk_row)
                chunk_rows.append(chunk_row)
            session.flush()

            for chunk_row, vec in zip(chunk_rows, embeddings, strict=False):
                session.add(
                    Embedding(
                        chunk_id=chunk_row.id,
                        model_name=MODEL_NAME,
                        vector=vec,
                    )
                )

            session.commit()

        elapsed = time.perf_counter() - t0
        print(
            f"  ✅ {ticker}: {parsed.page_count} pages, "
            f"{len(text_chunks)} chunks, {len(embeddings)} embeddings  ({elapsed:.0f}s)\n"
        )
        results.append((ticker, parsed.page_count, len(text_chunks), len(embeddings)))

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print(f"{'TICKER':<12} {'PAGES':>6} {'CHUNKS':>7} {'EMBEDDINGS':>11}")
    print("-" * 60)
    for ticker, pages, chunks, embs in results:
        print(f"{ticker:<12} {pages:>6} {chunks:>7} {embs:>11}")
    print("=" * 60)
    print(f"Companies processed: {len(results)}")

    # ── Final corpus counts ───────────────────────────────────────────────────
    print("\n=== Final Corpus State ===")
    from sqlalchemy import text as sqlt

    with engine.connect() as conn:
        rows = conn.execute(
            sqlt(
                "SELECT fiscal_year, COUNT(*) FROM sentinel.filings "
                "GROUP BY fiscal_year ORDER BY fiscal_year"
            )
        ).fetchall()
        for fy, cnt in rows:
            print(f"  sentinel.filings  fiscal_year={fy!r:12}  count={cnt}")

        rows = conn.execute(
            sqlt(
                "SELECT fiscal_year, COUNT(*) FROM sentinel.chunks "
                "GROUP BY fiscal_year ORDER BY fiscal_year"
            )
        ).fetchall()
        for fy, cnt in rows:
            print(f"  sentinel.chunks   fiscal_year={fy!r:12}  count={cnt}")


if __name__ == "__main__":
    main()
