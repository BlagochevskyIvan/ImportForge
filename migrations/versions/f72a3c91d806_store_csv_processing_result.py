"""Store processing statistics and artifact keys without changing old uploads."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f72a3c91d806"
down_revision = "e91b7c2a4f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_files", sa.Column("processing_result", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_files", "processing_result")
