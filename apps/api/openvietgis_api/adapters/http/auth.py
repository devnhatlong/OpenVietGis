from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.oidc.provider import (
    OidcProviderNotFoundError,
    OidcProviderRegistry,
)
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.identity_repository import SqlIdentityRepository
from openvietgis_api.config import Settings, get_settings
from openvietgis_api.domains.identity.service import (
    IdentityConflictError,
    IdentityService,
)
from openvietgis_api.security.csrf import make_csrf_token

router = APIRouter(tags=["identity"])


def _safe_return_to(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//") or "://" in value:
        return "/"
    return value


def _registry(settings: Settings) -> OidcProviderRegistry:
    return OidcProviderRegistry(settings)


def _identity_service(session: Session) -> IdentityService:
    return IdentityService(
        SqlIdentityRepository(session),
        SqlAuditRepository(session),
    )


@router.get("/auth/providers")
def list_identity_providers(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[dict[str, str]]:
    return [
        {"id": item.id, "display_name": item.display_name}
        for item in _registry(settings).summaries()
    ]


@router.get("/auth/login/{provider}")
async def begin_login(
    provider: str,
    request: Request,
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    mode: Literal["login", "link"] = Query(default="login"),
    return_to: str | None = Query(default=None),
) -> Response:
    if mode == "link":
        authentication = authenticate_request(request, session, settings)
        if authentication.actor.actor_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        request.session["ovg_link_user_id"] = str(authentication.actor.actor_id)
    else:
        request.session.pop("ovg_link_user_id", None)
    request.session["ovg_return_to"] = _safe_return_to(return_to)
    redirect_uri = (
        settings.api_public_base_url.rstrip("/")
        + f"/api/v1/auth/callback/{provider}"
    )
    try:
        return await _registry(settings).begin_login(
            request,
            provider_name=provider,
            redirect_uri=redirect_uri,
        )
    except OidcProviderNotFoundError as exc:
        raise HTTPException(status_code=400, detail="unknown identity provider") from exc


@router.get("/auth/callback/{provider}", name="complete_login")
async def complete_login(
    provider: str,
    request: Request,
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    try:
        claims = await _registry(settings).complete_login(
            request,
            provider_name=provider,
        )
    except OidcProviderNotFoundError as exc:
        raise HTTPException(status_code=400, detail="unknown identity provider") from exc

    service = _identity_service(session)
    link_user_id = request.session.pop("ovg_link_user_id", None)
    return_to = _safe_return_to(request.session.pop("ovg_return_to", "/"))
    redirect = RedirectResponse(
        url=f"{settings.web_base_url.rstrip('/')}{return_to}",
        status_code=status.HTTP_302_FOUND,
    )

    try:
        if link_user_id is not None:
            service.link_identity(user_id=UUID(link_user_id), claims=claims)
            return redirect
        result = service.login(
            claims,
            session_ttl_seconds=settings.session_ttl_seconds,
        )
    except IdentityConflictError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    redirect.set_cookie(
        settings.session_cookie_name,
        result.session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return redirect


@router.get("/auth/csrf")
def get_csrf(
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    if authentication.raw_session_token is None:
        raise HTTPException(status_code=500, detail="CSRF session unavailable")
    return {
        "token": make_csrf_token(
            authentication.raw_session_token,
            settings.csrf_secret.get_secret_value(),
        )
    }


@router.post("/auth/logout", status_code=204)
def logout(
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> None:
    if authentication.session_id is not None:
        SqlIdentityRepository(session).revoke_web_session(authentication.session_id)