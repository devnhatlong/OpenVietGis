from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import require_member_context
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.domain import ResourceGrant
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import (
    ORGANIZATION_ROLE_PERMISSIONS,
    RESOURCE_ROLE_PERMISSIONS,
)
from openvietgis_api.domains.authorization.service import TenantResourceNotFoundError
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

        try:
            require_member_context(self._session, context, context.organization_id)
        except TenantResourceNotFoundError:
            return frozenset()
        # Resolve live membership, project placement, and applicable grants in
        # one database snapshot. Missing/mismatched scope eliminates the row
        # before organization permissions are applied; LEFT JOIN grants preserves
        # organization role permissions even when no resource grant applies.
        rows = (
            self._session.execute(
                text(
                    """
                    WITH requested AS (
                        SELECT CAST(:organization_id AS uuid) AS organization_id,
                               CAST(:user_id AS uuid) AS user_id,
                               CAST(:workspace_id AS uuid) AS workspace_id,
                               CAST(:project_id AS uuid) AS project_id
                    )
                    SELECT m.role AS membership_role, g.role AS grant_role
                    FROM requested AS r
                    JOIN org.organization_memberships AS m
                      ON m.organization_id = r.organization_id
                     AND m.user_id = r.user_id
                     AND m.status = 'active'
                    JOIN org.organizations AS o
                      ON o.id = m.organization_id
                     AND o.status = 'active'
                    LEFT JOIN workspace.projects AS p
                      ON p.organization_id = r.organization_id
                     AND p.id = r.project_id
                    LEFT JOIN workspace.workspaces AS w
                      ON r.project_id IS NULL
                     AND w.organization_id = r.organization_id
                     AND w.id = r.workspace_id
                    LEFT JOIN org.resource_grants AS g
                      ON g.organization_id = r.organization_id
                     AND g.subject_kind = 'membership'
                     AND g.membership_id = m.id
                     AND g.revoked_at IS NULL
                     AND (
                          g.scope_kind = 'organization'
                          OR (
                              g.scope_kind = 'workspace'
                              AND g.workspace_id = CASE
                                  WHEN r.project_id IS NOT NULL THEN p.workspace_id
                                  ELSE r.workspace_id
                              END
                          )
                          OR (
                              g.scope_kind = 'project'
                              AND g.project_id = r.project_id
                          )
                     )
                    WHERE (
                        r.project_id IS NOT NULL
                        AND p.id IS NOT NULL
                        AND (r.workspace_id IS NULL OR r.workspace_id = p.workspace_id)
                    ) OR (
                        r.project_id IS NULL
                        AND (r.workspace_id IS NULL OR w.id IS NOT NULL)
                    )
                    """
                ),
                {
                    "organization_id": context.organization_id,
                    "user_id": actor.actor_id,
                    "workspace_id": context.workspace_id,
                    "project_id": context.project_id,
                },
            )
            .mappings()
            .all()
        )

        permissions: set[Permission] = set()
        for row in rows:
            permissions.update(
                ORGANIZATION_ROLE_PERMISSIONS[MembershipRole(row["membership_role"])]
            )
            if row["grant_role"] is not None:
                permissions.update(RESOURCE_ROLE_PERMISSIONS[ResourceRole(row["grant_role"])])

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

    def list_for_organization(
        self, organization_id: UUID, *, context: AuthorizationContext
    ) -> list[ResourceGrant]:
        require_member_context(self._session, context, organization_id)
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

    def create(self, grant: ResourceGrant, *, context: AuthorizationContext) -> None:
        require_member_context(self._session, context, grant.organization_id)
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
        context: AuthorizationContext,
        organization_id: UUID,
        grant_id: UUID,
        for_update: bool = False,
    ) -> ResourceGrant | None:
        require_member_context(self._session, context, organization_id)
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

    def update(self, grant: ResourceGrant, *, context: AuthorizationContext) -> None:
        require_member_context(self._session, context, grant.organization_id)
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
