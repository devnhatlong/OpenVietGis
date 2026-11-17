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
from openvietgis_api.domains.tenancy.domain import ProjectStatus
from openvietgis_api.domains.tenancy.service import TenancyService

router = APIRouter(tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)
    workspace_id: UUID | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    workspace_id: UUID | None = None
    status: ProjectStatus | None = None


def _service(session: Session) -> TenancyService:
    return TenancyService(
        SqlTenancyRepository(session),
        SqlPlatformRepository(session),
        SqlAuditRepository(session),
    )


def _serialize(project) -> dict[str, object]:
    return {
        "id": project.id,
        "organization_id": project.organization_id,
        "workspace_id": project.workspace_id,
        "name": project.name,
        "slug": project.slug,
        "status": project.status.value,
    }


@router.get("/organizations/{organization_id}/projects")
def list_projects(
    organization_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    workspace_id: UUID | None = None,
) -> list[dict[str, object]]:
    repository = SqlTenancyRepository(session)
    provider = SqlEffectivePermissionProvider(session)
    authorization = AuthorizationService(provider)

    base_context = context_for(
        authentication,
        organization_id=organization_id,
        workspace_id=workspace_id,
    )
    if authorization.is_allowed(base_context, Permission.PROJECT_READ):
        return [
            _serialize(item)
            for item in repository.list_projects(
                organization_id=organization_id,
                workspace_id=workspace_id,
            )
        ]

    visible = []
    for project in repository.list_projects(
        organization_id=organization_id,
        workspace_id=workspace_id,
    ):
        project_context = context_for(
            authentication,
            organization_id=organization_id,
            project_id=project.id,
        )
        if authorization.is_allowed(project_context, Permission.PROJECT_READ):
            visible.append(_serialize(project))
    return visible


@router.post("/organizations/{organization_id}/projects", status_code=201)
def create_project(
    organization_id: UUID,
    payload: CreateProjectRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(
        authentication,
        organization_id=organization_id,
        workspace_id=payload.workspace_id,
    )
    require_permission(session, context, Permission.PROJECT_MANAGE)
    project = _service(session).create_project(
        actor=authentication.actor,
        organization_id=organization_id,
        name=payload.name,
        slug=payload.slug,
        workspace_id=payload.workspace_id,
    )
    return _serialize(project)


@router.get("/organizations/{organization_id}/projects/{project_id}")
def get_project(
    organization_id: UUID,
    project_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(
        authentication,
        organization_id=organization_id,
        project_id=project_id,
    )
    require_permission(session, context, Permission.PROJECT_READ)
    project = SqlTenancyRepository(session).get_project(
        organization_id=organization_id,
        project_id=project_id,
    )
    if project is None:
        from openvietgis_api.domains.tenancy.service import ProjectNotFoundError

        raise ProjectNotFoundError("project not found")
    return _serialize(project)


@router.patch("/organizations/{organization_id}/projects/{project_id}")
def update_project(
    organization_id: UUID,
    project_id: UUID,
    payload: UpdateProjectRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(
        authentication,
        organization_id=organization_id,
        project_id=project_id,
    )
    if payload.name is not None:
        require_permission(session, context, Permission.PROJECT_MANAGE)
    if "workspace_id" in payload.model_fields_set:
        require_permission(session, context, Permission.PROJECT_MOVE_WORKSPACE)
    if payload.status == ProjectStatus.ARCHIVED or payload.status == ProjectStatus.ACTIVE:
        require_permission(session, context, Permission.PROJECT_ARCHIVE)
    if payload.status == ProjectStatus.DELETED:
        require_permission(session, context, Permission.PROJECT_DELETE)

    project = _service(session).update_project(
        actor=authentication.actor,
        organization_id=organization_id,
        project_id=project_id,
        name=payload.name,
        workspace_id=payload.workspace_id,
        workspace_supplied="workspace_id" in payload.model_fields_set,
        status=payload.status,
    )
    return _serialize(project)