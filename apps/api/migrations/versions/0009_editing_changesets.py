"""R006 Editing & Change History schema with RLS and immutable changesets."""

from __future__ import annotations

from alembic import op

revision = "0009_editing_changesets"
down_revision = "0008_import_export"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA editing")
    op.execute("GRANT USAGE ON SCHEMA editing TO openvietgis_runtime")

    op.execute("""
        CREATE OR REPLACE FUNCTION editing.reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'editing audit rows are append-only';
        END;
        $$
    """)

    op.execute("""
        CREATE TABLE editing.changesets (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            source_id uuid NOT NULL,
            actor_type varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            actor_display_snapshot varchar(200) NOT NULL,
            operation_id varchar(128) NOT NULL,
            base_content_revision varchar(64) NOT NULL,
            resulting_content_revision varchar(64) NOT NULL,
            base_catalog_revision bigint NOT NULL,
            resulting_catalog_revision bigint NOT NULL,
            summary varchar(500) NOT NULL,
            status varchar(32) NOT NULL,
            operation_count integer NOT NULL,
            audit_event_id uuid NOT NULL,
            reverted_from_changeset_id uuid NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_editing_changesets_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT uq_editing_changesets_op UNIQUE (
                organization_id, project_id, source_id, operation_id
            ),
            CONSTRAINT ck_editing_changeset_status CHECK (status IN ('committed', 'reverted')),
            CONSTRAINT ck_editing_changeset_revs CHECK (
                base_content_revision ~ '^[a-f0-9]{64}$'
                AND resulting_content_revision ~ '^[a-f0-9]{64}$'
                AND base_catalog_revision >= 1
                AND resulting_catalog_revision = base_catalog_revision + 1
            ),
            CONSTRAINT ck_editing_changeset_count CHECK (operation_count >= 1),
            CONSTRAINT fk_editing_changesets_source
                FOREIGN KEY (organization_id, project_id, source_id)
                REFERENCES spatial.data_sources(organization_id, project_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_editing_changesets_audit
                FOREIGN KEY (organization_id, audit_event_id)
                REFERENCES audit.audit_events(organization_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE TABLE editing.changeset_operations (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            changeset_id uuid NOT NULL,
            ordinal integer NOT NULL,
            op_type varchar(16) NOT NULL,
            feature_id varchar(128) NOT NULL,
            before_geometry_wkb bytea NULL,
            after_geometry_wkb bytea NULL,
            before_properties jsonb NULL,
            after_properties jsonb NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_editing_op_ord UNIQUE (changeset_id, ordinal),
            CONSTRAINT ck_editing_op_type CHECK (op_type IN ('create', 'update', 'delete')),
            CONSTRAINT ck_editing_op_ord CHECK (ordinal >= 0),
            CONSTRAINT fk_editing_ops_changeset
                FOREIGN KEY (organization_id, project_id, changeset_id)
                REFERENCES editing.changesets(organization_id, project_id, id)
                ON DELETE RESTRICT
        )
    """)

    for table in ("changesets", "changeset_operations"):
        op.execute(f"ALTER TABLE editing.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE editing.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY editing_{table}_project_scope ON editing.{table}
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
        op.execute(f"""
            CREATE TRIGGER trg_editing_{table}_immutable
            BEFORE UPDATE OR DELETE ON editing.{table}
            FOR EACH ROW EXECUTE FUNCTION editing.reject_mutation()
        """)
        op.execute(f"GRANT SELECT, INSERT ON editing.{table} TO openvietgis_runtime")

    op.execute("GRANT DELETE ON spatial.reference_features TO openvietgis_runtime")
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_resource")
    op.execute("""
        ALTER TABLE spatial.catalog_changes ADD CONSTRAINT ck_change_resource CHECK (COALESCE(
            (resource_type='data_source' AND source_id=resource_id AND layer_id IS NULL
                AND operation IN (
                    'register_source','import_source','edit_features','update_source',
                    'correct_source_crs','retire_source','refresh_reference_fixture'
                )
            ) OR (
                resource_type='layer' AND layer_id=resource_id AND source_id IS NULL
                AND operation IN ('create_layer','rename_layer','retire_layer')
            ), false
        ))
    """)


def downgrade() -> None:
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.execute("DROP TABLE editing.changeset_operations")
    op.execute("DROP TABLE editing.changesets")
    op.execute("DROP FUNCTION editing.reject_mutation()")
    op.execute("DROP SCHEMA editing")
    op.execute("REVOKE DELETE ON spatial.reference_features FROM openvietgis_runtime")
    op.execute("DELETE FROM spatial.catalog_changes WHERE operation = 'edit_features'")
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_resource")
    op.execute("""
        ALTER TABLE spatial.catalog_changes ADD CONSTRAINT ck_change_resource CHECK (COALESCE(
            (resource_type='data_source' AND source_id=resource_id AND layer_id IS NULL
                AND operation IN (
                    'register_source','import_source','update_source',
                    'correct_source_crs','retire_source','refresh_reference_fixture'
                )
            ) OR (
                resource_type='layer' AND layer_id=resource_id AND source_id IS NULL
                AND operation IN ('create_layer','rename_layer','retire_layer')
            ), false
        ))
    """)
