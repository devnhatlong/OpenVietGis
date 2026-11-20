"""R010 External Sources allowlist and read-only connections with RLS."""

from __future__ import annotations

from alembic import op

revision = "0013_external_sources"
down_revision = "0012_cartography_layouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA external_sources")
    op.execute("GRANT USAGE ON SCHEMA external_sources TO openvietgis_runtime")

    op.execute("""
        CREATE TABLE external_sources.allowlisted_hosts (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            hostname varchar(255) NOT NULL,
            allowed_schemes jsonb NOT NULL,
            allowed_ports jsonb NOT NULL,
            secret_ref_name varchar(128) NULL,
            enabled boolean NOT NULL DEFAULT true,
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_ext_allowlist_host UNIQUE (organization_id, hostname),
            CONSTRAINT fk_ext_allowlist_org
                FOREIGN KEY (organization_id)
                REFERENCES org.organizations(id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE TABLE external_sources.connections (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            allowlist_id uuid NOT NULL,
            name varchar(200) NOT NULL,
            protocol varchar(32) NOT NULL,
            endpoint_url varchar(1000) NOT NULL,
            layer_identifier varchar(200) NOT NULL,
            attribution varchar(300) NOT NULL,
            license_text varchar(300) NOT NULL,
            crs_codes jsonb NOT NULL,
            capabilities jsonb NOT NULL,
            read_only boolean NOT NULL DEFAULT true,
            cache_generation integer NOT NULL DEFAULT 1,
            lifecycle varchar(32) NOT NULL DEFAULT 'active',
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT ck_ext_protocol CHECK (
                protocol IN ('wms', 'wmts_xyz', 'cog_geotiff', 'wfs_ogc_features')
            ),
            CONSTRAINT ck_ext_readonly CHECK (read_only = true),
            CONSTRAINT ck_ext_lifecycle CHECK (lifecycle IN ('active', 'revoked')),
            CONSTRAINT fk_ext_conn_allowlist
                FOREIGN KEY (allowlist_id)
                REFERENCES external_sources.allowlisted_hosts(id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_ext_conn_project
                FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("ALTER TABLE external_sources.allowlisted_hosts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sources.allowlisted_hosts FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ext_allowlist_org_scope ON external_sources.allowlisted_hosts
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

    op.execute("ALTER TABLE external_sources.connections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sources.connections FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ext_connections_project_scope ON external_sources.connections
        FOR ALL TO openvietgis_runtime
        USING (
            organization_id = NULLIF(
                current_setting('openvietgis.organization_id', true), ''
            )::uuid
            AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
        )
        WITH CHECK (
            organization_id = NULLIF(
                current_setting('openvietgis.organization_id', true), ''
            )::uuid
            AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
        )
    """)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON external_sources.allowlisted_hosts TO openvietgis_runtime"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON external_sources.connections TO openvietgis_runtime"
    )


def downgrade() -> None:
    op.execute("DROP TABLE external_sources.connections")
    op.execute("DROP TABLE external_sources.allowlisted_hosts")
    op.execute("DROP SCHEMA external_sources")
