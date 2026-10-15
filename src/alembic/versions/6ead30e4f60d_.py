"""Create the legacy suppliers table required by the next revision.

Revision ID: 6ead30e4f60d
Revises:
Create Date: 2026-09-26 23:24:38.784311

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6ead30e4f60d"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("contact_email", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suppliers_id", "suppliers", ["id"], unique=False)
    op.create_index("ix_suppliers_name", "suppliers", ["name"], unique=True)
    op.create_index("ix_suppliers_contact_email", "suppliers", ["contact_email"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("suppliers")
