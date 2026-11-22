"""R011 Team Collaboration domain (reviews, comments, activity, conflict rebase helper)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from openvietgis_api.domains.editing.domain import EditOpType, validate_feature_id
from openvietgis_api.domains.platform_errors import PlatformValidationError


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


def validate_rebase_draft(
    draft_operations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not 1 <= len(draft_operations) <= 2000:
        raise PlatformValidationError(
            "rebase requires 1..2000 draft operations",
            code="INVALID_REBASE_DRAFT",
        )
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for operation in draft_operations:
        raw_id = operation.get("feature_id")
        kind = operation.get("op_type")
        if not isinstance(raw_id, str) or kind not in tuple(EditOpType):
            raise PlatformValidationError("invalid rebase operation", code="INVALID_REBASE_DRAFT")
        feature_id = validate_feature_id(raw_id)
        if feature_id in seen:
            raise PlatformValidationError("duplicate draft feature", code="DUPLICATE_FEATURE_OP")
        seen.add(feature_id)
        validated.append({**operation, "feature_id": feature_id})
    return validated


def analyze_draft_conflicts(
    *,
    draft_operations: Sequence[Mapping[str, Any]],
    intervening_changed_feature_ids: set[str],
    current_content_revision: str,
    existing_feature_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Explicit refresh-and-reapply conflict report (never last-write-wins)."""
    conflicts: list[dict[str, Any]] = []
    reapplicable: list[dict[str, Any]] = []
    for op in draft_operations:
        fid = str(op.get("feature_id", ""))
        reason = None
        if fid in intervening_changed_feature_ids:
            reason = "feature modified in an intervening committed changeset"
        elif existing_feature_ids is not None:
            if op.get("op_type") == EditOpType.CREATE and fid in existing_feature_ids:
                reason = "feature already exists in current revision"
            elif op.get("op_type") != EditOpType.CREATE and fid not in existing_feature_ids:
                reason = "feature absent from current revision"
        if reason is not None:
            conflicts.append(
                {
                    "feature_id": fid,
                    "op_type": op.get("op_type"),
                    "reason": reason,
                }
            )
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
