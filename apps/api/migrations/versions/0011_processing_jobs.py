"""R008 Spatial Processing & Durable Jobs schema with RLS and derived source lineage."""

from __future__ import annotations

from alembic import op

revision = "0011_processing_jobs"
down_revision = "0010_saved_queries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA processing")
    op.execute("GRANT USAGE ON SCHEMA processing TO openvietgis_runtime")

    op.execute("""
        CREATE TABLE processing.jobs (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            algorithm_id varchar(64) NOT NULL,
            operation_id varchar(128) NOT NULL,
            status varchar(32) NOT NULL,
            actor_type varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            input_refs jsonb NOT NULL,
            parameters jsonb NOT NULL,
            output_name varchar(200) NOT NULL,
            output_crs integer NOT NULL,
            engine_version varchar(128) NOT NULL,
            attempt_count integer NOT NULL DEFAULT 1,
            output_source_id uuid NULL,
            output_layer_id uuid NULL,
            output_content_revision varchar(64) NULL,
            feature_count integer NULL,
            error_code varchar(64) NULL,
            error_message varchar(500) NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            completed_at timestamptz NULL,
            CONSTRAINT uq_processing_jobs_op UNIQUE (organization_id, project_id, operation_id),
            CONSTRAINT ck_processing_algo CHECK (algorithm_id IN ('buffer', 'clip', 'dissolve')),
            CONSTRAINT ck_processing_status CHECK (
                status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
            ),
            CONSTRAINT ck_processing_crs CHECK (output_crs IN (4326, 3857, 4756, 5899)),
            CONSTRAINT fk_processing_project
                FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("ALTER TABLE processing.jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE processing.jobs FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY processing_jobs_project_scope ON processing.jobs
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
    op.execute("GRANT SELECT, INSERT, UPDATE ON processing.jobs TO openvietgis_runtime")

    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT ck_source_kind")
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT ck_source_kind CHECK (
            (kind = 'reference_fixture' AND source_asset_id IS NULL)
            OR (kind = 'imported_file' AND source_asset_id IS NOT NULL)
            OR (kind = 'derived_processing' AND source_asset_id IS NULL)
        )
    """)
    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT ck_source_ready_metadata")
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT ck_source_ready_metadata CHECK (COALESCE(
            CASE WHEN validation_state='ready' THEN
                source_crs IN (4326,3857,4756,5899)
                AND stored_crs IN (4326,3857,4756,5899)
                AND (kind IN ('imported_file', 'derived_processing') OR source_crs = stored_crs)
                AND schema_state='known'
                AND geometry_family IN ('Point','LineString','Polygon')
                AND dimensions='XY'
                AND feature_count_state='known'
                AND extent_state=CASE WHEN feature_count=0 THEN 'empty' ELSE 'available' END
            ELSE extent_state='unavailable' END, false
        ))
    """)
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_revisions")
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_resource")
    op.execute("""
        ALTER TABLE spatial.catalog_changes ADD CONSTRAINT ck_change_resource CHECK (COALESCE(
            (resource_type='data_source' AND source_id=resource_id AND layer_id IS NULL
                AND operation IN (
                    'register_source','import_source','processing_publish','edit_features',
                    'update_source','correct_source_crs','retire_source','refresh_reference_fixture'
                )
            ) OR (
                resource_type='layer' AND layer_id=resource_id AND source_id IS NULL
                AND operation IN ('create_layer','rename_layer','retire_layer')
            ), false
        ))
    """)
    op.execute("""
        ALTER TABLE spatial.catalog_changes ADD CONSTRAINT ck_change_revisions CHECK (COALESCE(
            spatial.valid_revision(new_revision, resource_type='data_source')
            AND (prior_revision IS NULL OR
                spatial.valid_revision(prior_revision, resource_type='data_source'))
            AND (prior_revision IS NULL) = (
                operation IN (
                    'register_source','import_source','processing_publish','create_layer'
                )
            )
            AND CASE WHEN resource_type='data_source' THEN
                (new_revision->>'catalog_revision')::numeric =
                    COALESCE((prior_revision->>'catalog_revision')::numeric, 0) + 1
                AND (
                    operation NOT IN ('update_source','retire_source') OR (
                        new_revision->>'content_revision' = prior_revision->>'content_revision'
                        AND new_revision->>'schema_revision' =
                            prior_revision->>'schema_revision'
                    )
                )
            ELSE (new_revision->>'layer_revision')::numeric =
                COALESCE((prior_revision->>'layer_revision')::numeric, 0) + 1 END,
            false
        ))
    """)


def downgrade() -> None:
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.execute("DROP TABLE processing.jobs")
    op.execute("DROP SCHEMA processing")
    op.execute("""
        DELETE FROM spatial.catalog_changes
        WHERE operation = 'processing_publish'
           OR source_id IN (SELECT id FROM spatial.data_sources WHERE kind = 'derived_processing')
           OR layer_id IN (
               SELECT id FROM spatial.layers
               WHERE source_id IN (
                   SELECT id FROM spatial.data_sources WHERE kind = 'derived_processing'
               )
           )
    """)
    op.execute("""
        DELETE FROM spatial.layers
        WHERE source_id IN (SELECT id FROM spatial.data_sources WHERE kind = 'derived_processing')
    """)
    op.execute("""
        DELETE FROM spatial.reference_features
        WHERE source_id IN (SELECT id FROM spatial.data_sources WHERE kind = 'derived_processing')
    """)
    op.execute("""
        DELETE FROM spatial.source_fields
        WHERE source_id IN (SELECT id FROM spatial.data_sources WHERE kind = 'derived_processing')
    """)
    op.execute("DELETE FROM spatial.data_sources WHERE kind = 'derived_processing'")
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_revisions")
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
    op.execute("""
        ALTER TABLE spatial.catalog_changes ADD CONSTRAINT ck_change_revisions CHECK (COALESCE(
            spatial.valid_revision(new_revision, resource_type='data_source')
            AND (prior_revision IS NULL OR
                spatial.valid_revision(prior_revision, resource_type='data_source'))
            AND (prior_revision IS NULL) = (
                operation IN ('register_source','import_source','create_layer')
            )
            AND CASE WHEN resource_type='data_source' THEN
                (new_revision->>'catalog_revision')::numeric =
                    COALESCE((prior_revision->>'catalog_revision')::numeric, 0) + 1
                AND (
                    operation NOT IN ('update_source','retire_source') OR (
                        new_revision->>'content_revision' = prior_revision->>'content_revision'
                        AND new_revision->>'schema_revision' =
                            prior_revision->>'schema_revision'
                    )
                )
            ELSE (new_revision->>'layer_revision')::numeric =
                COALESCE((prior_revision->>'layer_revision')::numeric, 0) + 1 END,
            false
        ))
    """)
    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT ck_source_ready_metadata")
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT ck_source_ready_metadata CHECK (COALESCE(
            CASE WHEN validation_state='ready' THEN
                source_crs IN (4326,3857,4756,5899)
                AND stored_crs IN (4326,3857,4756,5899)
                AND (kind = 'imported_file' OR source_crs = stored_crs)
                AND schema_state='known'
                AND geometry_family IN ('Point','LineString','Polygon')
                AND dimensions='XY'
                AND feature_count_state='known'
                AND extent_state=CASE WHEN feature_count=0 THEN 'empty' ELSE 'available' END
            ELSE extent_state='unavailable' END, false
        ))
    """)
    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT ck_source_kind")
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT ck_source_kind CHECK (
            (kind = 'reference_fixture' AND source_asset_id IS NULL)
            OR (kind = 'imported_file' AND source_asset_id IS NOT NULL)
        )
    """)
