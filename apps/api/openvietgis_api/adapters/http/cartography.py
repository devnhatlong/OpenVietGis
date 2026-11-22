"""R009 Cartography styles, print layouts, and PNG/PDF output HTTP adapter."""

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
from openvietgis_api.adapters.persistence.cartography_repository import SqlCartographyRepository
from openvietgis_api.config import get_settings
from openvietgis_api.domains.cartography.domain import (
    LayerStyleRecord,
    Orientation,
    PaperSize,
    PrintExportRecord,
    PrintFormat,
    PrintLayoutRecord,
    StyleMode,
)

router = APIRouter(tags=["cartography"])
_BASE = "/organizations/{organization_id}/projects/{project_id}"


def _repo(session: Session) -> SqlCartographyRepository:
    return SqlCartographyRepository(session, Path(get_settings().artifact_store_dir))


def _style_wire(s: LayerStyleRecord) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "layer_id": str(s.layer_id),
        "mode": s.mode.value,
        "style_spec": s.style_spec,
        "label_field": s.label_field,
        "legend_items": s.legend_items,
        "revision": s.revision,
        "updated_at": s.updated_at.isoformat(),
    }


def _layout_wire(lo: PrintLayoutRecord) -> dict[str, Any]:
    return {
        "id": str(lo.id),
        "name": lo.name,
        "title": lo.title,
        "paper_size": lo.paper_size.value,
        "orientation": lo.orientation.value,
        "crs_code": lo.crs_code,
        "attribution": lo.attribution,
        "show_north_arrow": lo.show_north_arrow,
        "show_scale_bar": lo.show_scale_bar,
        "show_legend": lo.show_legend,
        "layer_ids": lo.layer_ids,
        "extent": lo.extent,
        "created_at": lo.created_at.isoformat(),
    }


def _export_wire(ex: PrintExportRecord) -> dict[str, Any]:
    return {
        "id": str(ex.id),
        "layout_id": str(ex.layout_id),
        "output_format": ex.output_format.value,
        "dpi": ex.dpi,
        "scale_denominator": ex.scale_denominator,
        "scale_accuracy_note": ex.scale_accuracy_note,
        "revision_manifest": ex.revision_manifest,
        "sha256": ex.sha256,
        "byte_size": ex.byte_size,
        "created_at": ex.created_at.isoformat(),
    }


class UpsertStyleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: StyleMode
    style_spec: dict[str, Any]
    label_field: str | None = None


class CreateLayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    title: str
    paper_size: PaperSize = PaperSize.A4
    orientation: Orientation = Orientation.LANDSCAPE
    crs_code: int = 4326
    attribution: str = "OpenVietGIS Project Data"
    layer_ids: list[UUID]
    show_north_arrow: bool = True
    show_scale_bar: bool = True
    show_legend: bool = True
    extent: dict[str, float] | None = None


class PreviewLayoutExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_format: PrintFormat = PrintFormat.PNG
    dpi: int = 150


class ExportLayoutRequest(PreviewLayoutExportRequest):
    expected_revision_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.put(f"{_BASE}/cartography/layers/{{layer_id}}/style")
def upsert_layer_style(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    body: UpsertStyleRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec = _repo(session).upsert_layer_style(
        context=ctx,
        layer_id=layer_id,
        mode=body.mode,
        style_spec=body.style_spec,
        label_field=body.label_field,
    )
    return _style_wire(rec)


@router.get(f"{_BASE}/cartography/layers/{{layer_id}}/style")
def get_layer_style(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec = _repo(session).get_layer_style(context=ctx, layer_id=layer_id)
    return {"style": _style_wire(rec) if rec else None}


@router.post(f"{_BASE}/cartography/layouts", status_code=201)
def create_layout(
    organization_id: UUID,
    project_id: UUID,
    body: CreateLayoutRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec = _repo(session).create_layout(
        context=ctx,
        name=body.name,
        title=body.title,
        paper_size=body.paper_size,
        orientation=body.orientation,
        crs_code=body.crs_code,
        attribution=body.attribution,
        layer_ids=body.layer_ids,
        show_north_arrow=body.show_north_arrow,
        show_scale_bar=body.show_scale_bar,
        show_legend=body.show_legend,
        extent=body.extent,
    )
    return _layout_wire(rec)


@router.get(f"{_BASE}/cartography/layouts")
def list_layouts(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return {"items": [_layout_wire(lo) for lo in _repo(session).list_layouts(context=ctx)]}


@router.post(f"{_BASE}/cartography/layouts/{{layout_id}}/exports/preview")
def preview_layout_export(
    organization_id: UUID,
    project_id: UUID,
    layout_id: UUID,
    body: PreviewLayoutExportRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _repo(session).preview_export(
        context=ctx, layout_id=layout_id, output_format=body.output_format, dpi=body.dpi
    )


@router.post(f"{_BASE}/cartography/layouts/{{layout_id}}/exports", status_code=201)
def export_layout(
    organization_id: UUID,
    project_id: UUID,
    layout_id: UUID,
    body: ExportLayoutRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec = _repo(session).export_layout(
        context=ctx,
        layout_id=layout_id,
        output_format=body.output_format,
        dpi=body.dpi,
        expected_revision_fingerprint=body.expected_revision_fingerprint,
    )
    return _export_wire(rec)


@router.get(f"{_BASE}/cartography/exports")
def list_exports(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return {"items": [_export_wire(e) for e in _repo(session).list_exports(context=ctx)]}


@router.get(f"{_BASE}/cartography/exports/{{export_id}}/download")
def download_export(
    organization_id: UUID,
    project_id: UUID,
    export_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec, data = _repo(session).download_export(context=ctx, export_id=export_id)
    media = "image/png" if rec.output_format == PrintFormat.PNG else "application/pdf"
    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="map-{rec.id}.{rec.output_format.value}"',
            "X-Content-SHA256": rec.sha256,
        },
    )
