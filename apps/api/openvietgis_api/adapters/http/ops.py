"""R015 Production Operations, Readiness, Prometheus Metrics & Entitlements HTTP adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.ops_repository import SqlOpsRepository
from openvietgis_api.config import get_settings
from openvietgis_api.domains.ops.domain import (
    RELEASE_CAPABILITIES,
    OrganizationEntitlementRecord,
)

router = APIRouter(tags=["operations"])


def _ent_wire(e: OrganizationEntitlementRecord) -> dict[str, Any]:
    return {
        "organization_id": str(e.organization_id),
        "deployment_profile": e.deployment_profile,
        "plan_tier": e.plan_tier,
        "max_projects": e.max_projects,
        "max_storage_mb": e.max_storage_mb,
        "features_enabled": e.features_enabled,
        "updated_at": e.updated_at.isoformat(),
        "authorization_distinct": True,
        "data_deletion_on_plan_change": False,
    }


class UpsertEntitlementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deployment_profile: str = "self_host_team"
    plan_tier: str = "self_host_community"
    max_projects: int = Field(default=100, ge=1)
    max_storage_mb: int = Field(default=10240, ge=64)
    features_enabled: list[str] = Field(
        default_factory=lambda: ["R001", "R002", "R003", "R004", "R005", "R006", "R007"]
    )


@router.get("/ops/health/live")
def ops_health_live() -> dict[str, str]:
    return {"status": "alive", "service": "openvietgis-api"}


@router.get("/ops/health/ready")
def ops_health_ready(
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    storage = Path(get_settings().artifact_store_dir)
    return SqlOpsRepository(session).check_readiness(storage)


@router.get("/ops/metrics")
def ops_metrics(
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    text_body = SqlOpsRepository(session).render_prometheus_metrics()
    return Response(content=text_body, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/ops/release-capabilities")
def ops_release_capabilities() -> dict[str, Any]:
    return {
        "profile": "self_host_team",
        "total_releases": len(RELEASE_CAPABILITIES),
        "items": RELEASE_CAPABILITIES,
    }


@router.get("/organizations/{organization_id}/ops/entitlement")
def get_org_entitlement(
    organization_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id)
    rec = SqlOpsRepository(session).get_entitlement(context=ctx)
    if rec is None:
        return {
            "organization_id": str(organization_id),
            "deployment_profile": "self_host_team",
            "plan_tier": "self_host_community",
            "max_projects": 100,
            "max_storage_mb": 10240,
            "features_enabled": [c["id"] for c in RELEASE_CAPABILITIES],
            "authorization_distinct": True,
            "data_deletion_on_plan_change": False,
        }
    return _ent_wire(rec)


@router.put("/organizations/{organization_id}/ops/entitlement")
def upsert_org_entitlement(
    organization_id: UUID,
    body: UpsertEntitlementRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id)
    rec = SqlOpsRepository(session).upsert_entitlement(
        context=ctx,
        deployment_profile=body.deployment_profile,
        plan_tier=body.plan_tier,
        max_projects=body.max_projects,
        max_storage_mb=body.max_storage_mb,
        features_enabled=body.features_enabled,
    )
    return _ent_wire(rec)
