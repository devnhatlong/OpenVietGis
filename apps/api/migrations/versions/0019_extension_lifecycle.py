"""R014 extension lifecycle, UI contributions and optimistic record revisions."""

from __future__ import annotations

from alembic import op

revision = "0019_extension_lifecycle"
down_revision = "0018_production_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE extensions.manifests
        ADD COLUMN ui_contributions jsonb NOT NULL DEFAULT '[]'::jsonb
    """)
    op.execute("""
        ALTER TABLE extensions.project_activations
        ADD COLUMN revision bigint NOT NULL DEFAULT 1,
        ADD COLUMN disabled_by_actor_id uuid NULL,
        ADD COLUMN disabled_at timestamptz NULL,
        ADD CONSTRAINT ck_ext_activation_revision CHECK (revision > 0)
    """)
    op.execute("""
        ALTER TABLE extensions.records
        ADD COLUMN revision bigint NOT NULL DEFAULT 1,
        ADD COLUMN operation_id uuid NULL,
        ADD COLUMN updated_by_actor_id uuid NULL,
        ADD CONSTRAINT ck_ext_record_revision CHECK (revision > 0)
    """)
    op.execute("""
        UPDATE extensions.records
        SET updated_by_actor_id = created_by_actor_id
        WHERE updated_by_actor_id IS NULL
    """)
    op.execute("""
        ALTER TABLE extensions.records
        ALTER COLUMN updated_by_actor_id SET NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_ext_record_operation
        ON extensions.records (organization_id, project_id, extension_key, operation_id)
        WHERE operation_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS extensions.uq_ext_record_operation")
    op.execute("""
        ALTER TABLE extensions.records
        DROP CONSTRAINT IF EXISTS ck_ext_record_revision,
        DROP COLUMN updated_by_actor_id,
        DROP COLUMN operation_id,
        DROP COLUMN revision
    """)
    op.execute("""
        ALTER TABLE extensions.project_activations
        DROP CONSTRAINT IF EXISTS ck_ext_activation_revision,
        DROP COLUMN disabled_at,
        DROP COLUMN disabled_by_actor_id,
        DROP COLUMN revision
    """)
    op.execute("ALTER TABLE extensions.manifests DROP COLUMN ui_contributions")
