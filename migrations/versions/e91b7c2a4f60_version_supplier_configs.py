"""Allow multiple configuration versions for a supplier.

Revision ID: e91b7c2a4f60
Revises: d38f04e271ab
"""

import sqlalchemy as sa
from alembic import op

revision = "e91b7c2a4f60"
down_revision = "d38f04e271ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_import_configs_supplier_id", table_name="import_configs")
    op.create_index("ix_import_configs_supplier_id", "import_configs", ["supplier_id"])


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM import_configs GROUP BY supplier_id HAVING count(*) > 1)"
        )
    ):
        raise RuntimeError(
            "Cannot restore unique supplier configurations while multiple versions exist"
        )
    op.drop_index("ix_import_configs_supplier_id", table_name="import_configs")
    op.create_index("ix_import_configs_supplier_id", "import_configs", ["supplier_id"], unique=True)
