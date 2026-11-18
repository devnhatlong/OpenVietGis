"""Retire the disposable sample after the real tenant slice is accepted.

The downgrade reconstructs the empty disposable structure for historical
migration compatibility. Sample data is intentionally not recoverable from
this migration; all real tenant tables remain untouched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_retire_foundation_sample"
down_revision: str | Sequence[str] | None = "0004_machine_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("sample_records", schema="foundation")


def downgrade() -> None:
    op.create_table(
        "sample_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="foundation",
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON foundation.sample_records TO openvietgis_runtime")
