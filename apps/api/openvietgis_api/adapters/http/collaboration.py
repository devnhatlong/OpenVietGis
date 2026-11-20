"""R011 Team Collaboration HTTP adapter."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.collaboration_repository import (
    SqlCollaborationRepository,
)
from openvietgis_api.domains.collaboration.domain import (
    ActivityRecord,
    ChangeReviewRecord,
    ReviewCommentRecord,
    ReviewStatus,
)

router = APIRouter(tags=["collaboration"])
_BASE = "/organizations/{organization_id}/projects/{project_id}"


def _act_wire(a: ActivityRecord) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "actor_type": a.actor_type,
        "actor_id": str(a.actor_id),
        "actor_display": a.actor_display,
        "event_kind": a.event_kind,
        "resource_type": a.resource_type,
        "resource_id": str(a.resource_id),
        "revision_ref": a.revision_ref,
        "summary": a.summary,
        "metadata": a.metadata,
        "created_at": a.created_at.isoformat(),
    }


def _rev_wire(r: ChangeReviewRecord) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "source_id": str(r.source_id),
        "changeset_id": str(r.changeset_id),
        "content_revision": r.content_revision,
        "requested_by_actor_id": str(r.requested_by_actor_id),
        "assignee_user_id": str(r.assignee_user_id),
        "status": r.status.value,
        "decision_note": r.decision_note,
        "decided_by_actor_id": str(r.decided_by_actor_id) if r.decided_by_actor_id else None,
        "created_at": r.created_at.isoformat(),
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
    }


def _cmt_wire(c: ReviewCommentRecord) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "review_id": str(c.review_id),
        "changeset_id": str(c.changeset_id),
        "content_revision": c.content_revision,
        "feature_id": c.feature_id,
        "body": c.body,
        "author_actor_id": str(c.author_actor_id),
        "author_display": c.author_display,
        "created_at": c.created_at.isoformat(),
    }


class CreateReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changeset_id: UUID
    assignee_user_id: UUID


class DecideReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ReviewStatus
    decision_note: str = ""


class AddCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str
    feature_id: str | None = None


class ConflictRebaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_content_revision: str
    draft_operations: list[dict[str, Any]]


@router.get(f"{_BASE}/collaboration/activities")
def list_activities(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    items = SqlCollaborationRepository(session).list_activities(context=ctx, limit=limit)
    return {"items": [_act_wire(a) for a in items]}


@router.post(f"{_BASE}/collaboration/reviews", status_code=201)
def create_review(
    organization_id: UUID,
    project_id: UUID,
    body: CreateReviewRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    rec = SqlCollaborationRepository(session).create_review(
        context=ctx,
        changeset_id=body.changeset_id,
        assignee_user_id=body.assignee_user_id,
    )
    return _rev_wire(rec)


@router.get(f"{_BASE}/collaboration/reviews")
def list_reviews(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return {
        "items": [
            _rev_wire(r) for r in SqlCollaborationRepository(session).list_reviews(context=ctx)
        ]
    }


@router.post(f"{_BASE}/collaboration/reviews/{{review_id}}/decide")
def decide_review(
    organization_id: UUID,
    project_id: UUID,
    review_id: UUID,
    body: DecideReviewRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _rev_wire(
        SqlCollaborationRepository(session).decide_review(
            context=ctx,
            review_id=review_id,
            status=body.status,
            decision_note=body.decision_note,
        )
    )


@router.post(f"{_BASE}/collaboration/reviews/{{review_id}}/comments", status_code=201)
def add_comment(
    organization_id: UUID,
    project_id: UUID,
    review_id: UUID,
    body: AddCommentRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _cmt_wire(
        SqlCollaborationRepository(session).add_comment(
            context=ctx,
            review_id=review_id,
            body=body.body,
            feature_id=body.feature_id,
        )
    )


@router.get(f"{_BASE}/collaboration/reviews/{{review_id}}/comments")
def list_comments(
    organization_id: UUID,
    project_id: UUID,
    review_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    items = SqlCollaborationRepository(session).list_comments(context=ctx, review_id=review_id)
    return {"items": [_cmt_wire(c) for c in items]}


@router.post(f"{_BASE}/sources/{{source_id}}/conflict-rebase")
def inspect_conflict_rebase(
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    body: ConflictRebaseRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return SqlCollaborationRepository(session).inspect_conflict_rebase(
        context=ctx,
        source_id=source_id,
        base_content_revision=body.base_content_revision,
        draft_operations=body.draft_operations,
    )
