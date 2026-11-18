from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.db import session_scope
from openvietgis_api.adapters.persistence.rls import set_request_context
from openvietgis_api.config import Settings, get_settings
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.security.csrf import verify_csrf_token
from openvietgis_api.security.sessions import parse_session_token, verify_session_token


@dataclass(frozen=True, slots=True)
class AuthenticatedRequest:
    actor: Actor
    session_id: UUID | None
    raw_session_token: str | None
    identity_link_id: UUID | None = None


def get_db_session() -> Iterator[Session]:
    yield from session_scope()


def _secret_value(settings_value: object | None, name: str) -> str:
    if settings_value is None:
        raise RuntimeError(f"{name} is not configured")
    get_secret_value = getattr(settings_value, "get_secret_value", None)
    if get_secret_value is None:
        return str(settings_value)
    return str(get_secret_value())


def authenticate_request(
    request: Request,
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedRequest:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="service credentials are not enabled yet",
        )

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )

    try:
        parsed = parse_session_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid session",
        ) from exc

    row = (
        session.execute(
            text(
                """
                SELECT s.id, s.secret_hash, s.expires_at, s.revoked_at, s.identity_link_id,
                       u.id AS user_id, u.display_name, u.status AS user_status
                FROM identity.web_sessions AS s
                JOIN identity.users AS u ON u.id = s.user_id
                JOIN identity.identity_links AS l
                    ON l.id = s.identity_link_id AND l.user_id = s.user_id
                WHERE s.id = :session_id
                """
            ),
            {"session_id": parsed.session_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    if row["revoked_at"] is not None or row["user_status"] != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session revoked")
    expires_at = row["expires_at"]
    if expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired")
    try:
        verify_session_token(token, row["secret_hash"])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid session",
        ) from exc

    actor = Actor(
        actor_type="human",
        actor_id=row["user_id"],
        display_name=row["display_name"],
    )
    set_request_context(
        session,
        organization_id=None,
        actor_user_id=actor.actor_id,
    )
    return AuthenticatedRequest(
        actor=actor,
        session_id=row["id"],
        raw_session_token=token,
        identity_link_id=row["identity_link_id"],
    )


def require_csrf(
    request: Request,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedRequest:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return authentication
    if authentication.raw_session_token is None:
        return authentication

    candidate = request.headers.get("x-openvietgis-csrf", "")
    csrf_secret = settings.csrf_secret.get_secret_value()
    if not candidate or not verify_csrf_token(
        authentication.raw_session_token,
        csrf_secret,
        candidate,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    return authentication
