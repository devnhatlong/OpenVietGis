"""R006 Editing & Change History HTTP adapter."""

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
from openvietgis_api.adapters.persistence.editing_repository import SqlEditingRepository
from openvietgis_api.domains.editing.domain import (
    ChangesetOperationRecord,
    ChangesetRecord,
    EditOperationInput,
    EditOpType,
    snap_point_to_candidates,
)

router = APIRouter(tags=["editing"])
_BASE = "/organizations/{organization_id}/projects/{project_id}"


def _op_wire(op: ChangesetOperationRecord) -> dict[str, Any]:
    return {
        "id": str(op.id),
        "ordinal": op.ordinal,
        "op_type": op.op_type.value,
        "feature_id": op.feature_id,
        "before_geometry": op.before_geometry,
        "after_geometry": op.after_geometry,
        "before_properties": op.before_properties,
        "after_properties": op.after_properties,
        "created_at": op.created_at.isoformat(),
    }


def _cs_wire(cs: ChangesetRecord) -> dict[str, Any]:
    return {
        "id": str(cs.id),
        "organization_id": str(cs.organization_id),
        "project_id": str(cs.project_id),
        "source_id": str(cs.source_id),
        "actor_type": cs.actor_type,
        "actor_id": str(cs.actor_id),
        "actor_display_snapshot": cs.actor_display_snapshot,
        "operation_id": cs.operation_id,
        "base_content_revision": cs.base_content_revision,
        "resulting_content_revision": cs.resulting_content_revision,
        "base_catalog_revision": cs.base_catalog_revision,
        "resulting_catalog_revision": cs.resulting_catalog_revision,
        "summary": cs.summary,
        "status": cs.status,
        "operation_count": cs.operation_count,
        "audit_event_id": str(cs.audit_event_id),
        "reverted_from_changeset_id": str(cs.reverted_from_changeset_id)
        if cs.reverted_from_changeset_id
        else None,
        "created_at": cs.created_at.isoformat(),
        "operations": [_op_wire(o) for o in cs.operations],
    }


class EditOperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op_type: EditOpType
    feature_id: str
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None


class CommitChangesetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_content_revision: str
    operation_id: str
    summary: str = Field(default="Feature edit", max_length=500)
    operations: list[EditOperationRequest]


class RevertChangesetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str
    summary: str | None = None


class SnapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: tuple[float, float]
    vertices: list[tuple[float, float]] = Field(default_factory=list)
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = Field(default_factory=list)
    tolerance: float = Field(gt=0.0, le=10000.0)


@router.post(f"{_BASE}/sources/{{source_id}}/changesets", status_code=201)
def commit_changeset(
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    body: CommitChangesetRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    repo = SqlEditingRepository(session)
    cs = repo.commit_changeset(
        context=ctx,
        source_id=source_id,
        base_content_revision=body.base_content_revision,
        operation_id=body.operation_id,
        summary=body.summary,
        operations=[
            EditOperationInput(
                op_type=op.op_type,
                feature_id=op.feature_id,
                geometry=op.geometry,
                properties=op.properties,
            )
            for op in body.operations
        ],
    )
    return _cs_wire(cs)


@router.get(f"{_BASE}/sources/{{source_id}}/changesets")
def list_changesets(
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    repo = SqlEditingRepository(session)
    items = repo.list_changesets(context=ctx, source_id=source_id, limit=limit)
    return {"items": [_cs_wire(c) for c in items]}


@router.get(f"{_BASE}/changesets/{{changeset_id}}")
def get_changeset(
    organization_id: UUID,
    project_id: UUID,
    changeset_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    repo = SqlEditingRepository(session)
    return _cs_wire(repo.get_changeset(context=ctx, changeset_id=changeset_id))


@router.post(f"{_BASE}/changesets/{{changeset_id}}/revert", status_code=201)
def revert_changeset(
    organization_id: UUID,
    project_id: UUID,
    changeset_id: UUID,
    body: RevertChangesetRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    repo = SqlEditingRepository(session)
    return _cs_wire(
        repo.revert_changeset(
            context=ctx,
            changeset_id=changeset_id,
            operation_id=body.operation_id,
            summary=body.summary,
        )
    )


@router.post(f"{_BASE}/editing/snap")
def compute_snap(
    organization_id: UUID,
    project_id: UUID,
    body: SnapRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
) -> dict[str, Any]:
    _ = context_for(auth, organization_id=organization_id, project_id=project_id)
    return snap_point_to_candidates(
        target=body.target,
        vertices=body.vertices,
        segments=body.segments,
        tolerance=body.tolerance,
    )
