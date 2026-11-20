"""Project-scoped R005 Import, Export, Durable Job, and Artifact HTTP adapter."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.formats.registry import VectorFormatRegistry
from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.transfer_repository import SqlTransferRepository
from openvietgis_api.adapters.storage.local_object_store import LocalObjectStore
from openvietgis_api.config import get_settings
from openvietgis_api.domains.transfers.domain import (
    MAX_UPLOAD_BYTES,
    DerivedArtifact,
    SourceAsset,
    TransferFormat,
    TransferJob,
)
from openvietgis_api.domains.transfers.ports import TransferLimitExceededError
from openvietgis_api.domains.transfers.service import TransferService

router = APIRouter(tags=["transfers"])
_BASE = "/organizations/{organization_id}/projects/{project_id}"


def _service(session: Session) -> TransferService:
    settings = get_settings()
    return TransferService(
        repository=SqlTransferRepository(session),
        store=LocalObjectStore(settings.artifact_store_dir),
        codec=VectorFormatRegistry(),
    )


def _asset_wire(asset: SourceAsset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "organization_id": str(asset.organization_id),
        "project_id": str(asset.project_id),
        "filename": asset.filename,
        "detected_format": asset.detected_format.value,
        "byte_size": asset.byte_size,
        "sha256": asset.sha256,
        "uploaded_by_display": asset.uploaded_by_display,
        "created_at": asset.created_at.isoformat(),
    }


def _artifact_wire(artifact: DerivedArtifact) -> dict[str, Any]:
    return {
        "id": str(artifact.id),
        "organization_id": str(artifact.organization_id),
        "project_id": str(artifact.project_id),
        "job_id": str(artifact.job_id),
        "source_id": str(artifact.source_id),
        "layer_id": str(artifact.layer_id),
        "source_content_revision": artifact.source_content_revision,
        "source_schema_revision": artifact.source_schema_revision,
        "output_format": artifact.output_format.value,
        "output_crs": artifact.output_crs,
        "filename": artifact.filename,
        "content_type": artifact.content_type,
        "byte_size": artifact.byte_size,
        "sha256": artifact.sha256,
        "state": artifact.state.value,
        "created_by_display": artifact.created_by_display,
        "created_at": artifact.created_at.isoformat(),
        "expires_at": artifact.expires_at.isoformat(),
        "comparison_report": artifact.comparison_report,
    }


def _job_wire(job: TransferJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "organization_id": str(job.organization_id),
        "project_id": str(job.project_id),
        "operation_id": str(job.operation_id),
        "kind": job.kind.value,
        "request_fingerprint": job.request_fingerprint,
        "status": job.status.value,
        "actor_type": job.actor_type.value,
        "actor_id": str(job.actor_id),
        "actor_display_snapshot": job.actor_display_snapshot,
        "source_asset_id": str(job.source_asset_id) if job.source_asset_id else None,
        "target_source_id": str(job.target_source_id) if job.target_source_id else None,
        "target_layer_id": str(job.target_layer_id) if job.target_layer_id else None,
        "source_content_revision": job.source_content_revision,
        "source_schema_revision": job.source_schema_revision,
        "artifact_id": str(job.artifact_id) if job.artifact_id else None,
        "attempt_count": job.attempt_count,
        "inspection_report": job.inspection_report,
        "result_report": job.result_report,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "attempts": [
            {
                "id": str(a.id),
                "attempt_number": a.attempt_number,
                "status": a.status,
                "actor_type": a.actor_type.value,
                "actor_id": str(a.actor_id),
                "started_at": a.started_at.isoformat(),
                "finished_at": a.finished_at.isoformat() if a.finished_at else None,
                "error_code": a.error_code,
                "error_message": a.error_message,
            }
            for a in job.attempts
        ],
        "artifact": _artifact_wire(job.artifact) if job.artifact is not None else None,
    }


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportInspectBody(StrictBody):
    source_asset_id: UUID
    selected_member: str | None = None
    declared_source_crs: int | None = None
    target_crs: int | None = None
    declared_encoding: str | None = None


class ImportConfirmBody(StrictBody):
    operation_id: UUID
    source_asset_id: UUID
    selected_member: str = Field(min_length=1, max_length=200)
    source_name: str = Field(min_length=1, max_length=200)
    layer_name: str = Field(min_length=1, max_length=200)
    declared_source_crs: int | None = None
    target_crs: int | None = None
    declared_encoding: str | None = None
    approved_conversions: list[str] = Field(default_factory=list)
    inspection_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class ExportPreviewBody(StrictBody):
    layer_id: UUID
    content_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    schema_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_format: TransferFormat
    output_crs: int


class ExportConfirmBody(StrictBody):
    operation_id: UUID
    layer_id: UUID
    content_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    schema_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_format: TransferFormat
    output_crs: int
    approved_disclosures: list[str] = Field(default_factory=list)
    preview_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post(
    _BASE + "/imports/upload",
    status_code=201,
)
def upload_import_asset(
    organization_id: UUID,
    project_id: UUID,
    file: Annotated[UploadFile, File()],
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise TransferLimitExceededError(
                "UPLOAD_SIZE_EXCEEDED",
                f"Uploaded file exceeds maximum allowed size of {MAX_UPLOAD_BYTES} bytes.",
            )
        chunks.append(chunk)
    payload = b"".join(chunks)
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    asset, report = _service(session).upload_and_inspect(
        context=ctx,
        filename=file.filename or "upload.bin",
        payload=payload,
    )
    return {"asset": _asset_wire(asset), "inspection": report.to_wire()}


@router.post(
    _BASE + "/imports/inspect",
)
def inspect_import_asset(
    organization_id: UUID,
    project_id: UUID,
    body: ImportInspectBody,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    asset, report = _service(session).inspect_asset(
        context=ctx,
        source_asset_id=body.source_asset_id,
        selected_member=body.selected_member,
        declared_source_crs=body.declared_source_crs,
        target_crs=body.target_crs,
        declared_encoding=body.declared_encoding,
    )
    return {"asset": _asset_wire(asset), "inspection": report.to_wire()}


@router.post(
    _BASE + "/imports/confirm",
)
def confirm_import(
    organization_id: UUID,
    project_id: UUID,
    body: ImportConfirmBody,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    job = _service(session).confirm_import(
        context=ctx,
        operation_id=body.operation_id,
        source_asset_id=body.source_asset_id,
        selected_member=body.selected_member,
        source_name=body.source_name,
        layer_name=body.layer_name,
        declared_source_crs=body.declared_source_crs,
        target_crs=body.target_crs,
        declared_encoding=body.declared_encoding,
        approved_conversions=body.approved_conversions,
        inspection_fingerprint=body.inspection_fingerprint,
    )
    return _job_wire(job)


@router.post(
    _BASE + "/exports/preview",
)
def preview_export(
    organization_id: UUID,
    project_id: UUID,
    body: ExportPreviewBody,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    report = _service(session).preview_export(
        context=ctx,
        layer_id=body.layer_id,
        content_revision=body.content_revision,
        schema_revision=body.schema_revision,
        output_format=body.output_format,
        output_crs=body.output_crs,
    )
    return report.to_wire()


@router.post(
    _BASE + "/exports/confirm",
)
def confirm_export(
    organization_id: UUID,
    project_id: UUID,
    body: ExportConfirmBody,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    job = _service(session).confirm_export(
        context=ctx,
        operation_id=body.operation_id,
        layer_id=body.layer_id,
        content_revision=body.content_revision,
        schema_revision=body.schema_revision,
        output_format=body.output_format,
        output_crs=body.output_crs,
        approved_disclosures=body.approved_disclosures,
        preview_fingerprint=body.preview_fingerprint,
    )
    return _job_wire(job)


@router.get(_BASE + "/jobs")
def list_transfer_jobs(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    jobs = _service(session).list_jobs(context=ctx, limit=limit)
    return {"items": [_job_wire(j) for j in jobs]}


@router.get(_BASE + "/jobs/{job_id}")
def get_transfer_job(
    organization_id: UUID,
    project_id: UUID,
    job_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    job = _service(session).get_job(context=ctx, job_id=job_id)
    return _job_wire(job)


@router.post(
    _BASE + "/jobs/{job_id}/cancel",
)
def cancel_transfer_job(
    organization_id: UUID,
    project_id: UUID,
    job_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    job = _service(session).cancel_job(context=ctx, job_id=job_id)
    return _job_wire(job)


@router.post(
    _BASE + "/jobs/{job_id}/retry",
)
def retry_transfer_job(
    organization_id: UUID,
    project_id: UUID,
    job_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    job = _service(session).retry_job(context=ctx, job_id=job_id)
    return _job_wire(job)


@router.get(_BASE + "/artifacts/{artifact_id}")
def get_derived_artifact(
    organization_id: UUID,
    project_id: UUID,
    artifact_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    artifact = _service(session).get_artifact(context=ctx, artifact_id=artifact_id)
    return _artifact_wire(artifact)


@router.get(_BASE + "/artifacts/{artifact_id}/download")
def download_derived_artifact(
    organization_id: UUID,
    project_id: UUID,
    artifact_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    artifact, data = _service(session).download_artifact(context=ctx, artifact_id=artifact_id)
    return Response(
        content=data,
        media_type=artifact.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Content-SHA256": artifact.sha256,
            "Cache-Control": "no-store",
        },
    )
