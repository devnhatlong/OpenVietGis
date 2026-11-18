from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import (
    bind_new_organization_context,
    confirm_member_context,
    prepare_self_membership_lookup,
    require_invitation_context,
    require_member_context,
)
from openvietgis_api.domains.authorization.context import (
    Actor,
    AuthorizationContext,
    InvitationAcceptanceContext,
    TenantContext,
)
from openvietgis_api.domains.tenancy.domain import (
    ActorType,
    Invitation,
    InvitationStatus,
    InvitationTargetKind,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Project,
    ProjectStatus,
    ResourceRole,
    ResourceScopeKind,
    Workspace,
    WorkspaceStatus,
)


def _organization_from_row(mapping: RowMapping) -> Organization:
    return Organization(
        id=mapping["organization_id"],
        name=mapping["organization_name"],
        slug=mapping["organization_slug"],
        status=OrganizationStatus(mapping["organization_status"]),
        created_by_actor_type=ActorType(mapping["organization_created_by_actor_type"]),
        created_by_actor_id=mapping["organization_created_by_actor_id"],
        created_at=mapping["organization_created_at"],
        updated_at=mapping["organization_updated_at"],
        deleted_at=mapping["organization_deleted_at"],
    )


def _workspace_from_row(mapping: RowMapping) -> Workspace:
    return Workspace(
        id=mapping["workspace_id"],
        organization_id=mapping["organization_id"],
        name=mapping["workspace_name"],
        slug=mapping["workspace_slug"],
        status=WorkspaceStatus(mapping["workspace_status"]),
        created_by_actor_type=ActorType(mapping["workspace_created_by_actor_type"]),
        created_by_actor_id=mapping["workspace_created_by_actor_id"],
        created_at=mapping["workspace_created_at"],
        updated_at=mapping["workspace_updated_at"],
        archived_at=mapping["workspace_archived_at"],
        deleted_at=mapping["workspace_deleted_at"],
    )


def _project_from_row(mapping: RowMapping) -> Project:
    return Project(
        id=mapping["project_id"],
        organization_id=mapping["organization_id"],
        workspace_id=mapping["workspace_id"],
        name=mapping["project_name"],
        slug=mapping["project_slug"],
        status=ProjectStatus(mapping["project_status"]),
        created_by_actor_type=ActorType(mapping["project_created_by_actor_type"]),
        created_by_actor_id=mapping["project_created_by_actor_id"],
        created_at=mapping["project_created_at"],
        updated_at=mapping["project_updated_at"],
        archived_at=mapping["project_archived_at"],
        deleted_at=mapping["project_deleted_at"],
    )


def _invitation_from_row(mapping: RowMapping) -> Invitation:
    return Invitation(
        id=mapping["invitation_id"],
        organization_id=mapping["organization_id"],
        status=InvitationStatus(mapping["invitation_status"]),
        target_kind=InvitationTargetKind(mapping["target_kind"]),
        target_email_normalized=mapping["target_email_normalized"],
        target_user_id=mapping["target_user_id"],
        target_issuer=mapping["target_issuer"],
        target_subject=mapping["target_subject"],
        organization_role=MembershipRole(mapping["organization_role"]),
        resource_scope_kind=(
            ResourceScopeKind(mapping["resource_scope_kind"])
            if mapping["resource_scope_kind"] is not None
            else None
        ),
        resource_workspace_id=mapping["resource_workspace_id"],
        resource_project_id=mapping["resource_project_id"],
        resource_role=(
            ResourceRole(mapping["resource_role"]) if mapping["resource_role"] is not None else None
        ),
        token_hash=mapping["token_hash"],
        token_prefix=mapping["token_prefix"],
        expires_at=mapping["expires_at"],
        created_at=mapping["invitation_created_at"],
        created_by_actor_type=ActorType(mapping["invitation_created_by_actor_type"]),
        created_by_actor_id=mapping["invitation_created_by_actor_id"],
        accepted_at=mapping["accepted_at"],
        accepted_by_user_id=mapping["accepted_by_user_id"],
        revoked_at=mapping["revoked_at"],
    )


def _membership_from_row(mapping: RowMapping) -> OrganizationMembership:
    return OrganizationMembership(
        id=mapping["membership_id"],
        organization_id=mapping["organization_id"],
        user_id=mapping["user_id"],
        role=MembershipRole(mapping["membership_role"]),
        status=MembershipStatus(mapping["membership_status"]),
        created_at=mapping["membership_created_at"],
        activated_at=mapping["membership_activated_at"],
        suspended_at=mapping["membership_suspended_at"],
        revoked_at=mapping["membership_revoked_at"],
    )


class SqlTenancyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active_organizations_for_user(
        self,
        user_id: UUID,
        *,
        actor: Actor,
    ) -> list[tuple[Organization, OrganizationMembership]]:
        prepare_self_membership_lookup(self._session, actor)
        if actor.actor_id != user_id:
            raise PermissionError("self-membership discovery requires matching actor")
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT
                        o.id AS organization_id,
                        o.name AS organization_name,
                        o.slug AS organization_slug,
                        o.status AS organization_status,
                        o.created_by_actor_type AS organization_created_by_actor_type,
                        o.created_by_actor_id AS organization_created_by_actor_id,
                        o.created_at AS organization_created_at,
                        o.updated_at AS organization_updated_at,
                        o.deleted_at AS organization_deleted_at,
                        m.id AS membership_id,
                        m.user_id,
                        m.role AS membership_role,
                        m.status AS membership_status,
                        m.created_at AS membership_created_at,
                        m.activated_at AS membership_activated_at,
                        m.suspended_at AS membership_suspended_at,
                        m.revoked_at AS membership_revoked_at
                    FROM org.organization_memberships AS m
                    JOIN org.organizations AS o ON o.id = m.organization_id
                    WHERE m.user_id = :user_id
                      AND m.status = 'active'
                    ORDER BY o.name, o.id
                    """
                ),
                {"user_id": user_id},
            )
            .mappings()
            .all()
        )
        return [(_organization_from_row(row), _membership_from_row(row)) for row in rows]

    def get_active_membership(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        user_id: UUID,
    ) -> OrganizationMembership | None:
        if context.actor.actor_id != user_id or context.organization_id != organization_id:
            raise PermissionError("membership lookup requires matching actor and organization")
        prepare_self_membership_lookup(self._session, context.actor)
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS membership_id,
                        organization_id,
                        user_id,
                        role AS membership_role,
                        status AS membership_status,
                        created_at AS membership_created_at,
                        activated_at AS membership_activated_at,
                        suspended_at AS membership_suspended_at,
                        revoked_at AS membership_revoked_at
                    FROM org.organization_memberships
                    WHERE organization_id = :organization_id
                      AND user_id = :user_id
                      AND status = 'active'
                    """
                ),
                {"organization_id": organization_id, "user_id": user_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            confirm_member_context(self._session, context)
            return _membership_from_row(row)
        return None

    def create_organization_with_owner(
        self,
        organization: Organization,
        membership: OrganizationMembership,
        *,
        context: AuthorizationContext,
    ) -> None:
        if (
            context.organization_id != organization.id
            or context.actor.actor_id != membership.user_id
            or organization.created_by_actor_id != context.actor.actor_id
            or membership.organization_id != organization.id
            or membership.role != MembershipRole.OWNER
            or membership.status != MembershipStatus.ACTIVE
        ):
            raise PermissionError("organization creation context mismatch")
        bind_new_organization_context(self._session, context)
        self._session.execute(
            text(
                """
                INSERT INTO org.organizations (
                    id, name, slug, status, created_by_actor_type,
                    created_by_actor_id, created_at, updated_at, deleted_at
                )
                VALUES (
                    :id, :name, :slug, :status, :created_by_actor_type,
                    :created_by_actor_id, :created_at, :updated_at, :deleted_at
                )
                """
            ),
            {
                "id": organization.id,
                "name": organization.name,
                "slug": organization.slug,
                "status": organization.status.value,
                "created_by_actor_type": organization.created_by_actor_type.value,
                "created_by_actor_id": organization.created_by_actor_id,
                "created_at": organization.created_at,
                "updated_at": organization.updated_at,
                "deleted_at": organization.deleted_at,
            },
        )
        self._session.execute(
            text(
                """
                INSERT INTO org.organization_memberships (
                    id, organization_id, user_id, role, status,
                    created_at, activated_at, suspended_at, revoked_at
                )
                VALUES (
                    :id, :organization_id, :user_id, :role, :status,
                    :created_at, :activated_at, :suspended_at, :revoked_at
                )
                """
            ),
            {
                "id": membership.id,
                "organization_id": membership.organization_id,
                "user_id": membership.user_id,
                "role": membership.role.value,
                "status": membership.status.value,
                "created_at": membership.created_at,
                "activated_at": membership.activated_at,
                "suspended_at": membership.suspended_at,
                "revoked_at": membership.revoked_at,
            },
        )
        confirm_member_context(self._session, context)

    def list_workspaces(
        self, organization_id: UUID, *, context: AuthorizationContext
    ) -> list[Workspace]:
        require_member_context(self._session, context, organization_id)
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS workspace_id,
                        organization_id,
                        name AS workspace_name,
                        slug AS workspace_slug,
                        status AS workspace_status,
                        created_by_actor_type AS workspace_created_by_actor_type,
                        created_by_actor_id AS workspace_created_by_actor_id,
                        created_at AS workspace_created_at,
                        updated_at AS workspace_updated_at,
                        archived_at AS workspace_archived_at,
                        deleted_at AS workspace_deleted_at
                    FROM workspace.workspaces
                    WHERE organization_id = :organization_id
                      AND status <> 'deleted'
                    ORDER BY name, id
                    """
                ),
                {"organization_id": organization_id},
            )
            .mappings()
            .all()
        )
        return [_workspace_from_row(row) for row in rows]

    def get_workspace(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        workspace_id: UUID,
    ) -> Workspace | None:
        require_member_context(self._session, context, organization_id)
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS workspace_id,
                        organization_id,
                        name AS workspace_name,
                        slug AS workspace_slug,
                        status AS workspace_status,
                        created_by_actor_type AS workspace_created_by_actor_type,
                        created_by_actor_id AS workspace_created_by_actor_id,
                        created_at AS workspace_created_at,
                        updated_at AS workspace_updated_at,
                        archived_at AS workspace_archived_at,
                        deleted_at AS workspace_deleted_at
                    FROM workspace.workspaces
                    WHERE organization_id = :organization_id
                      AND id = :workspace_id
                    """
                ),
                {"organization_id": organization_id, "workspace_id": workspace_id},
            )
            .mappings()
            .one_or_none()
        )
        return _workspace_from_row(row) if row is not None else None

    def create_workspace(self, workspace: Workspace, *, context: AuthorizationContext) -> None:
        require_member_context(self._session, context, workspace.organization_id)
        self._session.execute(
            text(
                """
                INSERT INTO workspace.workspaces (
                    id, organization_id, name, slug, status,
                    created_by_actor_type, created_by_actor_id,
                    created_at, updated_at, archived_at, deleted_at
                )
                VALUES (
                    :id, :organization_id, :name, :slug, :status,
                    :created_by_actor_type, :created_by_actor_id,
                    :created_at, :updated_at, :archived_at, :deleted_at
                )
                """
            ),
            {
                "id": workspace.id,
                "organization_id": workspace.organization_id,
                "name": workspace.name,
                "slug": workspace.slug,
                "status": workspace.status.value,
                "created_by_actor_type": workspace.created_by_actor_type.value,
                "created_by_actor_id": workspace.created_by_actor_id,
                "created_at": workspace.created_at,
                "updated_at": workspace.updated_at,
                "archived_at": workspace.archived_at,
                "deleted_at": workspace.deleted_at,
            },
        )

    def update_workspace(self, workspace: Workspace, *, context: AuthorizationContext) -> None:
        require_member_context(self._session, context, workspace.organization_id)
        self._session.execute(
            text(
                """
                UPDATE workspace.workspaces
                SET name = :name,
                    status = :status,
                    updated_at = :updated_at,
                    archived_at = :archived_at,
                    deleted_at = :deleted_at
                WHERE organization_id = :organization_id
                  AND id = :workspace_id
                """
            ),
            {
                "organization_id": workspace.organization_id,
                "workspace_id": workspace.id,
                "name": workspace.name,
                "status": workspace.status.value,
                "updated_at": workspace.updated_at,
                "archived_at": workspace.archived_at,
                "deleted_at": workspace.deleted_at,
            },
        )

    def count_active_projects_in_workspace(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        workspace_id: UUID,
    ) -> int:
        require_member_context(self._session, context, organization_id)
        return int(
            self._session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM workspace.projects
                    WHERE organization_id = :organization_id
                      AND workspace_id = :workspace_id
                      AND status = 'active'
                    """
                ),
                {"organization_id": organization_id, "workspace_id": workspace_id},
            ).scalar_one()
        )

    def list_projects(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        workspace_id: UUID | None = None,
    ) -> list[Project]:
        require_member_context(self._session, context, organization_id)
        query = """
            SELECT
                id AS project_id,
                organization_id,
                workspace_id,
                name AS project_name,
                slug AS project_slug,
                status AS project_status,
                created_by_actor_type AS project_created_by_actor_type,
                created_by_actor_id AS project_created_by_actor_id,
                created_at AS project_created_at,
                updated_at AS project_updated_at,
                archived_at AS project_archived_at,
                deleted_at AS project_deleted_at
            FROM workspace.projects
            WHERE organization_id = :organization_id
              AND status <> 'deleted'
        """
        parameters: dict[str, object] = {"organization_id": organization_id}
        if workspace_id is not None:
            query += " AND workspace_id = :workspace_id"
            parameters["workspace_id"] = workspace_id
        query += " ORDER BY name, id"

        rows = self._session.execute(text(query), parameters).mappings().all()
        return [_project_from_row(row) for row in rows]

    def get_project(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        project_id: UUID,
    ) -> Project | None:
        require_member_context(self._session, context, organization_id)
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS project_id,
                        organization_id,
                        workspace_id,
                        name AS project_name,
                        slug AS project_slug,
                        status AS project_status,
                        created_by_actor_type AS project_created_by_actor_type,
                        created_by_actor_id AS project_created_by_actor_id,
                        created_at AS project_created_at,
                        updated_at AS project_updated_at,
                        archived_at AS project_archived_at,
                        deleted_at AS project_deleted_at
                    FROM workspace.projects
                    WHERE organization_id = :organization_id
                      AND id = :project_id
                    """
                ),
                {"organization_id": organization_id, "project_id": project_id},
            )
            .mappings()
            .one_or_none()
        )
        return _project_from_row(row) if row is not None else None

    def create_project(self, project: Project, *, context: AuthorizationContext) -> None:
        require_member_context(self._session, context, project.organization_id)
        self._session.execute(
            text(
                """
                INSERT INTO workspace.projects (
                    id, organization_id, workspace_id, name, slug, status,
                    created_by_actor_type, created_by_actor_id,
                    created_at, updated_at, archived_at, deleted_at
                )
                VALUES (
                    :id, :organization_id, :workspace_id, :name, :slug, :status,
                    :created_by_actor_type, :created_by_actor_id,
                    :created_at, :updated_at, :archived_at, :deleted_at
                )
                """
            ),
            {
                "id": project.id,
                "organization_id": project.organization_id,
                "workspace_id": project.workspace_id,
                "name": project.name,
                "slug": project.slug,
                "status": project.status.value,
                "created_by_actor_type": project.created_by_actor_type.value,
                "created_by_actor_id": project.created_by_actor_id,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "archived_at": project.archived_at,
                "deleted_at": project.deleted_at,
            },
        )

    def update_project(self, project: Project, *, context: AuthorizationContext) -> None:
        require_member_context(self._session, context, project.organization_id)
        self._session.execute(
            text(
                """
                UPDATE workspace.projects
                SET workspace_id = :workspace_id,
                    name = :name,
                    status = :status,
                    updated_at = :updated_at,
                    archived_at = :archived_at,
                    deleted_at = :deleted_at
                WHERE organization_id = :organization_id
                  AND id = :project_id
                """
            ),
            {
                "organization_id": project.organization_id,
                "project_id": project.id,
                "workspace_id": project.workspace_id,
                "name": project.name,
                "status": project.status.value,
                "updated_at": project.updated_at,
                "archived_at": project.archived_at,
                "deleted_at": project.deleted_at,
            },
        )

    def get_organization(
        self,
        organization_id: UUID,
        *,
        context: TenantContext,
        for_update: bool = False,
    ) -> Organization | None:
        if isinstance(context, InvitationAcceptanceContext):
            require_invitation_context(self._session, context, organization_id)
        else:
            require_member_context(self._session, context, organization_id)
        suffix = " FOR UPDATE" if for_update else ""
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS organization_id,
                        name AS organization_name,
                        slug AS organization_slug,
                        status AS organization_status,
                        created_by_actor_type AS organization_created_by_actor_type,
                        created_by_actor_id AS organization_created_by_actor_id,
                        created_at AS organization_created_at,
                        updated_at AS organization_updated_at,
                        deleted_at AS organization_deleted_at
                    FROM org.organizations
                    WHERE id = :organization_id
                    """
                    + suffix
                ),
                {"organization_id": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        return _organization_from_row(row) if row is not None else None

    def update_organization(
        self, organization: Organization, *, context: AuthorizationContext
    ) -> None:
        require_member_context(self._session, context, organization.id)
        self._session.execute(
            text(
                """
                UPDATE org.organizations
                SET name = :name,
                    status = :status,
                    updated_at = :updated_at,
                    deleted_at = :deleted_at
                WHERE id = :organization_id
                """
            ),
            {
                "organization_id": organization.id,
                "name": organization.name,
                "status": organization.status.value,
                "updated_at": organization.updated_at,
                "deleted_at": organization.deleted_at,
            },
        )

    def list_memberships(
        self,
        organization_id: UUID,
        *,
        context: AuthorizationContext,
    ) -> list[OrganizationMembership]:
        require_member_context(self._session, context, organization_id)
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS membership_id,
                        organization_id,
                        user_id,
                        role AS membership_role,
                        status AS membership_status,
                        created_at AS membership_created_at,
                        activated_at AS membership_activated_at,
                        suspended_at AS membership_suspended_at,
                        revoked_at AS membership_revoked_at
                    FROM org.organization_memberships
                    WHERE organization_id = :organization_id
                    ORDER BY created_at, id
                    """
                ),
                {"organization_id": organization_id},
            )
            .mappings()
            .all()
        )
        return [_membership_from_row(row) for row in rows]

    def get_membership(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        membership_id: UUID,
        for_update: bool = False,
    ) -> OrganizationMembership | None:
        require_member_context(self._session, context, organization_id)
        suffix = " FOR UPDATE" if for_update else ""
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS membership_id,
                        organization_id,
                        user_id,
                        role AS membership_role,
                        status AS membership_status,
                        created_at AS membership_created_at,
                        activated_at AS membership_activated_at,
                        suspended_at AS membership_suspended_at,
                        revoked_at AS membership_revoked_at
                    FROM org.organization_memberships
                    WHERE organization_id = :organization_id
                      AND id = :membership_id
                    """
                    + suffix
                ),
                {
                    "organization_id": organization_id,
                    "membership_id": membership_id,
                },
            )
            .mappings()
            .one_or_none()
        )
        return _membership_from_row(row) if row is not None else None

    def get_membership_for_user(
        self,
        *,
        context: TenantContext,
        organization_id: UUID,
        user_id: UUID,
        for_update: bool = False,
    ) -> OrganizationMembership | None:
        if isinstance(context, InvitationAcceptanceContext):
            require_invitation_context(
                self._session, context, organization_id, require_verified=True
            )
        else:
            require_member_context(self._session, context, organization_id)
        suffix = " FOR UPDATE" if for_update else ""
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS membership_id,
                        organization_id,
                        user_id,
                        role AS membership_role,
                        status AS membership_status,
                        created_at AS membership_created_at,
                        activated_at AS membership_activated_at,
                        suspended_at AS membership_suspended_at,
                        revoked_at AS membership_revoked_at
                    FROM org.organization_memberships
                    WHERE organization_id = :organization_id
                      AND user_id = :user_id
                    """
                    + suffix
                ),
                {"organization_id": organization_id, "user_id": user_id},
            )
            .mappings()
            .one_or_none()
        )
        return _membership_from_row(row) if row is not None else None

    def count_other_active_owners(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        excluding_membership_id: UUID,
    ) -> int:
        require_member_context(self._session, context, organization_id)
        return int(
            self._session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM org.organization_memberships
                    WHERE organization_id = :organization_id
                      AND id <> :membership_id
                      AND role = 'owner'
                      AND status = 'active'
                    """
                ),
                {
                    "organization_id": organization_id,
                    "membership_id": excluding_membership_id,
                },
            ).scalar_one()
        )

    def create_membership(
        self, membership: OrganizationMembership, *, context: TenantContext
    ) -> None:
        if isinstance(context, InvitationAcceptanceContext):
            if context.actor.actor_id != membership.user_id:
                raise PermissionError("invitation membership target mismatch")
            require_invitation_context(
                self._session, context, membership.organization_id, require_verified=True
            )
        else:
            require_member_context(self._session, context, membership.organization_id)
        self._session.execute(
            text(
                """
                INSERT INTO org.organization_memberships (
                    id, organization_id, user_id, role, status,
                    created_at, activated_at, suspended_at, revoked_at
                )
                VALUES (
                    :id, :organization_id, :user_id, :role, :status,
                    :created_at, :activated_at, :suspended_at, :revoked_at
                )
                """
            ),
            {
                "id": membership.id,
                "organization_id": membership.organization_id,
                "user_id": membership.user_id,
                "role": membership.role.value,
                "status": membership.status.value,
                "created_at": membership.created_at,
                "activated_at": membership.activated_at,
                "suspended_at": membership.suspended_at,
                "revoked_at": membership.revoked_at,
            },
        )

    def update_membership(
        self, membership: OrganizationMembership, *, context: TenantContext
    ) -> None:
        if isinstance(context, InvitationAcceptanceContext):
            if context.actor.actor_id != membership.user_id:
                raise PermissionError("invitation membership target mismatch")
            require_invitation_context(
                self._session, context, membership.organization_id, require_verified=True
            )
        else:
            require_member_context(self._session, context, membership.organization_id)
        self._session.execute(
            text(
                """
                UPDATE org.organization_memberships
                SET role = :role,
                    status = :status,
                    activated_at = :activated_at,
                    suspended_at = :suspended_at,
                    revoked_at = :revoked_at
                WHERE organization_id = :organization_id
                  AND id = :membership_id
                """
            ),
            {
                "organization_id": membership.organization_id,
                "membership_id": membership.id,
                "role": membership.role.value,
                "status": membership.status.value,
                "activated_at": membership.activated_at,
                "suspended_at": membership.suspended_at,
                "revoked_at": membership.revoked_at,
            },
        )

    def create_invitation(self, invitation: Invitation, *, context: AuthorizationContext) -> None:
        require_member_context(self._session, context, invitation.organization_id)
        self._session.execute(
            text(
                """
                INSERT INTO org.invitations (
                    id, organization_id, status, target_kind,
                    target_email_normalized, target_user_id, target_issuer, target_subject,
                    organization_role, resource_scope_kind, resource_workspace_id,
                    resource_project_id, resource_role, token_hash, token_prefix,
                    expires_at, created_at, created_by_actor_type, created_by_actor_id,
                    accepted_at, accepted_by_user_id, revoked_at
                )
                VALUES (
                    :id, :organization_id, :status, :target_kind,
                    :target_email_normalized, :target_user_id, :target_issuer, :target_subject,
                    :organization_role, :resource_scope_kind, :resource_workspace_id,
                    :resource_project_id, :resource_role, :token_hash, :token_prefix,
                    :expires_at, :created_at, :created_by_actor_type, :created_by_actor_id,
                    :accepted_at, :accepted_by_user_id, :revoked_at
                )
                """
            ),
            {
                "id": invitation.id,
                "organization_id": invitation.organization_id,
                "status": invitation.status.value,
                "target_kind": invitation.target_kind.value,
                "target_email_normalized": invitation.target_email_normalized,
                "target_user_id": invitation.target_user_id,
                "target_issuer": invitation.target_issuer,
                "target_subject": invitation.target_subject,
                "organization_role": invitation.organization_role.value,
                "resource_scope_kind": (
                    invitation.resource_scope_kind.value
                    if invitation.resource_scope_kind is not None
                    else None
                ),
                "resource_workspace_id": invitation.resource_workspace_id,
                "resource_project_id": invitation.resource_project_id,
                "resource_role": (
                    invitation.resource_role.value if invitation.resource_role is not None else None
                ),
                "token_hash": invitation.token_hash,
                "token_prefix": invitation.token_prefix,
                "expires_at": invitation.expires_at,
                "created_at": invitation.created_at,
                "created_by_actor_type": invitation.created_by_actor_type.value,
                "created_by_actor_id": invitation.created_by_actor_id,
                "accepted_at": invitation.accepted_at,
                "accepted_by_user_id": invitation.accepted_by_user_id,
                "revoked_at": invitation.revoked_at,
            },
        )

    def get_invitation(
        self,
        *,
        context: TenantContext,
        organization_id: UUID,
        invitation_id: UUID,
        for_update: bool = False,
    ) -> Invitation | None:
        if isinstance(context, InvitationAcceptanceContext):
            require_invitation_context(
                self._session, context, organization_id, invitation_id=invitation_id
            )
        else:
            require_member_context(self._session, context, organization_id)
        suffix = " FOR UPDATE" if for_update else ""
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS invitation_id,
                        organization_id,
                        status AS invitation_status,
                        target_kind,
                        target_email_normalized,
                        target_user_id,
                        target_issuer,
                        target_subject,
                        organization_role,
                        resource_scope_kind,
                        resource_workspace_id,
                        resource_project_id,
                        resource_role,
                        token_hash,
                        token_prefix,
                        expires_at,
                        created_at AS invitation_created_at,
                        created_by_actor_type AS invitation_created_by_actor_type,
                        created_by_actor_id AS invitation_created_by_actor_id,
                        accepted_at,
                        accepted_by_user_id,
                        revoked_at
                    FROM org.invitations
                    WHERE organization_id = :organization_id
                      AND id = :invitation_id
                    """
                    + suffix
                ),
                {
                    "organization_id": organization_id,
                    "invitation_id": invitation_id,
                },
            )
            .mappings()
            .one_or_none()
        )
        return _invitation_from_row(row) if row is not None else None

    def update_invitation(self, invitation: Invitation, *, context: TenantContext) -> None:
        if isinstance(context, InvitationAcceptanceContext):
            require_invitation_context(
                self._session,
                context,
                invitation.organization_id,
                invitation_id=invitation.id,
                require_verified=invitation.status != InvitationStatus.EXPIRED,
            )
        else:
            require_member_context(self._session, context, invitation.organization_id)
        self._session.execute(
            text(
                """
                UPDATE org.invitations
                SET status = :status,
                    accepted_at = :accepted_at,
                    accepted_by_user_id = :accepted_by_user_id,
                    revoked_at = :revoked_at
                WHERE organization_id = :organization_id
                  AND id = :invitation_id
                """
            ),
            {
                "organization_id": invitation.organization_id,
                "invitation_id": invitation.id,
                "status": invitation.status.value,
                "accepted_at": invitation.accepted_at,
                "accepted_by_user_id": invitation.accepted_by_user_id,
                "revoked_at": invitation.revoked_at,
            },
        )
