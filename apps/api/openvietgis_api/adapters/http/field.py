"""R013 Field & Offline packages and outbox sync HTTP adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.field_repository import SqlFieldRepository
from openvietgis_api.config import get_settings
from openvietgis_api.domains.field.domain import OfflinePackageRecord, SyncBatchRecord

router = APIRouter(tags=["field-offline"])
_BASE = "/organizations/{organization_id}/projects/{project_id}"


def _repo(session: Session) -> SqlFieldRepository:
    return SqlFieldRepository(session, Path(get_settings().artifact_store_dir))


def _pkg_wire(p: OfflinePackageRecord) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": p.name,
        "profile": p.profile,
        "aoi_bbox": p.aoi_bbox,
        "crs_code": p.crs_code,
        "layer_pins": p.layer_pins,
        "feature_count": p.feature_count,
        "sha256": p.sha256,
        "byte_size": p.byte_size,
        "expires_at": p.expires_at.isoformat(),
        "revoked_at": p.revoked_at.isoformat() if p.revoked_at else None,
        "created_at": p.created_at.isoformat(),
    }


def _sync_wire(s: SyncBatchRecord) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "package_id": str(s.package_id),
        "operation_id": s.operation_id,
        "status": s.status,
        "submitted_ops_count": s.submitted_ops_count,
        "applied_changeset_ids": s.applied_changeset_ids,
        "conflicts": s.conflicts,
        "operation_receipts": s.operation_receipts,
        "created_at": s.created_at.isoformat(),
    }


class CreateOfflinePackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    layer_id: UUID
    aoi_bbox: dict[str, float]
    ttl_hours: int = 72
    local_storage_confirmed: bool = False


class SyncOutboxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str
    operations: list[dict[str, Any]]


@router.post(f"{_BASE}/field/packages", status_code=201)
def create_offline_package(
    organization_id: UUID,
    project_id: UUID,
    body: CreateOfflinePackageRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _pkg_wire(
        _repo(session).create_package(
            context=ctx,
            name=body.name,
            layer_id=body.layer_id,
            aoi_bbox=body.aoi_bbox,
            ttl_hours=body.ttl_hours,
            local_storage_confirmed=body.local_storage_confirmed,
        )
    )


@router.get(f"{_BASE}/field/packages")
def list_offline_packages(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return {"items": [_pkg_wire(p) for p in _repo(session).list_packages(context=ctx)]}


@router.get(f"{_BASE}/field/packages/{{package_id}}/download")
def download_offline_package(
    organization_id: UUID,
    project_id: UUID,
    package_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    pkg, data = _repo(session).download_package(context=ctx, package_id=package_id)
    return Response(
        content=data,
        media_type="application/geopackage+sqlite3",
        headers={
            "Content-Disposition": f'attachment; filename="offline-{pkg.id}.gpkg"',
            "X-Content-SHA256": pkg.sha256,
            "Cache-Control": "no-store",
        },
    )


@router.get(f"{_BASE}/field/packages/{{package_id}}/snapshot")
def download_browser_snapshot(
    organization_id: UUID,
    project_id: UUID,
    package_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    pkg, payload = _repo(session).download_snapshot(context=ctx, package_id=package_id)
    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Cache-Control": "no-store",
            "X-Content-SHA256": str(pkg.layer_pins[0]["snapshot_sha256"]),
        },
    )


@router.post(f"{_BASE}/field/packages/{{package_id}}/revoke")
def revoke_offline_package(
    organization_id: UUID,
    project_id: UUID,
    package_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _pkg_wire(_repo(session).revoke_package(context=ctx, package_id=package_id))


@router.post(f"{_BASE}/field/packages/{{package_id}}/sync", status_code=201)
def sync_offline_outbox(
    organization_id: UUID,
    project_id: UUID,
    package_id: UUID,
    body: SyncOutboxRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _sync_wire(
        _repo(session).sync_outbox(
            context=ctx,
            package_id=package_id,
            operation_id=body.operation_id,
            operations=body.operations,
        )
    )
