from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.security import AuthenticatedRequest
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlEffectivePermissionProvider,
)
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import AuthorizationService


def context_for(
    authentication: AuthenticatedRequest,
    *,
    organization_id: UUID,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
) -> AuthorizationContext:
    return AuthorizationContext(
        actor=authentication.actor,
        organization_id=organization_id,
        workspace_id=workspace_id,
        project_id=project_id,
        credential_id=authentication.credential_id,
    )


def require_permission(
    session: Session,
    context: AuthorizationContext,
    permission: Permission,
) -> None:
    AuthorizationService(SqlEffectivePermissionProvider(session)).require(
        context,
        permission,
    )
