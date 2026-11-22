"""Scoped append-only extension history and portable-copy receipts.

Legacy rows are captured as a baseline, not reconstructed prior history. Changes
are transactional; no executable module or Core schema migration is installed.
"""

from __future__ import annotations

from alembic import op

revision = "0019_extension_history"
down_revision = "0018_production_ops"
branch_labels = None
depends_on = None


def _statements(sql: str) -> None:
    # PostgreSQL drivers need a separate execute for each DDL statement.
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    # Migration owner only: temporarily remove FORCE during the transactional
    # backfill. No runtime role, session or policy is permitted to bypass RLS.
    for table in ("manifests", "project_activations", "records"):
        op.execute(f"ALTER TABLE extensions.{table} NO FORCE ROW LEVEL SECURITY")
    _statements("""
        ALTER TABLE extensions.manifests
        ADD CONSTRAINT uq_ext_manifest_owner_id UNIQUE (organization_id, id);
        ALTER TABLE extensions.records
        ADD COLUMN manifest_id uuid,
        ADD COLUMN revision integer NOT NULL DEFAULT 1,
        ADD COLUMN link_context jsonb,
        ADD CONSTRAINT uq_ext_record_owner_id UNIQUE (organization_id, project_id, id),
        ADD CONSTRAINT ck_ext_record_revision CHECK (revision >= 1);
        UPDATE extensions.records r
        SET manifest_id = a.manifest_id,
            link_context = CASE WHEN r.linked_layer_id IS NOT NULL
              THEN '{"status":"legacy_unpinned"}'::jsonb ELSE NULL END
        FROM extensions.project_activations a
        WHERE r.organization_id = a.organization_id AND r.project_id = a.project_id
          AND r.extension_key = a.extension_key;
        ALTER TABLE extensions.records
        ALTER COLUMN manifest_id SET NOT NULL,
        ADD CONSTRAINT fk_ext_record_manifest FOREIGN KEY (organization_id, manifest_id)
          REFERENCES extensions.manifests(organization_id, id) ON DELETE RESTRICT;
        ALTER TABLE extensions.project_activations
        ADD CONSTRAINT uq_ext_activation_owner_id UNIQUE (organization_id, project_id, id),
        ADD CONSTRAINT fk_ext_activation_manifest_owner FOREIGN KEY (organization_id, manifest_id)
          REFERENCES extensions.manifests (organization_id, id) ON DELETE RESTRICT
    """)
    _statements("""
        CREATE TABLE extensions.record_revisions (
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            record_id uuid NOT NULL,
            revision integer NOT NULL CHECK (revision >= 1),
            manifest_id uuid NOT NULL,
            entity_name varchar(64) NOT NULL,
            payload jsonb NOT NULL,
            linked_layer_id uuid,
            linked_feature_id varchar(128),
            link_context jsonb,
            actor_id uuid NOT NULL,
            event varchar(32) NOT NULL CHECK (
                event IN ('legacy_baseline','create','update','import')
            ),
            occurred_at timestamptz NOT NULL,
            import_origin jsonb,
            PRIMARY KEY (organization_id, project_id, record_id, revision),
            FOREIGN KEY (organization_id, project_id, record_id)
              REFERENCES extensions.records(organization_id, project_id, id) ON DELETE RESTRICT,
            FOREIGN KEY (organization_id, manifest_id)
              REFERENCES extensions.manifests(organization_id, id) ON DELETE RESTRICT
        );
        INSERT INTO extensions.record_revisions (
            organization_id, project_id, record_id, revision, manifest_id,
            entity_name, payload, linked_layer_id, linked_feature_id, link_context,
            actor_id, event, occurred_at
        )
        SELECT organization_id, project_id, id, revision, manifest_id,
            entity_name, payload, linked_layer_id, linked_feature_id, link_context,
            created_by_actor_id, 'legacy_baseline', created_at
        FROM extensions.records
    """)
    _statements("""
        CREATE TABLE extensions.activation_events (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            activation_id uuid NOT NULL,
            event varchar(32) NOT NULL CHECK (
              event IN ('legacy_baseline','activate','deactivate','transition')
            ),
            previous_manifest_id uuid,
            manifest_id uuid NOT NULL,
            status varchar(32) NOT NULL CHECK (status IN ('active','disabled')),
            actor_id uuid NOT NULL,
            occurred_at timestamptz NOT NULL,
            FOREIGN KEY (organization_id, project_id, activation_id)
              REFERENCES extensions.project_activations(organization_id, project_id, id)
              ON DELETE RESTRICT,
            FOREIGN KEY (organization_id, previous_manifest_id)
              REFERENCES extensions.manifests(organization_id, id) ON DELETE RESTRICT,
            FOREIGN KEY (organization_id, manifest_id)
              REFERENCES extensions.manifests(organization_id, id) ON DELETE RESTRICT
        );
        INSERT INTO extensions.activation_events (
            id, organization_id, project_id, activation_id, event,
            manifest_id, status, actor_id, occurred_at
        )
        SELECT id, organization_id, project_id, id, 'legacy_baseline',
            manifest_id, status, activated_by_actor_id, updated_at
        FROM extensions.project_activations
    """)
    op.execute("""
        CREATE TABLE extensions.import_receipts (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            extension_key varchar(100) NOT NULL,
            manifest_id uuid NOT NULL,
            bundle_sha256 varchar(64) NOT NULL CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
            mappings jsonb NOT NULL,
            actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            UNIQUE (organization_id, project_id, extension_key, bundle_sha256),
            FOREIGN KEY (organization_id, project_id)
              REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            FOREIGN KEY (organization_id, manifest_id)
              REFERENCES extensions.manifests(organization_id, id) ON DELETE RESTRICT
        )
    """)
    for table in ("record_revisions", "activation_events", "import_receipts"):
        op.execute(f"ALTER TABLE extensions.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE extensions.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY ext_{table}_project_scope ON extensions.{table}
            FOR ALL TO openvietgis_runtime
            USING (
                organization_id = NULLIF(
                    current_setting('openvietgis.organization_id', true), '')::uuid
                AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
            )
            WITH CHECK (
                organization_id = NULLIF(
                    current_setting('openvietgis.organization_id', true), '')::uuid
                AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
            )
        """)
        op.execute(f"GRANT SELECT, INSERT ON extensions.{table} TO openvietgis_runtime")
    for table in ("manifests", "project_activations", "records"):
        op.execute(f"ALTER TABLE extensions.{table} FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE UPDATE ON extensions.manifests FROM openvietgis_runtime")
    op.execute("REVOKE UPDATE, DELETE ON extensions.records FROM openvietgis_runtime")
    op.execute("""
        GRANT UPDATE (payload, updated_at, revision, manifest_id, link_context)
          ON extensions.records TO openvietgis_runtime
    """)


def downgrade() -> None:
    # Never discard attributable post-upgrade data/history during ordinary
    # rollback. An operator must restore a verified pre-upgrade backup instead.
    for table in ("record_revisions", "activation_events", "import_receipts"):
        op.execute(f"ALTER TABLE extensions.{table} NO FORCE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM extensions.record_revisions WHERE event <> 'legacy_baseline')
               OR EXISTS (SELECT 1 FROM extensions.activation_events
                          WHERE event <> 'legacy_baseline')
               OR EXISTS (SELECT 1 FROM extensions.import_receipts)
            THEN RAISE EXCEPTION 'R014 history exists; restore pre-upgrade backup for rollback';
            END IF;
        END $$
    """)
    op.execute("DROP TABLE extensions.import_receipts")
    op.execute("DROP TABLE extensions.activation_events")
    op.execute("DROP TABLE extensions.record_revisions")
    _statements("""
        ALTER TABLE extensions.project_activations
          DROP CONSTRAINT fk_ext_activation_manifest_owner,
          DROP CONSTRAINT uq_ext_activation_owner_id;
        ALTER TABLE extensions.records
          DROP CONSTRAINT fk_ext_record_manifest,
          DROP CONSTRAINT uq_ext_record_owner_id,
          DROP COLUMN manifest_id,
          DROP COLUMN revision,
          DROP COLUMN link_context;
        ALTER TABLE extensions.manifests DROP CONSTRAINT uq_ext_manifest_owner_id
    """)
    op.execute("GRANT UPDATE ON extensions.manifests TO openvietgis_runtime")
    op.execute("GRANT UPDATE, DELETE ON extensions.records TO openvietgis_runtime")
