from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.http.tenant_access import human_tenant, require_human_permission
from openvietgis_api.adapters.http.tenant_serialization import serialize_grant
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlResourceGrantRepository,
)
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import GrantNotFoundError, GrantService
from openvietgis_api.domains.tenancy.domain import ResourceRole, ResourceScopeKind

router = APIRouter(tags=["grants"])


class CreateGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_kind: Literal["membership", "service_principal"]
    subject_id: UUID
    scope_kind: ResourceScopeKind
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    role: ResourceRole


def _service(session: Session) -> GrantService:
    return GrantService(
        SqlResourceGrantRepository(session),
        SqlTenancyRepository(session),
        SqlAuditRepository(session),
    )


@router.get("/organizations/{organization_id}/grants")
def list_resource_grants(
    organization_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> list[dict[str, object]]:
    require_human_permission(
        session, authentication, organization_id, Permission.AUTHORIZATION_MANAGE_GRANTS
    )
    return [
        serialize_grant(grant)
        for grant in SqlResourceGrantRepository(session).list_for_organization(
            organization_id, context=context_for(authentication, organization_id=organization_id)
        )
    ]


@router.post("/organizations/{organization_id}/grants", status_code=201)
def create_resource_grant(
    organization_id: UUID,
    payload: CreateGrantRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    require_human_permission(
        session,
        authentication,
        organization_id,
        Permission.AUTHORIZATION_MANAGE_GRANTS,
        lock=True,
    )
    # Service credential grants are handled by the P2 machine-identity implementation.
    if payload.subject_kind != "membership":
        raise HTTPException(status_code=400, detail="service principals are not enabled yet")
    try:
        grant = _service(session).create_membership_grant(
            actor=authentication.actor,
            organization_id=organization_id,
            membership_id=payload.subject_id,
            scope_kind=payload.scope_kind,
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            role=payload.role,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="invalid or duplicate grant") from exc
    return serialize_grant(grant)


@router.post("/organizations/{organization_id}/grants/{grant_id}/revoke", status_code=204)
def revoke_resource_grant(
    organization_id: UUID,
    grant_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    human_tenant(session, authentication, organization_id, lock=True)
    context = context_for(authentication, organization_id=organization_id)
    if (
        SqlResourceGrantRepository(session).get(
            organization_id=organization_id, grant_id=grant_id, context=context
        )
        is None
    ):
        raise GrantNotFoundError("grant not found")
    require_human_permission(
        session,
        authentication,
        organization_id,
        Permission.AUTHORIZATION_MANAGE_GRANTS,
    )
    _service(session).revoke(
        actor=authentication.actor, organization_id=organization_id, grant_id=grant_id
    )
    return Response(status_code=204)
