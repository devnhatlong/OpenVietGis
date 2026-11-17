from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import set_request_context
from openvietgis_api.domains.tenancy.domain import (
    ActorType,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
    Project,
    ProjectStatus,
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
    ) -> list[tuple[Organization, OrganizationMembership]]:
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
        organization_id: UUID,
        user_id: UUID,
    ) -> OrganizationMembership | None:
        set_request_context(
            self._session,
            organization_id=organization_id,
            actor_user_id=user_id,
        )
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
        return _membership_from_row(row) if row is not None else None

    def create_organization_with_owner(
        self,
        organization: Organization,
        membership: OrganizationMembership,
    ) -> None:
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
        set_request_context(
            self._session,
            organization_id=organization.id,
            actor_user_id=membership.user_id,
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

    def list_workspaces(self, organization_id: UUID) -> list[Workspace]:
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
        organization_id: UUID,
        workspace_id: UUID,
    ) -> Workspace | None:
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

    def create_workspace(self, workspace: Workspace) -> None:
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

    def update_workspace(self, workspace: Workspace) -> None:
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
        organization_id: UUID,
        workspace_id: UUID,
    ) -> int:
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
        organization_id: UUID,
        workspace_id: UUID | None = None,
    ) -> list[Project]:
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
        organization_id: UUID,
        project_id: UUID,
    ) -> Project | None:
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

    def create_project(self, project: Project) -> None:
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

    def update_project(self, project: Project) -> None:
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
