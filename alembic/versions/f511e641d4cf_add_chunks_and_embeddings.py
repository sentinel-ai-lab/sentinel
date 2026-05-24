"""add_chunks_and_embeddings

Revision ID: f511e641d4cf
Revises: 8164c7ff610f
Create Date: 2026-05-21

Adds Phase 2 tables sentinel.chunks and sentinel.embeddings (idempotent).

The tables may already exist from a previous manual creation; this migration
uses CREATE TABLE IF NOT EXISTS so it is safe to run in either case.

sentinel.chunks has denormalized company/filing_type/fiscal_year columns for
query performance (avoids joins when searching by company or year).

sentinel.embeddings uses the column name `vector` (matches the live DB).

Requires pgvector.  Enable via Aiven Console → Service → Extensions → "vector",
or run:  CREATE EXTENSION IF NOT EXISTS vector;
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f511e641d4cf"
down_revision: Union[str, Sequence[str], None] = "8164c7ff610f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Use raw SQL so CREATE TABLE IF NOT EXISTS is idempotent.
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS sentinel.chunks (
            id             SERIAL      NOT NULL,
            raw_document_id INTEGER    NOT NULL,
            chunk_index    INTEGER     NOT NULL,
            text           TEXT        NOT NULL,
            page_number    INTEGER,
            company        VARCHAR(20),
            filing_type    VARCHAR(50),
            fiscal_year    VARCHAR(10),
            is_table       BOOLEAN     NOT NULL DEFAULT false,
            char_count     INTEGER,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY (raw_document_id) REFERENCES sentinel.raw_documents(id)
        )
    """)
    op.execute(
        "ALTER TABLE sentinel.chunks ADD COLUMN IF NOT EXISTS char_count INTEGER"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sentinel_chunks_raw_document_id "
        "ON sentinel.chunks (raw_document_id)"
    )

    op.execute(f"""
        CREATE TABLE IF NOT EXISTS sentinel.embeddings (
            id          SERIAL       NOT NULL,
            chunk_id    INTEGER      NOT NULL,
            model_name  VARCHAR(100) NOT NULL,
            vector      vector({EMBEDDING_DIM}) NOT NULL,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            UNIQUE (chunk_id),
            FOREIGN KEY (chunk_id) REFERENCES sentinel.chunks(id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sentinel_embeddings_ivfflat "
        f"ON sentinel.embeddings "
        f"USING ivfflat (vector vector_cosine_ops) "
        f"WITH (lists = 100)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS sentinel.ix_sentinel_embeddings_ivfflat")
    op.execute("DROP TABLE IF EXISTS sentinel.embeddings")
    op.execute("DROP INDEX IF EXISTS sentinel.ix_sentinel_chunks_raw_document_id")
    op.execute("DROP TABLE IF EXISTS sentinel.chunks")
