"""
Sentinel — Database Models (SQLAlchemy 2.0 style)

All tables live in the `sentinel` schema inside `defaultdb` (Aiven free tier).

Phase 1 tables:  companies, filings, raw_documents
Phase 2 tables:  chunks, embeddings (requires pgvector extension in the DB)
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
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


class FilingType(enum.StrEnum):
    annual_report = "annual_report"
    quarterly_results = "quarterly_results"
    earnings_transcript = "earnings_transcript"


class Sector(enum.StrEnum):
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
    company_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.companies.id"), nullable=False, index=True
    )
    filing_type: Mapped[str] = mapped_column(Enum(FilingType, schema=SCHEMA), nullable=False)
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "2024-25"
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship("Company", back_populates="filings")
    raw_document: Mapped[RawDocument | None] = relationship(
        "RawDocument", back_populates="filing", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Filing {self.filing_type} {self.fiscal_year}>"


class RawDocument(Base):
    __tablename__ = "raw_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filing_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.filings.id"), unique=True, nullable=False
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filing: Mapped[Filing] = relationship("Filing", back_populates="raw_document")
    chunks: Mapped[list[Chunk]] = relationship("Chunk", back_populates="raw_document")

    def __repr__(self) -> str:
        return f"<RawDocument filing_id={self.filing_id} pages={self.page_count}>"


# ── Phase 2 tables ────────────────────────────────────────────────────────────

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_sentinel_chunks_raw_document_id", "raw_document_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_document_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.raw_documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    # Denormalized for query performance — avoids joins when filtering by company/year
    company: Mapped[str | None] = mapped_column(String(20))
    filing_type: Mapped[str | None] = mapped_column(String(50))
    fiscal_year: Mapped[str | None] = mapped_column(String(10))
    is_table: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    char_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    raw_document: Mapped[RawDocument] = relationship("RawDocument", back_populates="chunks")
    embedding: Mapped[Embedding | None] = relationship(
        "Embedding", back_populates="chunk", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Chunk raw_doc={self.raw_document_id} idx={self.chunk_index}>"


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__: ClassVar[dict[str, str]] = {"schema": SCHEMA}  # type: ignore[misc]

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.chunks.id"), unique=True, nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Column is named `vector` in the live DB (matches existing data)
    vector: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunk: Mapped[Chunk] = relationship("Chunk", back_populates="embedding")

    def __repr__(self) -> str:
        return f"<Embedding chunk_id={self.chunk_id} model={self.model_name}>"
