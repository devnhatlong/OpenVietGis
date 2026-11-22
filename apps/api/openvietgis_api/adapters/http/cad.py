"""R012 CAD Interoperability (2D DXF) & Precision COGO HTTP adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.cad_repository import SqlCadRepository
from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.config import get_settings
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.cad.domain import (
    CadConversionRecord,
    CadUnit,
    compute_line_intersection,
    compute_parallel_offset,
    compute_precision_snap,
    compute_traverse_point,
)
from openvietgis_api.domains.platform_errors import PlatformValidationError

router = APIRouter(tags=["cad"])
_BASE = "/organizations/{organization_id}/projects/{project_id}"


def _repo(session: Session) -> SqlCadRepository:
    return SqlCadRepository(session, Path(get_settings().artifact_store_dir))


def _conv_wire(c: CadConversionRecord) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "direction": c.direction,
        "cad_format": c.cad_format,
        "filename": c.filename,
        "units": c.units.value,
        "crs_code": c.crs_code,
        "status": c.status,
        "entity_summary": c.entity_summary,
        "loss_report": c.loss_report,
        "sha256": c.sha256,
        "byte_size": c.byte_size,
        "source_id": str(c.source_id) if c.source_id else None,
        "layer_id": str(c.layer_id) if c.layer_id else None,
        "content_revision": c.content_revision,
        "created_at": c.created_at.isoformat(),
    }


class ExportDxfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layer_id: UUID
    units: CadUnit
    expected_content_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledge_attribute_loss: bool = False


class CogoTraverseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: tuple[float, float]
    distance: float
    azimuth_degrees: float


class CogoIntersectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seg_a: tuple[tuple[float, float], tuple[float, float]]
    seg_b: tuple[tuple[float, float], tuple[float, float]]


class CogoOffsetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment: tuple[tuple[float, float], tuple[float, float]]
    offset_distance: float


class CogoSnapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: tuple[float, float]
    segments: list[tuple[tuple[float, float], tuple[float, float]]]
    tolerance: float


@router.post(f"{_BASE}/cad/inspect")
def inspect_cad_file(
    organization_id: UUID,
    project_id: UUID,
    file: Annotated[UploadFile, File()],
    units: Annotated[CadUnit, Form()],
    crs_code: Annotated[int, Form()],
    curve_tolerance_m: Annotated[float | None, Form()] = None,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)] = ...,  # type: ignore[assignment]
    session: Annotated[Session, Depends(get_db_session, scope="function")] = ...,  # type: ignore[assignment]
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    payload = file.file.read(25 * 1024 * 1024 + 1)
    return _repo(session).inspect_dxf(
        context=ctx,
        filename=file.filename or "drawing.dxf",
        payload=payload,
        units=units,
        crs_code=crs_code,
        curve_tolerance_m=curve_tolerance_m,
    )


@router.post(f"{_BASE}/cad/import", status_code=201)
def import_cad_file(
    organization_id: UUID,
    project_id: UUID,
    file: Annotated[UploadFile, File()],
    units: Annotated[CadUnit, Form()],
    crs_code: Annotated[int, Form()],
    layer_name: Annotated[str, Form()] = "CAD Import",
    curve_tolerance_m: Annotated[float | None, Form()] = None,
    acknowledge_loss: Annotated[bool, Form()] = False,
    expected_sha256: Annotated[str | None, Form()] = None,
    expected_inspection_fingerprint: Annotated[str | None, Form()] = None,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)] = ...,  # type: ignore[assignment]
    session: Annotated[Session, Depends(get_db_session, scope="function")] = ...,  # type: ignore[assignment]
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    cap = 25 * 1024 * 1024
    payload = file.file.read(cap + 1)
    if len(payload) > cap:
        raise PlatformValidationError("CAD upload exceeds 25 MiB limit", code="CAD_FILE_LIMIT")
    rec = _repo(session).import_cad(
        context=ctx,
        filename=file.filename or "drawing.dxf",
        payload=payload,
        layer_name=layer_name,
        units=units,
        crs_code=crs_code,
        curve_tolerance_m=curve_tolerance_m,
        acknowledge_loss=acknowledge_loss,
        expected_sha256=expected_sha256,
        expected_inspection_fingerprint=expected_inspection_fingerprint,
    )
    return _conv_wire(rec)


@router.post(f"{_BASE}/cad/export")
def export_cad_dxf(
    organization_id: UUID,
    project_id: UUID,
    body: ExportDxfRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec, data = _repo(session).export_dxf(
        context=ctx,
        layer_id=body.layer_id,
        units=body.units,
        expected_content_revision=body.expected_content_revision,
        acknowledge_attribute_loss=body.acknowledge_attribute_loss,
    )
    return Response(
        content=data,
        media_type="application/dxf",
        headers={
            "Content-Disposition": f'attachment; filename="{rec.filename}"',
            "X-Content-SHA256": rec.sha256,
            "X-CAD-Conversion-Id": str(rec.id),
        },
    )


@router.get(f"{_BASE}/cad/conversions")
def list_cad_conversions(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return {"items": [_conv_wire(c) for c in _repo(session).list_conversions(context=ctx)]}


def _planar_preview(result: dict[str, Any]) -> dict[str, Any]:
    # These operations receive caller-supplied coordinates only, not a verified
    # GIS source/revision. They must not imply a survey-grade CRS or edit.
    return result | {
        "coordinate_reference": "unreferenced_planar_input",
        "units": "input_coordinate_units",
        "survey_grade": False,
        "published": False,
    }


@router.post(f"{_BASE}/cad/precision/traverse")
def cogo_traverse(
    organization_id: UUID,
    project_id: UUID,
    body: CogoTraverseRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    context = context_for(auth, organization_id=organization_id, project_id=project_id)
    prepare_project_scope(session, context, permission=Permission.PROJECT_READ)
    return _planar_preview(
        compute_traverse_point(
            origin=body.origin, distance=body.distance, azimuth_degrees=body.azimuth_degrees
        )
    )


@router.post(f"{_BASE}/cad/precision/intersection")
def cogo_intersection(
    organization_id: UUID,
    project_id: UUID,
    body: CogoIntersectionRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    context = context_for(auth, organization_id=organization_id, project_id=project_id)
    prepare_project_scope(session, context, permission=Permission.PROJECT_READ)
    return _planar_preview(compute_line_intersection(seg_a=body.seg_a, seg_b=body.seg_b))


@router.post(f"{_BASE}/cad/precision/offset")
def cogo_offset(
    organization_id: UUID,
    project_id: UUID,
    body: CogoOffsetRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    context = context_for(auth, organization_id=organization_id, project_id=project_id)
    prepare_project_scope(session, context, permission=Permission.PROJECT_READ)
    return _planar_preview(
        compute_parallel_offset(segment=body.segment, offset_distance=body.offset_distance)
    )


@router.post(f"{_BASE}/cad/precision/snap")
def cogo_snap(
    organization_id: UUID,
    project_id: UUID,
    body: CogoSnapRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    context = context_for(auth, organization_id=organization_id, project_id=project_id)
    prepare_project_scope(session, context, permission=Permission.PROJECT_READ)
    return _planar_preview(
        compute_precision_snap(target=body.target, segments=body.segments, tolerance=body.tolerance)
    )
