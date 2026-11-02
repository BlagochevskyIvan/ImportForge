"""Bind new uploads to a supplier and snapshot their CSV configuration.

Revision ID: d38f04e271ab
Revises: 47770e44ab25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d38f04e271ab"
down_revision = "47770e44ab25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep legacy uploads; their ownership cannot safely be inferred.
    op.add_column("source_files", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.add_column("source_files", sa.Column("config_data", postgresql.JSONB(), nullable=True))
    op.create_foreign_key(
        "fk_source_files_supplier_id",
        "source_files",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_source_files_supplier_id", "source_files", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_source_files_supplier_id", table_name="source_files")
    op.drop_constraint("fk_source_files_supplier_id", "source_files", type_="foreignkey")
    op.drop_column("source_files", "config_data")
    op.drop_column("source_files", "supplier_id")
