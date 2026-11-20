"""R009 Cartography styles, print layouts, and immutable print export manifests."""

from __future__ import annotations

from alembic import op

revision = "0012_cartography_layouts"
down_revision = "0011_processing_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA cartography")
    op.execute("GRANT USAGE ON SCHEMA cartography TO openvietgis_runtime")

    op.execute("""
        CREATE OR REPLACE FUNCTION cartography.reject_export_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'cartography print exports are immutable';
        END;
        $$
    """)

    op.execute("""
        CREATE TABLE cartography.layer_styles (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            layer_id uuid NOT NULL,
            mode varchar(32) NOT NULL,
            style_spec jsonb NOT NULL,
            label_field varchar(64) NULL,
            legend_items jsonb NOT NULL,
            revision integer NOT NULL DEFAULT 1,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_cartography_layer_style UNIQUE (organization_id, project_id, layer_id),
            CONSTRAINT ck_cartography_style_mode CHECK (
                mode IN ('single', 'categorical', 'range')
            ),
            CONSTRAINT fk_cartography_style_layer
                FOREIGN KEY (organization_id, project_id, layer_id)
                REFERENCES spatial.layers(organization_id, project_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE TABLE cartography.print_layouts (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            name varchar(200) NOT NULL,
            title varchar(200) NOT NULL,
            paper_size varchar(8) NOT NULL,
            orientation varchar(16) NOT NULL,
            crs_code integer NOT NULL,
            attribution varchar(300) NOT NULL,
            show_north_arrow boolean NOT NULL DEFAULT true,
            show_scale_bar boolean NOT NULL DEFAULT true,
            show_legend boolean NOT NULL DEFAULT true,
            layer_ids jsonb NOT NULL,
            extent jsonb NULL,
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT ck_layout_paper CHECK (paper_size IN ('A4', 'A3')),
            CONSTRAINT ck_layout_orient CHECK (orientation IN ('portrait', 'landscape')),
            CONSTRAINT ck_layout_crs CHECK (crs_code IN (4326, 3857, 4756, 5899)),
            CONSTRAINT fk_layout_project
                FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE TABLE cartography.print_exports (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            layout_id uuid NOT NULL,
            output_format varchar(8) NOT NULL,
            dpi integer NOT NULL,
            scale_denominator integer NOT NULL,
            scale_accuracy_note varchar(300) NOT NULL,
            revision_manifest jsonb NOT NULL,
            storage_key varchar(500) NOT NULL,
            sha256 varchar(64) NOT NULL,
            byte_size bigint NOT NULL,
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT ck_export_format CHECK (output_format IN ('png', 'pdf')),
            CONSTRAINT ck_export_dpi CHECK (dpi IN (150, 300)),
            CONSTRAINT ck_export_sha256 CHECK (sha256 ~ '^[a-f0-9]{64}$'),
            CONSTRAINT fk_export_layout
                FOREIGN KEY (layout_id)
                REFERENCES cartography.print_layouts(id)
                ON DELETE RESTRICT
        )
    """)

    for table in ("layer_styles", "print_layouts", "print_exports"):
        op.execute(f"ALTER TABLE cartography.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE cartography.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY cartography_{table}_project_scope ON cartography.{table}
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

    op.execute("""
        CREATE TRIGGER trg_cartography_exports_immutable
        BEFORE UPDATE OR DELETE ON cartography.print_exports
        FOR EACH ROW EXECUTE FUNCTION cartography.reject_export_mutation()
    """)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON cartography.layer_styles TO openvietgis_runtime"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON cartography.print_layouts TO openvietgis_runtime"
    )
    op.execute("GRANT SELECT, INSERT ON cartography.print_exports TO openvietgis_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE cartography.print_exports")
    op.execute("DROP TABLE cartography.print_layouts")
    op.execute("DROP TABLE cartography.layer_styles")
    op.execute("DROP FUNCTION cartography.reject_export_mutation()")
    op.execute("DROP SCHEMA cartography")
