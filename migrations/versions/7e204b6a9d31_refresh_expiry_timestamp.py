"""Use a timezone-aware refresh expiry and an indexed unique token hash.

Revision ID: 7e204b6a9d31
Revises: 50f66e3c7ef9
"""

import sqlalchemy as sa
from alembic import op

revision = "7e204b6a9d31"
down_revision = "50f66e3c7ef9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "exp_time",
        existing_type=sa.String(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="NULLIF(exp_time, '')::timestamptz",
    )
    op.create_index("ix_users_ref_hash", "users", ["ref_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_ref_hash", table_name="users")
    op.alter_column(
        "users",
        "exp_time",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.String(),
        postgresql_using="exp_time::text",
    )
