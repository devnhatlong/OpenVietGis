from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for, require_permission
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlEffectivePermissionProvider,
)
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import AuthorizationService
from openvietgis_api.domains.tenancy.domain import WorkspaceStatus
from openvietgis_api.domains.tenancy.service import TenancyService

router = APIRouter(tags=["workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: WorkspaceStatus | None = None


def _service(session: Session) -> TenancyService:
    return TenancyService(
        SqlTenancyRepository(session),
        SqlPlatformRepository(session),
        SqlAuditRepository(session),
    )


def _serialize(workspace) -> dict[str, object]:
    return {
        "id": workspace.id,
        "organization_id": workspace.organization_id,
        "name": workspace.name,
        "slug": workspace.slug,
        "status": workspace.status.value,
    }


@router.get("/organizations/{organization_id}/workspaces")
def list_workspaces(
    organization_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> list[dict[str, object]]:
    repository = SqlTenancyRepository(session)
    provider = SqlEffectivePermissionProvider(session)
    authorization = AuthorizationService(provider)

    organization_context = context_for(
        authentication,
        organization_id=organization_id,
    )
    if authorization.is_allowed(organization_context, Permission.WORKSPACE_READ):
        return [_serialize(item) for item in repository.list_workspaces(organization_id)]

    visible = []
    for workspace in repository.list_workspaces(organization_id):
        workspace_context = context_for(
            authentication,
            organization_id=organization_id,
            workspace_id=workspace.id,
        )
        if authorization.is_allowed(workspace_context, Permission.WORKSPACE_READ):
            visible.append(_serialize(workspace))
    return visible


@router.post("/organizations/{organization_id}/workspaces", status_code=201)
def create_workspace(
    organization_id: UUID,
    payload: CreateWorkspaceRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id)
    require_permission(session, context, Permission.WORKSPACE_MANAGE)
    workspace = _service(session).create_workspace(
        actor=authentication.actor,
        organization_id=organization_id,
        name=payload.name,
        slug=payload.slug,
    )
    return _serialize(workspace)


@router.patch("/organizations/{organization_id}/workspaces/{workspace_id}")
def update_workspace(
    organization_id: UUID,
    workspace_id: UUID,
    payload: UpdateWorkspaceRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(
        authentication,
        organization_id=organization_id,
        workspace_id=workspace_id,
    )
    require_permission(session, context, Permission.WORKSPACE_MANAGE)
    workspace = _service(session).update_workspace(
        actor=authentication.actor,
        organization_id=organization_id,
        workspace_id=workspace_id,
        name=payload.name,
        status=payload.status,
    )
    return _serialize(workspace)
