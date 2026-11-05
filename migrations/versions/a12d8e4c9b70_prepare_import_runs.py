"""Separate immutable run snapshots and results from uploaded files.

Revision ID: a12d8e4c9b70
Revises: 4a3c0f95eccb
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a12d8e4c9b70"
down_revision = "4a3c0f95eccb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM source_files "
            "WHERE status IS NULL OR status NOT IN ('uploaded', 'completed', 'failed'))"
        )
    ):
        raise RuntimeError(
            "Resolve legacy processing/unknown file states before migrating import runs"
        )
    op.add_column(
        "import_configs",
        sa.Column("name", sa.String(200), nullable=False, server_default="Основная"),
    )
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_file_id",
            sa.Uuid(),
            sa.ForeignKey("source_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "config_id", sa.Integer(), sa.ForeignKey("import_configs.id", ondelete="SET NULL")
        ),
        sa.Column("config_name", sa.String(200), nullable=False),
        sa.Column("config_data", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.Text()),
        sa.Column("processing_result", postgresql.JSONB()),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'retry_wait', 'completed', 'failed')",
            name="ck_import_runs_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_import_runs_attempt_count"),
    )
    op.create_index("ix_import_runs_source_file_id", "import_runs", ["source_file_id"])
    op.create_index("ix_import_runs_config_id", "import_runs", ["config_id"])
    op.create_index(
        "uq_import_runs_active_file",
        "import_runs",
        ["source_file_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'processing', 'retry_wait')"),
    )
    runs = sa.table(
        "import_runs",
        sa.column("id", sa.Uuid()),
        sa.column("source_file_id", sa.Uuid()),
        sa.column("config_name", sa.String()),
        sa.column("config_data", postgresql.JSONB()),
        sa.column("status", sa.String()),
        sa.column("error_code", sa.String()),
        sa.column("error_message", sa.Text()),
        sa.column("processing_result", postgresql.JSONB()),
    )
    # Original start/end times and attempt counts were never recorded; leave them unknown.
    records = connection.execute(
        sa.text(
            "SELECT id, config_data, status, processing_result FROM source_files "
            "WHERE status IN ('completed', 'failed')"
        )
    ).mappings()
    for record in records:
        error = (record["processing_result"] or {}).get("error")
        connection.execute(
            runs.insert().values(
                id=uuid4(),
                source_file_id=record["id"],
                config_name="Исторический снимок",
                config_data=record["config_data"] or {},
                status=record["status"],
                processing_result=record["processing_result"],
                error_code="legacy_error" if record["status"] == "failed" else None,
                error_message=error,
            )
        )
    op.drop_column("source_files", "processing_result")
    op.drop_column("source_files", "status")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM import_runs)")):
        raise RuntimeError(
            "Cannot drop import run history; downgrade requires an empty import_runs table"
        )
    op.add_column("source_files", sa.Column("status", sa.String(30), server_default="uploaded"))
    # The old schema had an application default, not a database default.
    op.alter_column("source_files", "status", server_default=None)
    op.add_column("source_files", sa.Column("processing_result", postgresql.JSONB()))
    op.drop_table("import_runs")
    op.drop_column("import_configs", "name")
