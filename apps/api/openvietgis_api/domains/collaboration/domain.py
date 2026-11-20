"""R011 Team Collaboration domain (reviews, comments, activity, conflict rebase helper)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


@dataclass(frozen=True, slots=True)
class ActivityRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    actor_type: str
    actor_id: UUID
    actor_display: str
    event_kind: str
    resource_type: str
    resource_id: UUID
    revision_ref: str | None
    summary: str
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChangeReviewRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    source_id: UUID
    changeset_id: UUID
    content_revision: str
    requested_by_actor_id: UUID
    assignee_user_id: UUID
    status: ReviewStatus
    decision_note: str
    decided_by_actor_id: UUID | None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReviewCommentRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    review_id: UUID
    changeset_id: UUID
    content_revision: str
    feature_id: str | None
    body: str
    author_actor_id: UUID
    author_display: str
    created_at: datetime


def analyze_draft_conflicts(
    *,
    draft_operations: Sequence[Mapping[str, Any]],
    intervening_changed_feature_ids: set[str],
    current_content_revision: str,
) -> dict[str, Any]:
    """Explicit refresh-and-reapply conflict report (never last-write-wins)."""
    conflicts: list[dict[str, Any]] = []
    reapplicable: list[dict[str, Any]] = []
    for op in draft_operations:
        fid = str(op.get("feature_id", ""))
        if fid in intervening_changed_feature_ids:
            conflicts.append({
                "feature_id": fid,
                "op_type": op.get("op_type"),
                "reason": "feature modified in an intervening committed changeset",
            })
        else:
            reapplicable.append(dict(op))
    return {
        "current_content_revision": current_content_revision,
        "has_conflicts": len(conflicts) > 0,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "reapplicable_operations": reapplicable,
        "policy": "explicit_refresh_and_reapply",
    }
