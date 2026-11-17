from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import set_request_context
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.domain import ResourceGrant
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import (
    ORGANIZATION_ROLE_PERMISSIONS,
    RESOURCE_ROLE_PERMISSIONS,
)
from openvietgis_api.domains.tenancy.domain import (
    ActorType,
    MembershipRole,
    ResourceRole,
    ResourceScopeKind,
)


class SqlEffectivePermissionProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve(self, context: AuthorizationContext) -> frozenset[Permission]:
        actor = context.actor
        if actor.actor_type != "human" or actor.actor_id is None:
            return frozenset()

        set_request_context(
            self._session,
            organization_id=context.organization_id,
            actor_user_id=actor.actor_id,
        )
        membership = (
            self._session.execute(
                text(
                    """
                    SELECT m.id, m.role
                    FROM org.organization_memberships AS m
                    JOIN org.organizations AS o
                      ON o.id = m.organization_id
                    WHERE m.organization_id = :organization_id
                      AND m.user_id = :user_id
                      AND m.status = 'active'
                      AND o.status = 'active'
                    """
                ),
                {
                    "organization_id": context.organization_id,
                    "user_id": actor.actor_id,
                },
            )
            .mappings()
            .one_or_none()
        )
        if membership is None:
            return frozenset()

        permissions = set(
            ORGANIZATION_ROLE_PERMISSIONS[MembershipRole(membership["role"])]
        )

        workspace_id = context.workspace_id
        if context.project_id is not None:
            project_workspace_id = self._session.execute(
                text(
                    """
                    SELECT workspace_id
                    FROM workspace.projects
                    WHERE organization_id = :organization_id
                      AND id = :project_id
                    """
                ),
                {
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                },
            ).scalar_one_or_none()
            workspace_id = project_workspace_id

        rows = self._session.execute(
            text(
                """
                SELECT role
                FROM org.resource_grants
                WHERE organization_id = :organization_id
                  AND subject_kind = 'membership'
                  AND membership_id = :membership_id
                  AND revoked_at IS NULL
                  AND (
                    scope_kind = 'organization'
                    OR (
                        scope_kind = 'workspace'
                        AND workspace_id = :workspace_id
                    )
                    OR (
                        scope_kind = 'project'
                        AND project_id = :project_id
                    )
                  )
                """
            ),
            {
                "organization_id": context.organization_id,
                "membership_id": membership["id"],
                "workspace_id": workspace_id,
                "project_id": context.project_id,
            },
        ).scalars()

        for role in rows:
            permissions.update(RESOURCE_ROLE_PERMISSIONS[ResourceRole(role)])

        return frozenset(permissions)

def _grant_from_row(row: RowMapping) -> ResourceGrant:
    return ResourceGrant(
        id=row["grant_id"],
        organization_id=row["organization_id"],
        subject_kind=row["subject_kind"],
        membership_id=row["membership_id"],
        service_principal_id=row["service_principal_id"],
        scope_kind=ResourceScopeKind(row["scope_kind"]),
        workspace_id=row["workspace_id"],
        project_id=row["project_id"],
        role=ResourceRole(row["role"]),
        created_at=row["created_at"],
        created_by_actor_type=ActorType(row["created_by_actor_type"]),
        created_by_actor_id=row["created_by_actor_id"],
        revoked_at=row["revoked_at"],
    )


class SqlResourceGrantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_organization(self, organization_id: UUID) -> list[ResourceGrant]:
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS grant_id,
                        organization_id,
                        subject_kind,
                        membership_id,
                        service_principal_id,
                        scope_kind,
                        workspace_id,
                        project_id,
                        role,
                        created_at,
                        created_by_actor_type,
                        created_by_actor_id,
                        revoked_at
                    FROM org.resource_grants
                    WHERE organization_id = :organization_id
                    ORDER BY created_at, id
                    """
                ),
                {"organization_id": organization_id},
            )
            .mappings()
            .all()
        )
        return [_grant_from_row(row) for row in rows]

    def create(self, grant: ResourceGrant) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO org.resource_grants (
                    id, organization_id, subject_kind, membership_id,
                    service_principal_id, scope_kind, workspace_id,
                    project_id, role, created_at, created_by_actor_type,
                    created_by_actor_id, revoked_at
                )
                VALUES (
                    :id, :organization_id, :subject_kind, :membership_id,
                    :service_principal_id, :scope_kind, :workspace_id,
                    :project_id, :role, :created_at, :created_by_actor_type,
                    :created_by_actor_id, :revoked_at
                )
                """
            ),
            {
                "id": grant.id,
                "organization_id": grant.organization_id,
                "subject_kind": grant.subject_kind,
                "membership_id": grant.membership_id,
                "service_principal_id": grant.service_principal_id,
                "scope_kind": grant.scope_kind.value,
                "workspace_id": grant.workspace_id,
                "project_id": grant.project_id,
                "role": grant.role.value,
                "created_at": grant.created_at,
                "created_by_actor_type": grant.created_by_actor_type.value,
                "created_by_actor_id": grant.created_by_actor_id,
                "revoked_at": grant.revoked_at,
            },
        )

    def get(
        self,
        *,
        organization_id: UUID,
        grant_id: UUID,
        for_update: bool = False,
    ) -> ResourceGrant | None:
        suffix = " FOR UPDATE" if for_update else ""
        row = (
            self._session.execute(
                text(
                    """
                    SELECT
                        id AS grant_id,
                        organization_id,
                        subject_kind,
                        membership_id,
                        service_principal_id,
                        scope_kind,
                        workspace_id,
                        project_id,
                        role,
                        created_at,
                        created_by_actor_type,
                        created_by_actor_id,
                        revoked_at
                    FROM org.resource_grants
                    WHERE organization_id = :organization_id
                      AND id = :grant_id
                    """
                    + suffix
                ),
                {"organization_id": organization_id, "grant_id": grant_id},
            )
            .mappings()
            .one_or_none()
        )
        return _grant_from_row(row) if row is not None else None

    def update(self, grant: ResourceGrant) -> None:
        self._session.execute(
            text(
                """
                UPDATE org.resource_grants
                SET revoked_at = :revoked_at
                WHERE organization_id = :organization_id
                  AND id = :grant_id
                """
            ),
            {
                "organization_id": grant.organization_id,
                "grant_id": grant.id,
                "revoked_at": grant.revoked_at,
            },
        )