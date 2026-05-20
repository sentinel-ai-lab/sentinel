"""sync_live_schema

Revision ID: 8164c7ff610f
Revises: 69ae39eab224
Create Date: 2026-05-17 23:44:29.849375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8164c7ff610f'
down_revision: Union[str, Sequence[str], None] = '69ae39eab224'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop source column from filings if it still exists (idempotent)
    op.execute("ALTER TABLE sentinel.filings DROP COLUMN IF EXISTS source")
    # Add is_scanned to raw_documents if it does not exist yet (idempotent)
    op.execute(
        "ALTER TABLE sentinel.raw_documents "
        "ADD COLUMN IF NOT EXISTS is_scanned BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE sentinel.raw_documents DROP COLUMN IF EXISTS is_scanned")
    op.execute(
        "ALTER TABLE sentinel.filings "
        "ADD COLUMN IF NOT EXISTS source VARCHAR(10)"
    )
