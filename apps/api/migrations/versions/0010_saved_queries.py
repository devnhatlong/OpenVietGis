"""R007 Attribute & Spatial Query saved definitions with RLS."""

from __future__ import annotations

from alembic import op

revision = "0010_saved_queries"
down_revision = "0009_editing_changesets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA queries")
    op.execute("GRANT USAGE ON SCHEMA queries TO openvietgis_runtime")

    op.execute("""
        CREATE TABLE queries.saved_queries (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            layer_id uuid NOT NULL,
            name varchar(200) NOT NULL,
            description varchar(500) NOT NULL DEFAULT '',
            attribute_filter jsonb NULL,
            spatial_filter jsonb NULL,
            sort_field varchar(64) NULL,
            sort_direction varchar(4) NOT NULL DEFAULT 'asc',
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT ck_saved_query_name CHECK (name = btrim(name) AND length(name) >= 1),
            CONSTRAINT ck_saved_query_dir CHECK (sort_direction IN ('asc', 'desc')),
            CONSTRAINT fk_saved_queries_layer
                FOREIGN KEY (organization_id, project_id, layer_id)
                REFERENCES spatial.layers(organization_id, project_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("ALTER TABLE queries.saved_queries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE queries.saved_queries FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY queries_saved_project_scope ON queries.saved_queries
        FOR ALL TO openvietgis_runtime
        USING (
            organization_id = NULLIF(current_setting('openvietgis.organization_id', true), '')::uuid
            AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
        )
        WITH CHECK (
            organization_id = NULLIF(current_setting('openvietgis.organization_id', true), '')::uuid
            AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
        )
    """)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON queries.saved_queries TO openvietgis_runtime"
    )


def downgrade() -> None:
    op.execute("DROP TABLE queries.saved_queries")
    op.execute("DROP SCHEMA queries")
