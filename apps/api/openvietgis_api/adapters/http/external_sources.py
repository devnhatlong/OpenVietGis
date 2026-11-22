"""R010 External Sources HTTP adapter."""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.external_provider_transport import (
    fetch_provider_bytes,
    fetch_provider_range,
)
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.external_sources_repository import (
    SqlExternalSourcesRepository,
)
from openvietgis_api.domains.external_sources.domain import (
    ExternalConnectionRecord,
    ExternalProtocol,
    sanitize_allowlist_wire,
)
from openvietgis_api.domains.external_sources.provider import (
    approved_profile,
    provider_preview,
    provider_viewport,
)
from openvietgis_api.domains.platform_errors import PlatformForbiddenError

router = APIRouter(tags=["external-sources"])
_ORG = "/organizations/{organization_id}"
_PROJ = f"{_ORG}/projects/{{project_id}}"


def _safe_display_endpoint(endpoint: str) -> str:
    """Never expose query/fragment/userinfo from a legacy registration."""
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return ""
        authority = parsed.hostname + (f":{parsed.port}" if parsed.port is not None else "")
        return urlunsplit((parsed.scheme, authority, parsed.path, "", ""))
    except ValueError:
        return ""


def _conn_wire(c: ExternalConnectionRecord) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "organization_id": str(c.organization_id),
        "project_id": str(c.project_id),
        "allowlist_id": str(c.allowlist_id),
        "name": c.name,
        "protocol": c.protocol.value,
        "endpoint_url": _safe_display_endpoint(c.endpoint_url),
        "layer_identifier": c.layer_identifier,
        "attribution": c.attribution,
        "license_text": c.license_text,
        "crs_codes": list(c.crs_codes),
        "capabilities": c.capabilities,
        "read_only": c.read_only,
        "cache_generation": c.cache_generation,
        "lifecycle": c.lifecycle,
        "availability": "revoked" if c.lifecycle == "revoked" else "unverified",
        "created_at": c.created_at.isoformat(),
    }


class AllowlistHostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hostname: str
    allowed_schemes: list[str] = Field(default_factory=lambda: ["https"])
    allowed_ports: list[int] = Field(default_factory=lambda: [443])
    secret_ref_name: str | None = None


class CreateExternalConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowlist_id: UUID
    name: str
    protocol: ExternalProtocol
    endpoint_url: str
    layer_identifier: str = "default"
    attribution: str = "External Provider"
    license_text: str = "Provider License Terms"
    crs_codes: list[int] = Field(default_factory=lambda: [4326, 3857])


class ExternalViewportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    crs: int
    bbox: list[float] = Field(min_length=4, max_length=4)
    width: int = Field(ge=1, le=512)
    height: int = Field(ge=1, le=512)


@router.post(f"{_ORG}/external-sources/allowlist", status_code=201)
def register_allowlisted_host(
    organization_id: UUID,
    body: AllowlistHostRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id)
    rec = SqlExternalSourcesRepository(session).register_allowlisted_host(
        context=ctx,
        hostname=body.hostname,
        allowed_schemes=body.allowed_schemes,
        allowed_ports=body.allowed_ports,
        secret_ref_name=body.secret_ref_name,
    )
    return sanitize_allowlist_wire(rec)


@router.get(f"{_ORG}/external-sources/allowlist")
def list_allowlisted_hosts(
    organization_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id)
    items = SqlExternalSourcesRepository(session).list_allowlisted_hosts(context=ctx)
    return {"items": [sanitize_allowlist_wire(x) for x in items]}


@router.post(f"{_PROJ}/external-sources", status_code=201)
def create_external_connection(
    organization_id: UUID,
    project_id: UUID,
    body: CreateExternalConnectionRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec = SqlExternalSourcesRepository(session).create_connection(
        context=ctx,
        allowlist_id=body.allowlist_id,
        name=body.name,
        protocol=body.protocol,
        endpoint_url=body.endpoint_url,
        layer_identifier=body.layer_identifier,
        attribution=body.attribution,
        license_text=body.license_text,
        crs_codes=body.crs_codes,
    )
    return _conn_wire(rec)


@router.get(f"{_PROJ}/external-sources")
def list_external_connections(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    items = SqlExternalSourcesRepository(session).list_connections(context=ctx)
    return {"items": [_conn_wire(c) for c in items]}


@router.post(f"{_PROJ}/external-sources/{{connection_id}}/preview")
def preview_external_source(
    organization_id: UUID,
    project_id: UUID,
    connection_id: UUID,
    response: Response,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    """Fresh provider proof of the operator-approved sample, never user geometry."""
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    repository = SqlExternalSourcesRepository(session)
    conn, allowlist = repository.connection_for_provider_request(
        context=ctx, connection_id=connection_id
    )
    profile = approved_profile(conn, allowlist)
    result = provider_preview(profile, fetch_provider_bytes, fetch_provider_range)
    # Recheck live authorization after the bounded outbound request. Row locks
    # prevent provider revocation/cache mutation during this proof transaction.
    current, current_allowlist = repository.connection_for_provider_request(
        context=ctx, connection_id=connection_id
    )
    if approved_profile(current, current_allowlist) != profile:
        raise PlatformForbiddenError("provider profile changed", code="PROVIDER_DISABLED")
    response.headers["Cache-Control"] = "no-store"
    return {**result, "connection_id": str(conn.id), "cache_generation": conn.cache_generation}


@router.post(f"{_PROJ}/external-sources/{{connection_id}}/viewport")
def preview_external_viewport(
    organization_id: UUID,
    project_id: UUID,
    connection_id: UUID,
    body: ExternalViewportRequest,
    response: Response,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    """Only approved COG regions; user coordinates never reach the outbound URL."""
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    repository = SqlExternalSourcesRepository(session)
    conn, allowlist = repository.connection_for_provider_request(
        context=ctx, connection_id=connection_id
    )
    profile = approved_profile(conn, allowlist)
    x0, y0, x1, y1 = body.bbox
    result = provider_viewport(
        profile,
        fetch_provider_range,
        crs=body.crs,
        bbox=(x0, y0, x1, y1),
        width=body.width,
        height=body.height,
    )
    current, current_allowlist = repository.connection_for_provider_request(
        context=ctx, connection_id=connection_id
    )
    if approved_profile(current, current_allowlist) != profile:
        raise PlatformForbiddenError("provider profile changed", code="PROVIDER_DISABLED")
    response.headers["Cache-Control"] = "no-store"
    return {**result, "connection_id": str(conn.id), "cache_generation": conn.cache_generation}


@router.post(f"{_PROJ}/external-sources/{{connection_id}}/invalidate-cache")
def invalidate_external_cache(
    organization_id: UUID,
    project_id: UUID,
    connection_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _conn_wire(
        SqlExternalSourcesRepository(session).invalidate_cache(
            context=ctx, connection_id=connection_id
        )
    )


@router.post(f"{_PROJ}/external-sources/{{connection_id}}/revoke")
def revoke_external_connection(
    organization_id: UUID,
    project_id: UUID,
    connection_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _conn_wire(
        SqlExternalSourcesRepository(session).revoke_connection(
            context=ctx, connection_id=connection_id
        )
    )
