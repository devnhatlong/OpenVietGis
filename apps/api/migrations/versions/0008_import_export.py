"""Add R005 import/export durable jobs, immutable source assets, and derived artifacts."""

from __future__ import annotations

from alembic import op

revision = "0008_import_export"
down_revision = "0007_map_workspace"
branch_labels = None
depends_on = None

_SCOPE = (
    "NULLIF(current_setting('openvietgis.organization_id', true), '')::uuid = organization_id"
    " AND NULLIF(current_setting('openvietgis.project_id', true), '')::uuid = project_id"
)

TABLES = ("source_assets", "jobs", "job_attempts", "derived_artifacts")


def upgrade() -> None:
    op.execute("CREATE SCHEMA transfers")
    op.execute("GRANT USAGE ON SCHEMA transfers TO openvietgis_runtime")

    op.execute("""
        CREATE TABLE transfers.source_assets (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            filename varchar(255) NOT NULL,
            detected_format varchar(32) NOT NULL,
            byte_size bigint NOT NULL,
            sha256 varchar(64) NOT NULL,
            storage_key varchar(255) NOT NULL,
            uploaded_by_type varchar(32) NOT NULL,
            uploaded_by_id uuid NOT NULL,
            uploaded_by_display varchar(200) NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_source_assets_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_source_assets_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects (organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_source_asset_format CHECK (
                detected_format IN ('geopackage', 'geojson', 'shapefile_zip')
            ),
            CONSTRAINT ck_source_asset_size CHECK (byte_size > 0),
            CONSTRAINT ck_source_asset_sha256 CHECK (sha256 ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_source_asset_actor CHECK (
                uploaded_by_type IN ('human', 'service_principal')
                AND uploaded_by_display = btrim(uploaded_by_display)
                AND length(uploaded_by_display) >= 1
            )
        )
    """)

    op.execute("""
        CREATE TABLE transfers.jobs (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            operation_id uuid NOT NULL,
            kind varchar(16) NOT NULL,
            request_fingerprint varchar(64) NOT NULL,
            status varchar(32) NOT NULL,
            actor_type varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            actor_display_snapshot varchar(200) NOT NULL,
            credential_id uuid,
            source_asset_id uuid,
            target_source_id uuid,
            target_layer_id uuid,
            source_content_revision varchar(64),
            source_schema_revision varchar(64),
            artifact_id uuid,
            attempt_count integer NOT NULL DEFAULT 0,
            options_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            inspection_report jsonb,
            result_report jsonb,
            error_code varchar(64),
            error_message varchar(500),
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            completed_at timestamptz,
            CONSTRAINT uq_transfer_jobs_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT uq_transfer_jobs_operation
                UNIQUE (organization_id, project_id, operation_id),
            CONSTRAINT fk_transfer_jobs_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects (organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_transfer_jobs_asset
                FOREIGN KEY (organization_id, project_id, source_asset_id)
                REFERENCES transfers.source_assets (organization_id, project_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_transfer_job_kind CHECK (kind IN ('import', 'export')),
            CONSTRAINT ck_transfer_job_fingerprint CHECK (request_fingerprint ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_transfer_job_status CHECK (
                status IN (
                    'accepted', 'queued', 'active', 'awaiting_confirmation',
                    'cancel_requested', 'recoverable_failed', 'succeeded',
                    'failed', 'denied', 'cancelled'
                )
            ),
            CONSTRAINT ck_transfer_job_actor CHECK (
                actor_type IN ('human', 'service_principal')
                AND actor_display_snapshot = btrim(actor_display_snapshot)
                AND length(actor_display_snapshot) >= 1
            ),
            CONSTRAINT ck_transfer_job_attempts CHECK (attempt_count >= 0)
        )
    """)

    op.execute("""
        CREATE TABLE transfers.job_attempts (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            job_id uuid NOT NULL,
            attempt_number integer NOT NULL,
            status varchar(32) NOT NULL,
            actor_type varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            credential_id uuid,
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            error_code varchar(64),
            error_message varchar(500),
            CONSTRAINT uq_job_attempts_number
                UNIQUE (organization_id, project_id, job_id, attempt_number),
            CONSTRAINT fk_job_attempts_job FOREIGN KEY (organization_id, project_id, job_id)
                REFERENCES transfers.jobs (organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_job_attempt_number CHECK (attempt_number >= 1)
        )
    """)

    op.execute("""
        CREATE TABLE transfers.derived_artifacts (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            job_id uuid NOT NULL,
            source_id uuid NOT NULL,
            layer_id uuid NOT NULL,
            source_content_revision varchar(64) NOT NULL,
            source_schema_revision varchar(64) NOT NULL,
            output_format varchar(32) NOT NULL,
            output_crs integer NOT NULL,
            filename varchar(255) NOT NULL,
            content_type varchar(120) NOT NULL,
            byte_size bigint NOT NULL,
            sha256 varchar(64) NOT NULL,
            storage_key varchar(255) NOT NULL,
            comparison_report jsonb NOT NULL,
            created_by_type varchar(32) NOT NULL,
            created_by_id uuid NOT NULL,
            created_by_display varchar(200) NOT NULL,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            state varchar(32) NOT NULL,
            CONSTRAINT uq_derived_artifacts_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_derived_artifacts_job FOREIGN KEY (organization_id, project_id, job_id)
                REFERENCES transfers.jobs (organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_derived_artifacts_source
                FOREIGN KEY (organization_id, project_id, source_id)
                REFERENCES spatial.data_sources (organization_id, project_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_derived_artifacts_layer
                FOREIGN KEY (organization_id, project_id, layer_id)
                REFERENCES spatial.layers (organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_derived_artifact_format CHECK (
                output_format IN ('geopackage', 'geojson', 'shapefile_zip')
            ),
            CONSTRAINT ck_derived_artifact_crs CHECK (output_crs IN (4326, 3857, 4756, 5899)),
            CONSTRAINT ck_derived_artifact_size CHECK (byte_size > 0),
            CONSTRAINT ck_derived_artifact_sha256 CHECK (sha256 ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_derived_artifact_revisions CHECK (
                source_content_revision ~ '^[a-f0-9]{64}$'
                AND source_schema_revision ~ '^[a-f0-9]{64}$'
            ),
            CONSTRAINT ck_derived_artifact_state
                CHECK (state IN ('ready', 'expired', 'unavailable')),
            CONSTRAINT ck_derived_artifact_expiry CHECK (expires_at > created_at)
        )
    """)

    op.execute("""
        CREATE INDEX ix_transfer_jobs_project_created
        ON transfers.jobs (organization_id, project_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX ix_derived_artifacts_project_created
        ON transfers.derived_artifacts (organization_id, project_id, created_at DESC)
    """)

    # Extend spatial.data_sources & spatial.catalog_changes to accept imported_file & import_source
    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT ck_source_kind")
    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT ck_source_ready_metadata")
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT ck_source_ready_metadata CHECK (COALESCE(
            CASE WHEN validation_state='ready' THEN
                source_crs IN (4326,3857,4756,5899)
                AND stored_crs IN (4326,3857,4756,5899)
                AND (kind='imported_file' OR source_crs=stored_crs)
                AND schema_state='known'
                AND geometry_family IN ('Point','LineString','Polygon')
                AND dimensions='XY'
                AND feature_count_state='known'
                AND extent_state=CASE WHEN feature_count=0 THEN 'empty' ELSE 'available' END
            ELSE extent_state='unavailable' END, false
        ))
    """)
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT ck_source_kind CHECK (
            (kind = 'reference_fixture' AND source_asset_id IS NULL)
            OR (kind = 'imported_file' AND source_asset_id IS NOT NULL)
        )
    """)
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT fk_sources_asset
            FOREIGN KEY (organization_id, project_id, source_asset_id)
            REFERENCES transfers.source_assets (organization_id, project_id, id)
            ON DELETE RESTRICT
    """)

    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_resource")
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_revisions")
    op.execute("""
        ALTER TABLE spatial.catalog_changes ADD CONSTRAINT ck_change_resource CHECK (COALESCE(
            (resource_type='data_source' AND source_id=resource_id AND layer_id IS NULL
                AND operation IN (
                    'register_source','import_source','update_source','correct_source_crs',
                    'retire_source','refresh_reference_fixture'
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

    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT ON transfers.{table} TO openvietgis_runtime")
        op.execute(f"ALTER TABLE transfers.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE transfers.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_project_scope ON transfers.{table}
            FOR ALL TO openvietgis_runtime
            USING ({_SCOPE})
            WITH CHECK ({_SCOPE})
        """)

    # Append-only source_assets & job_attempts; bounded updates on jobs & artifacts
    op.execute("""
        GRANT UPDATE (
            status, target_source_id, target_layer_id, source_content_revision,
            source_schema_revision, artifact_id, attempt_count, options_json,
            inspection_report, result_report, error_code, error_message,
            updated_at, completed_at
        ) ON transfers.jobs TO openvietgis_runtime
    """)
    op.execute("""
        GRANT UPDATE (state) ON transfers.derived_artifacts TO openvietgis_runtime
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_revisions")
    op.execute("ALTER TABLE spatial.catalog_changes DROP CONSTRAINT ck_change_resource")
    op.execute("""
        ALTER TABLE spatial.catalog_changes ADD CONSTRAINT ck_change_resource CHECK (COALESCE(
            (resource_type='data_source' AND source_id=resource_id AND layer_id IS NULL
                AND operation IN (
                    'register_source','update_source','correct_source_crs','retire_source',
                    'refresh_reference_fixture'
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
            AND (prior_revision IS NULL) = (operation IN ('register_source','create_layer'))
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
                AND source_crs=stored_crs
                AND schema_state='known'
                AND geometry_family IN ('Point','LineString','Polygon')
                AND dimensions='XY'
                AND feature_count_state='known'
                AND extent_state=CASE WHEN feature_count=0 THEN 'empty' ELSE 'available' END
            ELSE extent_state='unavailable' END, false
        ))
    """)
    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT fk_sources_asset")
    op.execute("ALTER TABLE spatial.data_sources DROP CONSTRAINT ck_source_kind")
    op.execute("""
        ALTER TABLE spatial.data_sources ADD CONSTRAINT ck_source_kind
            CHECK (kind='reference_fixture' AND source_asset_id IS NULL)
    """)
    for table in ("derived_artifacts", "job_attempts", "jobs", "source_assets"):
        op.drop_table(table, schema="transfers")
    op.execute("DROP SCHEMA transfers")
