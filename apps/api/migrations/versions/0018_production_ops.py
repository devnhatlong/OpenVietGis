"""R015 Production Operations & optional non-destructive organization entitlements."""

from __future__ import annotations

from alembic import op

revision = "0018_production_ops"
down_revision = "0017_extension_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA ops")
    op.execute("GRANT USAGE ON SCHEMA ops TO openvietgis_runtime")

    op.execute("""
        CREATE TABLE ops.organization_entitlements (
            organization_id uuid PRIMARY KEY,
            deployment_profile varchar(32) NOT NULL DEFAULT 'self_host_team',
            plan_tier varchar(32) NOT NULL DEFAULT 'self_host_community',
            max_projects integer NOT NULL DEFAULT 100,
            max_storage_mb integer NOT NULL DEFAULT 10240,
            features_enabled jsonb NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT ck_ops_profile CHECK (
                deployment_profile IN ('self_host_team', 'cloud_saas', 'enterprise_private')
            ),
            CONSTRAINT ck_ops_plan CHECK (
                plan_tier IN ('self_host_community', 'team_standard', 'enterprise')
            ),
            CONSTRAINT ck_ops_limits CHECK (max_projects >= 1 AND max_storage_mb >= 64),
            CONSTRAINT fk_ops_ent_org
                FOREIGN KEY (organization_id)
                REFERENCES org.organizations(id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("ALTER TABLE ops.organization_entitlements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ops.organization_entitlements FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ops_entitlements_org_scope ON ops.organization_entitlements
        FOR ALL TO openvietgis_runtime
        USING (
            organization_id = NULLIF(
                current_setting('openvietgis.organization_id', true), ''
            )::uuid
        )
        WITH CHECK (
            organization_id = NULLIF(
                current_setting('openvietgis.organization_id', true), ''
            )::uuid
        )
    """)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON ops.organization_entitlements TO openvietgis_runtime"
    )


def downgrade() -> None:
    op.execute("DROP TABLE ops.organization_entitlements")
    op.execute("DROP SCHEMA ops")
