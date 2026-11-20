"""R012 CAD Interoperability (2D DXF) & Precision conversions schema with RLS."""

from __future__ import annotations

from alembic import op

revision = "0015_cad_precision"
down_revision = "0014_team_collaboration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA cad")
    op.execute("GRANT USAGE ON SCHEMA cad TO openvietgis_runtime")

    op.execute("""
        CREATE TABLE cad.conversions (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            direction varchar(16) NOT NULL,
            cad_format varchar(16) NOT NULL,
            filename varchar(255) NOT NULL,
            units varchar(16) NOT NULL,
            crs_code integer NOT NULL,
            status varchar(32) NOT NULL,
            entity_summary jsonb NOT NULL,
            loss_report jsonb NOT NULL,
            storage_key varchar(500) NOT NULL,
            sha256 varchar(64) NOT NULL,
            byte_size bigint NOT NULL,
            source_id uuid NULL,
            layer_id uuid NULL,
            content_revision varchar(64) NULL,
            actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT ck_cad_direction CHECK (direction IN ('import', 'export')),
            CONSTRAINT ck_cad_format CHECK (cad_format IN ('dxf', 'dwg')),
            CONSTRAINT ck_cad_units CHECK (units IN ('meter', 'centimeter', 'millimeter')),
            CONSTRAINT ck_cad_status CHECK (status IN ('succeeded', 'rejected')),
            CONSTRAINT fk_cad_project
                FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("ALTER TABLE cad.conversions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cad.conversions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY cad_conversions_project_scope ON cad.conversions
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
    op.execute("GRANT SELECT, INSERT ON cad.conversions TO openvietgis_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE cad.conversions")
    op.execute("DROP SCHEMA cad")
