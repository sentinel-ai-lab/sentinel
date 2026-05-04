"""
Sentinel — Database Models (SQLAlchemy 2.0 style)

All tables live in the `sentinel` schema inside `defaultdb` (Aiven free tier).

Phase 1 tables:  companies, filings, raw_documents
Phase 2 stubs:   chunks, embeddings (vectors added when pgvector extension is enabled)
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# All tables go into the `sentinel` schema
SCHEMA = "sentinel"
metadata = MetaData(schema=SCHEMA)


class Base(DeclarativeBase):
    metadata = metadata


# ── Enums ─────────────────────────────────────────────────────────────────────

class FilingType(str, enum.Enum):
    annual_report = "annual_report"
    quarterly_results = "quarterly_results"
    earnings_transcript = "earnings_transcript"


class Sector(str, enum.Enum):
    it = "IT"
    banking = "Banking"
    finance = "Finance"
    fmcg = "FMCG"
    auto = "Auto"
    pharma = "Pharma"
    cement = "Cement"
    energy = "Energy"
    infrastructure = "Infrastructure"
    consumer = "Consumer"
    other = "Other"


# ── Phase 1 tables ────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    bse_code: Mapped[str | None] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str | None] = mapped_column(Enum(Sector, schema=SCHEMA))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filings: Mapped[list[Filing]] = relationship("Filing", back_populates="company")

    def __repr__(self) -> str:
        return f"<Company {self.ticker}>"


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.companies.id"), nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(Enum(FilingType, schema=SCHEMA), nullable=False)
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "2024-25"
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(10))               # "NSE" or "BSE"
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship("Company", back_populates="filings")
    raw_document: Mapped[RawDocument | None] = relationship("RawDocument", back_populates="filing", uselist=False)

    def __repr__(self) -> str:
        return f"<Filing {self.filing_type} {self.fiscal_year}>"


class RawDocument(Base):
    __tablename__ = "raw_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.filings.id"), unique=True, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filing: Mapped[Filing] = relationship("Filing", back_populates="raw_document")

    def __repr__(self) -> str:
        return f"<RawDocument filing_id={self.filing_id} pages={self.page_count}>"
