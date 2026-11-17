"""Create identity, tenancy, audit, and installation-state foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_identity_tenant_core"
down_revision: str | Sequence[str] | None = "0001_foundation_sample"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    for schema in ("identity", "org", "workspace", "audit", "platform"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email_snapshot", sa.String(length=320), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_users_status"),
        schema="identity",
    )

    op.create_table(
        "identity_links",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("issuer", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("email_snapshot", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("display_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.id"],
            name="fk_identity_links_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("issuer", "subject", name="uq_identity_links_issuer_subject"),
        schema="identity",
    )

    op.create_table(
        "web_sessions",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("identity_link_id", UUID, nullable=False),
        sa.Column("secret_hash", sa.LargeBinary(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.id"],
            name="fk_web_sessions_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["identity_link_id"],
            ["identity.identity_links.id"],
            name="fk_web_sessions_identity_link",
            ondelete="CASCADE",
        ),
        schema="identity",
    )

    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active','suspended','deleted')",
            name="ck_organizations_status",
        ),
        sa.CheckConstraint(
            "created_by_actor_type IN ('human','service_principal','system')",
            name="ck_organizations_actor_type",
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        schema="org",
    )

    op.create_table(
        "organization_memberships",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["org.organizations.id"],
            name="fk_memberships_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.users.id"],
            name="fk_memberships_user",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "role IN ('owner','admin','member','guest')",
            name="ck_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('active','suspended','revoked')",
            name="ck_memberships_status",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_memberships_organization_user",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_memberships_organization_id_id",
        ),
        schema="org",
    )

    op.create_table(
        "workspaces",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["org.organizations.id"],
            name="fk_workspaces_organization",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('active','archived','deleted')",
            name="ck_workspaces_status",
        ),
        sa.CheckConstraint(
            "created_by_actor_type IN ('human','service_principal','system')",
            name="ck_workspaces_actor_type",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_workspaces_organization_slug",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_workspaces_organization_id_id",
        ),
        schema="workspace",
    )

    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("workspace_id", UUID, nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["org.organizations.id"],
            name="fk_projects_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspace.workspaces.organization_id", "workspace.workspaces.id"],
            name="fk_projects_workspace_same_org",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('active','archived','deleted')",
            name="ck_projects_status",
        ),
        sa.CheckConstraint(
            "created_by_actor_type IN ('human','service_principal','system')",
            name="ck_projects_actor_type",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_projects_organization_slug",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_projects_organization_id_id",
        ),
        schema="workspace",
    )

    op.create_table(
        "resource_grants",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("subject_kind", sa.String(length=32), nullable=False),
        sa.Column("membership_id", UUID, nullable=True),
        sa.Column("service_principal_id", UUID, nullable=True),
        sa.Column("scope_kind", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", UUID, nullable=True),
        sa.Column("project_id", UUID, nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["org.organizations.id"],
            name="fk_resource_grants_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            [
                "org.organization_memberships.organization_id",
                "org.organization_memberships.id",
            ],
            name="fk_resource_grants_membership_same_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspace.workspaces.organization_id", "workspace.workspaces.id"],
            name="fk_resource_grants_workspace_same_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["workspace.projects.organization_id", "workspace.projects.id"],
            name="fk_resource_grants_project_same_org",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            """(
                subject_kind = 'membership'
                AND membership_id IS NOT NULL
                AND service_principal_id IS NULL
            ) OR (
                subject_kind = 'service_principal'
                AND membership_id IS NULL
                AND service_principal_id IS NOT NULL
            )""",
            name="ck_resource_grants_subject",
        ),
        sa.CheckConstraint(
            """(
                scope_kind = 'organization'
                AND workspace_id IS NULL
                AND project_id IS NULL
            ) OR (
                scope_kind = 'workspace'
                AND workspace_id IS NOT NULL
                AND project_id IS NULL
            ) OR (
                scope_kind = 'project'
                AND workspace_id IS NULL
                AND project_id IS NOT NULL
            )""",
            name="ck_resource_grants_scope",
        ),
        sa.CheckConstraint(
            "role IN ('manager','editor','contributor','viewer')",
            name="ck_resource_grants_role",
        ),
        sa.CheckConstraint(
            "created_by_actor_type IN ('human','service_principal','system')",
            name="ck_resource_grants_actor_type",
        ),
        schema="org",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_resource_grants_active
        ON org.resource_grants (
            organization_id,
            subject_kind,
            membership_id,
            service_principal_id,
            scope_kind,
            workspace_id,
            project_id,
            role
        ) NULLS NOT DISTINCT
        WHERE revoked_at IS NULL
        """
    )

    op.create_table(
        "invitations",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_email_normalized", sa.String(length=320), nullable=True),
        sa.Column("target_user_id", UUID, nullable=True),
        sa.Column("target_issuer", sa.Text(), nullable=True),
        sa.Column("target_subject", sa.Text(), nullable=True),
        sa.Column("organization_role", sa.String(length=32), nullable=False),
        sa.Column("resource_scope_kind", sa.String(length=32), nullable=True),
        sa.Column("resource_workspace_id", UUID, nullable=True),
        sa.Column("resource_project_id", UUID, nullable=True),
        sa.Column("resource_role", sa.String(length=32), nullable=True),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("token_prefix", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=False),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", UUID, nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["org.organizations.id"],
            name="fk_invitations_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["identity.users.id"],
            name="fk_invitations_target_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"],
            ["identity.users.id"],
            name="fk_invitations_accepted_user",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "resource_workspace_id"],
            ["workspace.workspaces.organization_id", "workspace.workspaces.id"],
            name="fk_invitations_workspace_same_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "resource_project_id"],
            ["workspace.projects.organization_id", "workspace.projects.id"],
            name="fk_invitations_project_same_org",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','revoked','expired')",
            name="ck_invitations_status",
        ),
        sa.CheckConstraint(
            "organization_role IN ('owner','admin','member','guest')",
            name="ck_invitations_organization_role",
        ),
        sa.CheckConstraint(
            """(
                target_kind = 'email'
                AND target_email_normalized IS NOT NULL
                AND target_user_id IS NULL
                AND target_issuer IS NULL
                AND target_subject IS NULL
            ) OR (
                target_kind = 'user'
                AND target_email_normalized IS NULL
                AND target_user_id IS NOT NULL
                AND target_issuer IS NULL
                AND target_subject IS NULL
            ) OR (
                target_kind = 'external_identity'
                AND target_email_normalized IS NULL
                AND target_user_id IS NULL
                AND target_issuer IS NOT NULL
                AND target_subject IS NOT NULL
            )""",
            name="ck_invitations_target",
        ),
        sa.CheckConstraint(
            """(
                resource_scope_kind IS NULL
                AND resource_workspace_id IS NULL
                AND resource_project_id IS NULL
                AND resource_role IS NULL
            ) OR (
                resource_scope_kind = 'organization'
                AND resource_workspace_id IS NULL
                AND resource_project_id IS NULL
                AND resource_role IS NOT NULL
            ) OR (
                resource_scope_kind = 'workspace'
                AND resource_workspace_id IS NOT NULL
                AND resource_project_id IS NULL
                AND resource_role IS NOT NULL
            ) OR (
                resource_scope_kind = 'project'
                AND resource_workspace_id IS NULL
                AND resource_project_id IS NOT NULL
                AND resource_role IS NOT NULL
            )""",
            name="ck_invitations_resource_scope",
        ),
        sa.CheckConstraint(
            "resource_role IS NULL OR resource_role IN ('manager','editor','contributor','viewer')",
            name="ck_invitations_resource_role",
        ),
        sa.CheckConstraint(
            "created_by_actor_type IN ('human','service_principal','system')",
            name="ck_invitations_actor_type",
        ),
        schema="org",
    )

    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("organization_id", UUID, nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", UUID, nullable=True),
        sa.Column("actor_display_snapshot", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=True),
        sa.Column("resource_id", UUID, nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["org.organizations.id"],
            name="fk_audit_events_organization",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "actor_type IN ('human','service_principal','system')",
            name="ck_audit_events_actor_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('success','denied','failure')",
            name="ck_audit_events_outcome",
        ),
        schema="audit",
    )

    op.create_table(
        "installation_state",
        sa.Column("singleton_key", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initial_organization_id", UUID, nullable=True),
        sa.Column("initialized_by_user_id", UUID, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["initial_organization_id"],
            ["org.organizations.id"],
            name="fk_installation_state_organization",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["initialized_by_user_id"],
            ["identity.users.id"],
            name="fk_installation_state_user",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "singleton_key = 'installation'",
            name="ck_installation_state_singleton",
        ),
        schema="platform",
    )
    op.execute(
        """
        INSERT INTO platform.installation_state (
            singleton_key,
            initialized_at,
            initial_organization_id,
            initialized_by_user_id,
            updated_at
        )
        VALUES ('installation', NULL, NULL, NULL, now())
        ON CONFLICT (singleton_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("installation_state", schema="platform")
    op.drop_table("audit_events", schema="audit")
    op.drop_table("invitations", schema="org")
    op.execute("DROP INDEX IF EXISTS org.uq_resource_grants_active")
    op.drop_table("resource_grants", schema="org")
    op.drop_table("projects", schema="workspace")
    op.drop_table("workspaces", schema="workspace")
    op.drop_table("organization_memberships", schema="org")
    op.drop_table("organizations", schema="org")
    op.drop_table("web_sessions", schema="identity")
    op.drop_table("identity_links", schema="identity")
    op.drop_table("users", schema="identity")

    for schema in ("platform", "audit", "workspace", "org", "identity"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
