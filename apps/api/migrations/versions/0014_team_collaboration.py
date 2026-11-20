"""R011 Team Collaboration activity feed, post-commit change reviews, and threaded comments."""

from __future__ import annotations

from alembic import op

revision = "0014_team_collaboration"
down_revision = "0013_external_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA collaboration")
    op.execute("GRANT USAGE ON SCHEMA collaboration TO openvietgis_runtime")

    op.execute("""
        CREATE OR REPLACE FUNCTION collaboration.reject_activity_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'project activity rows are append-only';
        END;
        $$
    """)

    op.execute("""
        CREATE TABLE collaboration.activities (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            actor_type varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            actor_display varchar(200) NOT NULL,
            event_kind varchar(64) NOT NULL,
            resource_type varchar(64) NOT NULL,
            resource_id uuid NOT NULL,
            revision_ref varchar(64) NULL,
            summary varchar(500) NOT NULL,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL,
            CONSTRAINT fk_collab_act_project
                FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE TABLE collaboration.change_reviews (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            source_id uuid NOT NULL,
            changeset_id uuid NOT NULL,
            content_revision varchar(64) NOT NULL,
            requested_by_actor_id uuid NOT NULL,
            assignee_user_id uuid NOT NULL,
            status varchar(32) NOT NULL DEFAULT 'pending',
            decision_note varchar(500) NOT NULL DEFAULT '',
            decided_by_actor_id uuid NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            decided_at timestamptz NULL,
            CONSTRAINT ck_collab_review_status CHECK (
                status IN ('pending', 'approved', 'changes_requested')
            ),
            CONSTRAINT fk_collab_rev_changeset
                FOREIGN KEY (organization_id, project_id, changeset_id)
                REFERENCES editing.changesets(organization_id, project_id, id)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE TABLE collaboration.review_comments (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            review_id uuid NOT NULL,
            changeset_id uuid NOT NULL,
            content_revision varchar(64) NOT NULL,
            feature_id varchar(128) NULL,
            body varchar(2000) NOT NULL,
            author_actor_id uuid NOT NULL,
            author_display varchar(200) NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT fk_collab_comment_review
                FOREIGN KEY (review_id)
                REFERENCES collaboration.change_reviews(id)
                ON DELETE RESTRICT
        )
    """)

    for table in ("activities", "change_reviews", "review_comments"):
        op.execute(f"ALTER TABLE collaboration.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE collaboration.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY collab_{table}_project_scope ON collaboration.{table}
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
        CREATE TRIGGER trg_collab_activities_immutable
        BEFORE UPDATE OR DELETE ON collaboration.activities
        FOR EACH ROW EXECUTE FUNCTION collaboration.reject_activity_mutation()
    """)
    op.execute("GRANT SELECT, INSERT ON collaboration.activities TO openvietgis_runtime")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON collaboration.change_reviews TO openvietgis_runtime"
    )
    op.execute("GRANT SELECT, INSERT ON collaboration.review_comments TO openvietgis_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE collaboration.review_comments")
    op.execute("DROP TABLE collaboration.change_reviews")
    op.execute("DROP TABLE collaboration.activities")
    op.execute("DROP FUNCTION collaboration.reject_activity_mutation()")
    op.execute("DROP SCHEMA collaboration")
