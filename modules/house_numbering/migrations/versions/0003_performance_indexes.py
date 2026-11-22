"""Add House Numbering lookup indexes proven necessary by the 10k/100k benchmark."""

from __future__ import annotations

from alembic import op

revision = "hn_0003_performance_indexes"
down_revision = "hn_0002_private_access_gate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX ix_hn_buildings_route_active
        ON house_numbering.buildings (
            organization_id, project_id, route_id, id
        )
        WHERE state = 'active'
    """)
    op.execute("""
        CREATE INDEX ix_hn_buildings_parcel_active
        ON house_numbering.buildings (
            organization_id, project_id, parcel_ref, id
        )
        WHERE state = 'active' AND parcel_ref IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_hn_numbers_building_current
        ON house_numbering.address_numbers (
            organization_id, project_id, building_id, created_at DESC, id
        )
        WHERE retired_at IS NULL AND building_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_hn_numbers_text_current
        ON house_numbering.address_numbers (
            organization_id, project_id, number_text, building_id
        )
        WHERE retired_at IS NULL
    """)
    op.execute("""
        CREATE INDEX ix_hn_evidence_building_recent
        ON house_numbering.evidence (
            organization_id, project_id, building_id, created_at DESC, id
        )
        WHERE building_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_hn_evidence_number
        ON house_numbering.evidence (
            organization_id, project_id, raw_number, building_id
        )
        WHERE raw_number IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS house_numbering.ix_hn_evidence_number")
    op.execute("DROP INDEX IF EXISTS house_numbering.ix_hn_evidence_building_recent")
    op.execute("DROP INDEX IF EXISTS house_numbering.ix_hn_numbers_text_current")
    op.execute("DROP INDEX IF EXISTS house_numbering.ix_hn_numbers_building_current")
    op.execute("DROP INDEX IF EXISTS house_numbering.ix_hn_buildings_parcel_active")
    op.execute("DROP INDEX IF EXISTS house_numbering.ix_hn_buildings_route_active")
