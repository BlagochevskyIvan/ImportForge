"""Align the schema with validated CRUD and ownership.

Revision ID: c84c8b7d1a20
Revises: b54de5027f26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c84c8b7d1a20"
down_revision = "b54de5027f26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM suppliers")):
        raise RuntimeError(
            "Legacy suppliers have no owner. Prepare an explicit owner backfill before "
            "applying this migration; no rows have been deleted or assigned automatically."
        )
    if connection.scalar(sa.text("SELECT count(*) FROM import_configs")):
        raise RuntimeError("Resolve orphan legacy configs before applying this migration.")

    op.execute("UPDATE users SET email = lower(trim(email))")
    op.alter_column("users", "username", type_=sa.String(64), existing_type=sa.String())
    op.alter_column("users", "email", type_=sa.String(320), existing_type=sa.String())
    op.alter_column(
        "users",
        "created_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.String(),
        postgresql_using="COALESCE(to_timestamp(NULLIF(created_at, '')::double precision), now())",
        nullable=False,
        server_default=sa.func.now(),
    )
    for table in ("users", "suppliers"):
        op.alter_column(
            table,
            "is_active",
            type_=sa.Boolean(),
            existing_type=sa.Integer(),
            postgresql_using="COALESCE(is_active, 1) <> 0",
            nullable=False,
            server_default=sa.text("true"),
        )
    op.alter_column("suppliers", "name", type_=sa.String(200), nullable=False)
    op.alter_column("suppliers", "contact_email", type_=sa.String(320), nullable=False)
    op.add_column("suppliers", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_index("ix_suppliers_user_id", "suppliers", ["user_id"])
    op.create_foreign_key(
        "fk_suppliers_user_id", "suppliers", "users", ["user_id"], ["id"], ondelete="RESTRICT"
    )
    op.alter_column("import_configs", "supplier_id", nullable=False)
    op.drop_index("ix_import_configs_supplier_id", table_name="import_configs")
    op.create_index("ix_import_configs_supplier_id", "import_configs", ["supplier_id"], unique=True)
    op.create_foreign_key(
        "fk_import_configs_supplier_id",
        "import_configs",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "import_configs",
        "config_data",
        type_=postgresql.JSONB(),
        existing_type=sa.String(),
        postgresql_using="config_data::jsonb",
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "import_configs",
        "config_data",
        type_=sa.String(),
        postgresql_using="config_data::text",
        nullable=True,
    )
    op.drop_constraint("fk_import_configs_supplier_id", "import_configs", type_="foreignkey")
    op.drop_index("ix_import_configs_supplier_id", table_name="import_configs")
    op.create_index("ix_import_configs_supplier_id", "import_configs", ["supplier_id"])
    op.alter_column("import_configs", "supplier_id", nullable=True)
    op.drop_constraint("fk_suppliers_user_id", "suppliers", type_="foreignkey")
    op.drop_index("ix_suppliers_user_id", table_name="suppliers")
    op.drop_column("suppliers", "user_id")
    op.alter_column("suppliers", "name", type_=sa.String(), nullable=True)
    op.alter_column("suppliers", "contact_email", type_=sa.String(), nullable=True)
    for table in ("users", "suppliers"):
        op.alter_column(table, "is_active", server_default=None)
        op.alter_column(
            table,
            "is_active",
            type_=sa.Integer(),
            postgresql_using="is_active::integer",
            nullable=True,
        )
    op.alter_column("users", "created_at", server_default=None)
    op.alter_column(
        "users",
        "created_at",
        type_=sa.String(),
        postgresql_using="EXTRACT(EPOCH FROM created_at)::bigint::text",
        nullable=True,
    )
    op.alter_column("users", "username", type_=sa.String())
    op.alter_column("users", "email", type_=sa.String())
