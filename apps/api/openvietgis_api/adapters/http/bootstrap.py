from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_human_request,
    get_db_session,
    verify_request_csrf,
)
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.config import Settings, get_settings
from openvietgis_api.domains.bootstrap.service import (
    BootstrapAlreadyInitializedError,
    BootstrapAuthorizationError,
    BootstrapService,
    InvalidBootstrapInputError,
)

router = APIRouter(tags=["bootstrap"])


class BootstrapInitializeRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    organization_slug: str = Field(min_length=1, max_length=120)


@router.get("/bootstrap/status")
def get_bootstrap_status(
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, bool]:
    return {"initialized": SqlPlatformRepository(session).is_initialized()}


@router.post("/bootstrap/initialize", status_code=status.HTTP_201_CREATED)
def initialize_bootstrap(
    payload: BootstrapInitializeRequest,
    request: Request,
    authentication: Annotated[
        AuthenticatedRequest,
        Depends(authenticate_human_request),
    ],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    verify_request_csrf(request, authentication, settings)

    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="bootstrap authority required",
        )
    presented_authority = authorization[7:].strip()

    try:
        result = BootstrapService(
            SqlPlatformRepository(session),
            SqlTenancyRepository(session),
            SqlAuditRepository(session),
        ).initialize(
            actor=authentication.actor,
            presented_authority=presented_authority,
            configured_authority=settings.bootstrap_secret.get_secret_value(),
            organization_name=payload.organization_name,
            organization_slug=payload.organization_slug,
        )
    except BootstrapAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid bootstrap authority",
        ) from exc
    except BootstrapAlreadyInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="installation already initialized",
        ) from exc
    except InvalidBootstrapInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "organization_id": result.organization_id,
        "owner_membership_id": result.owner_membership_id,
    }
