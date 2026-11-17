from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.tenancy.service import (
    InstallationNotInitializedError,
    InvalidOrganizationInputError,
    TenancyService,
)

router = APIRouter(tags=["organizations"])


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)


@router.post("/organizations", status_code=201)
def create_organization(
    payload: CreateOrganizationRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    service = TenancyService(
        SqlTenancyRepository(session),
        SqlPlatformRepository(session),
        SqlAuditRepository(session),
    )
    try:
        organization, membership = service.create_organization(
            actor=authentication.actor,
            name=payload.name,
            slug=payload.slug,
        )
    except InstallationNotInitializedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidOrganizationInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="organization slug already exists") from exc

    return {
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "status": organization.status.value,
        },
        "owner_membership": {
            "id": membership.id,
            "organization_id": membership.organization_id,
            "user_id": membership.user_id,
            "role": membership.role.value,
            "status": membership.status.value,
        },
    }