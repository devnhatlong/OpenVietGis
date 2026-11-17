from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import set_request_context
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import (
    ORGANIZATION_ROLE_PERMISSIONS,
    RESOURCE_ROLE_PERMISSIONS,
)
from openvietgis_api.domains.tenancy.domain import MembershipRole, ResourceRole


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
                    SELECT id, role
                    FROM org.organization_memberships
                    WHERE organization_id = :organization_id
                      AND user_id = :user_id
                      AND status = 'active'
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
