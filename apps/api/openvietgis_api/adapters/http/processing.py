"""R008 Spatial Processing & Durable Jobs HTTP adapter."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.processing_repository import SqlProcessingRepository
from openvietgis_api.domains.processing.domain import (
    ALGORITHM_REGISTRY,
    AlgorithmId,
    ProcessingJobRecord,
)

router = APIRouter(tags=["processing"])
_BASE = "/organizations/{organization_id}/projects/{project_id}"


def _job_wire(job: ProcessingJobRecord) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "organization_id": str(job.organization_id),
        "project_id": str(job.project_id),
        "algorithm_id": job.algorithm_id.value,
        "operation_id": job.operation_id,
        "status": job.status.value,
        "actor_type": job.actor_type,
        "actor_id": str(job.actor_id),
        "input_refs": job.input_refs,
        "parameters": job.parameters,
        "output_name": job.output_name,
        "output_crs": job.output_crs,
        "engine_version": job.engine_version,
        "attempt_count": job.attempt_count,
        "output_source_id": str(job.output_source_id) if job.output_source_id else None,
        "output_layer_id": str(job.output_layer_id) if job.output_layer_id else None,
        "output_content_revision": job.output_content_revision,
        "feature_count": job.feature_count,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


class CreateProcessingJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    algorithm_id: AlgorithmId
    input_layer_id: UUID
    overlay_layer_id: UUID | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_name: str
    operation_id: str
    execute_now: bool = True


@router.get(f"{_BASE}/processing/algorithms")
def list_algorithms(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
) -> dict[str, Any]:
    _ = context_for(auth, organization_id=organization_id, project_id=project_id)
    return {
        "items": [
            {
                "id": d.id.value,
                "name": d.name,
                "description": d.description,
                "required_inputs": list(d.required_inputs),
                "parameters_schema": d.parameters_schema,
            }
            for d in ALGORITHM_REGISTRY.values()
        ]
    }


@router.post(f"{_BASE}/processing/jobs", status_code=201)
def create_processing_job(
    organization_id: UUID,
    project_id: UUID,
    body: CreateProcessingJobRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    repo = SqlProcessingRepository(session)
    job = repo.submit_and_run(
        context=ctx,
        algorithm_id=body.algorithm_id,
        input_layer_id=body.input_layer_id,
        overlay_layer_id=body.overlay_layer_id,
        parameters=body.parameters,
        output_name=body.output_name,
        operation_id=body.operation_id,
        execute_now=body.execute_now,
    )
    return _job_wire(job)


@router.get(f"{_BASE}/processing/jobs")
def list_processing_jobs(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    items = SqlProcessingRepository(session).list_jobs(context=ctx, limit=limit)
    return {"items": [_job_wire(j) for j in items]}


@router.get(f"{_BASE}/processing/jobs/{{job_id}}")
def get_processing_job(
    organization_id: UUID,
    project_id: UUID,
    job_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _job_wire(SqlProcessingRepository(session).get_job(context=ctx, job_id=job_id))


@router.post(f"{_BASE}/processing/jobs/{{job_id}}/cancel")
def cancel_processing_job(
    organization_id: UUID,
    project_id: UUID,
    job_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _job_wire(SqlProcessingRepository(session).cancel_job(context=ctx, job_id=job_id))


@router.post(f"{_BASE}/processing/jobs/{{job_id}}/retry")
def retry_processing_job(
    organization_id: UUID,
    project_id: UUID,
    job_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _job_wire(SqlProcessingRepository(session).retry_job(context=ctx, job_id=job_id))
