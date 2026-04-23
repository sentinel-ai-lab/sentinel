"""
Sentinel — Database Models
Owner: Kishan K (schema) + Data Analyst (filing-specific fields)
Phase: 1 (Week 2)

Tables:
- companies       → ticker, bse_code, name, sector
- filings         → company_id, filing_type, fiscal_year, pdf_url, ingested_at
- raw_documents   → filing_id, page_count, raw_text, file_size_bytes
- chunks          → raw_document_id, chunk_index, text, page_number (Phase 2)
- embeddings      → chunk_id, vector (pgvector) (Phase 2)
"""

from __future__ import annotations

# TODO: implement SQLAlchemy models + Alembic migration in Phase 1, Week 2
