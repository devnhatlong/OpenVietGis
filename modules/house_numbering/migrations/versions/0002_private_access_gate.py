"""Move private household RLS to the generic extension-private transaction namespace."""

from __future__ import annotations

from alembic import op

revision = "hn_0002_private_access_gate"
down_revision = "hn_0001_house_numbering"
branch_labels = None
depends_on = None


def _policy(setting: str, expected: str) -> None:
    op.execute(
        "DROP POLICY IF EXISTS hn_restricted_households_project_scope "
        "ON house_numbering.restricted_households"
    )
    op.execute(f"""
        CREATE POLICY hn_restricted_households_project_scope
        ON house_numbering.restricted_households
        FOR ALL TO openvietgis_runtime
        USING (
            organization_id = NULLIF(
                current_setting('openvietgis.organization_id', true), ''
            )::uuid
            AND project_id = NULLIF(
                current_setting('openvietgis.project_id', true), ''
            )::uuid
            AND current_setting('{setting}', true) = '{expected}'
        )
        WITH CHECK (
            organization_id = NULLIF(
                current_setting('openvietgis.organization_id', true), ''
            )::uuid
            AND project_id = NULLIF(
                current_setting('openvietgis.project_id', true), ''
            )::uuid
            AND current_setting('{setting}', true) = '{expected}'
        )
    """)


def upgrade() -> None:
    _policy("openvietgis.extension_private_access", "house_numbering")


def downgrade() -> None:
    _policy("openvietgis.house_numbering_private_access", "on")
