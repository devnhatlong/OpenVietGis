"""R011 RLS-enforced repository for team activity feed, change reviews, comments & conflicts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import (
    ORGANIZATION_ROLE_PERMISSIONS,
    RESOURCE_ROLE_PERMISSIONS,
)
from openvietgis_api.domains.collaboration.domain import (
    ActivityRecord,
    ChangeReviewRecord,
    ReviewCommentRecord,
    ReviewStatus,
    analyze_draft_conflicts,
    validate_rebase_draft,
)
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformForbiddenError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.domains.tenancy.domain import MembershipRole, ResourceRole


def _act_from_row(row: RowMapping) -> ActivityRecord:
    return ActivityRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        actor_type=str(row["actor_type"]),
        actor_id=row["actor_id"],
        actor_display=str(row["actor_display"]),
        event_kind=str(row["event_kind"]),
        resource_type=str(row["resource_type"]),
        resource_id=row["resource_id"],
        revision_ref=str(row["revision_ref"]) if row["revision_ref"] else None,
        summary=str(row["summary"]),
        metadata=dict(row["metadata"]),
        created_at=row["created_at"],
    )


def _review_from_row(row: RowMapping) -> ChangeReviewRecord:
    return ChangeReviewRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        source_id=row["source_id"],
        changeset_id=row["changeset_id"],
        content_revision=str(row["content_revision"]),
        requested_by_actor_id=row["requested_by_actor_id"],
        assignee_user_id=row["assignee_user_id"],
        status=ReviewStatus(str(row["status"])),
        decision_note=str(row["decision_note"]),
        decided_by_actor_id=row["decided_by_actor_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        decided_at=row["decided_at"],
    )


def _comment_from_row(row: RowMapping) -> ReviewCommentRecord:
    return ReviewCommentRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        review_id=row["review_id"],
        changeset_id=row["changeset_id"],
        content_revision=str(row["content_revision"]),
        feature_id=str(row["feature_id"]) if row["feature_id"] else None,
        body=str(row["body"]),
        author_actor_id=row["author_actor_id"],
        author_display=str(row["author_display"]),
        created_at=row["created_at"],
    )


class SqlCollaborationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _record_activity(
        self,
        *,
        context: AuthorizationContext,
        event_kind: str,
        resource_type: str,
        resource_id: UUID,
        revision_ref: str | None,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        self._session.execute(
            text("""
                INSERT INTO collaboration.activities (
                    id, organization_id, project_id, actor_type, actor_id, actor_display,
                    event_kind, resource_type, resource_id, revision_ref, summary,
                    metadata, created_at
                ) VALUES (
                    :id, :org, :proj, :atype, :aid, :adisp,
                    :kind, :rtype, :rid, :rref, :summary,
                    CAST(:meta AS jsonb), :now
                )
            """),
            {
                "id": uuid4(),
                "org": context.organization_id,
                "proj": context.project_id,
                "atype": str(context.actor.actor_type),
                "aid": context.actor.actor_id,
                "adisp": (context.actor.display_name or str(context.actor.actor_id))[:200],
                "kind": event_kind,
                "rtype": resource_type,
                "rid": resource_id,
                "rref": revision_ref,
                "summary": summary[:500],
                "meta": json.dumps(metadata or {}),
                "now": datetime.now(UTC),
            },
        )

    def create_review(
        self,
        *,
        context: AuthorizationContext,
        changeset_id: UUID,
        assignee_user_id: UUID,
    ) -> ChangeReviewRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None

        cs = (
            self._session.execute(
                text("""
                SELECT id, source_id, resulting_content_revision
                FROM editing.changesets
                WHERE organization_id = :org AND project_id = :proj AND id = :cid
            """),
                {"org": context.organization_id, "proj": context.project_id, "cid": changeset_id},
            )
            .mappings()
            .first()
        )
        if cs is None:
            raise PlatformNotFoundError("changeset not found")

        # Resolve the assignee's current human membership and applicable
        # project grants under the verified tenant scope; never impersonate them.
        roles = (
            self._session.execute(
                text("""
                SELECT m.role AS membership_role, g.role AS grant_role
                FROM org.organization_memberships m
                JOIN identity.users u ON u.id = m.user_id AND u.status = 'active'
                JOIN workspace.projects p ON p.organization_id = m.organization_id
                    AND p.id = :proj AND p.status = 'active'
                LEFT JOIN org.resource_grants g ON g.organization_id = m.organization_id
                    AND g.membership_id = m.id AND g.subject_kind = 'membership'
                    AND g.revoked_at IS NULL
                    AND (g.scope_kind = 'organization'
                        OR (g.scope_kind = 'workspace' AND g.workspace_id = p.workspace_id)
                        OR (g.scope_kind = 'project' AND g.project_id = p.id))
                WHERE m.organization_id = :org AND m.user_id = :uid AND m.status = 'active'
            """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "uid": assignee_user_id,
                },
            )
            .mappings()
            .all()
        )
        eligible = any(
            Permission.PROJECT_EDIT
            in ORGANIZATION_ROLE_PERMISSIONS[MembershipRole(r["membership_role"])]
            or (
                r["grant_role"] is not None
                and Permission.PROJECT_EDIT
                in RESOURCE_ROLE_PERMISSIONS[ResourceRole(r["grant_role"])]
            )
            for r in roles
        )
        if not eligible:
            raise PlatformValidationError(
                "assignee must have current project review eligibility",
                code="INVALID_ASSIGNEE",
            )

        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO collaboration.change_reviews (
                    id, organization_id, project_id, source_id, changeset_id,
                    content_revision, requested_by_actor_id, assignee_user_id,
                    status, decision_note, created_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :src, :cid,
                    :crev, :req, :assignee,
                    'pending', '', :now, :now
                )
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "src": cs["source_id"],
                    "cid": changeset_id,
                    "crev": str(cs["resulting_content_revision"]),
                    "req": context.actor.actor_id,
                    "assignee": assignee_user_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._record_activity(
            context=context,
            event_kind="review.requested",
            resource_type="change_review",
            resource_id=row["id"],
            revision_ref=str(cs["resulting_content_revision"]),
            summary=f"Requested post-commit review on changeset {changeset_id}",
            metadata={"changeset_id": str(changeset_id), "assignee_user_id": str(assignee_user_id)},
        )
        self._session.commit()
        return _review_from_row(row)

    def decide_review(
        self,
        *,
        context: AuthorizationContext,
        review_id: UUID,
        status: ReviewStatus,
        decision_note: str = "",
    ) -> ChangeReviewRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        if status == ReviewStatus.PENDING:
            raise PlatformValidationError(
                "decision status must be 'approved' or 'changes_requested'"
            )
        existing = (
            self._session.execute(
                text("""
                SELECT assignee_user_id, status FROM collaboration.change_reviews
                WHERE organization_id = :org AND project_id = :proj AND id = :rid
                FOR UPDATE
            """),
                {"org": context.organization_id, "proj": context.project_id, "rid": review_id},
            )
            .mappings()
            .first()
        )
        if existing is None:
            raise PlatformNotFoundError("change review not found")
        if (
            context.actor.actor_type != "human"
            or existing["assignee_user_id"] != context.actor.actor_id
        ):
            raise PlatformForbiddenError("only the assigned current reviewer may decide")
        if existing["status"] != ReviewStatus.PENDING.value:
            raise PlatformConflictError(
                "a completed review cannot be overwritten", code="REVIEW_ALREADY_DECIDED"
            )
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                UPDATE collaboration.change_reviews
                SET status = :st, decision_note = :note, decided_by_actor_id = :actor,
                    updated_at = :now, decided_at = :now
                WHERE organization_id = :org AND project_id = :proj AND id = :rid
                RETURNING *
            """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "rid": review_id,
                    "st": status.value,
                    "note": decision_note.strip()[:500],
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("change review not found")
        self._record_activity(
            context=context,
            event_kind=f"review.{status.value}",
            resource_type="change_review",
            resource_id=review_id,
            revision_ref=str(row["content_revision"]),
            summary=f"Review marked {status.value}",
            metadata={"decision_note": decision_note.strip()[:200]},
        )
        self._session.commit()
        return _review_from_row(row)

    def add_comment(
        self,
        *,
        context: AuthorizationContext,
        review_id: UUID,
        body: str,
        feature_id: str | None = None,
    ) -> ReviewCommentRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        clean_body = body.strip()
        if not clean_body or len(clean_body) > 2000:
            raise PlatformValidationError("comment body must be 1..2000 characters")
        rev = (
            self._session.execute(
                text("""
                SELECT id, changeset_id, content_revision FROM collaboration.change_reviews
                WHERE organization_id = :org AND project_id = :proj AND id = :rid
            """),
                {"org": context.organization_id, "proj": context.project_id, "rid": review_id},
            )
            .mappings()
            .first()
        )
        if rev is None:
            raise PlatformNotFoundError("change review not found")
        if feature_id is not None:
            # A feature comment references immutable evidence in the exact
            # reviewed changeset, not an arbitrary current or foreign feature.
            anchor = self._session.execute(
                text("""
                    SELECT 1 FROM editing.changeset_operations
                    WHERE organization_id = :org AND project_id = :proj
                      AND changeset_id = :cid AND feature_id = :fid
                """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "cid": rev["changeset_id"],
                    "fid": feature_id,
                },
            ).first()
            if anchor is None:
                raise PlatformValidationError(
                    "feature comment must reference an operation in the reviewed changeset",
                    code="INVALID_REVIEW_ANCHOR",
                )
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO collaboration.review_comments (
                    id, organization_id, project_id, review_id, changeset_id,
                    content_revision, feature_id, body, author_actor_id,
                    author_display, created_at
                ) VALUES (
                    :id, :org, :proj, :rid, :cid,
                    :crev, :fid, :body, :actor, :adisp, :now
                )
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "rid": review_id,
                    "cid": rev["changeset_id"],
                    "crev": str(rev["content_revision"]),
                    "fid": feature_id,
                    "body": clean_body,
                    "actor": context.actor.actor_id,
                    "adisp": (context.actor.display_name or str(context.actor.actor_id))[:200],
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._record_activity(
            context=context,
            event_kind="review.commented",
            resource_type="change_review",
            resource_id=review_id,
            revision_ref=str(rev["content_revision"]),
            summary=f"Commented on review {review_id}",
            metadata={"feature_id": feature_id},
        )
        self._session.commit()
        return _comment_from_row(row)

    def list_reviews(self, *, context: AuthorizationContext) -> list[ChangeReviewRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM collaboration.change_reviews
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY created_at DESC LIMIT 100
            """),
                {"org": context.organization_id, "proj": context.project_id},
            )
            .mappings()
            .all()
        )
        return [_review_from_row(r) for r in rows]

    def list_comments(
        self, *, context: AuthorizationContext, review_id: UUID
    ) -> list[ReviewCommentRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM collaboration.review_comments
                WHERE organization_id = :org AND project_id = :proj AND review_id = :rid
                ORDER BY created_at ASC
            """),
                {"org": context.organization_id, "proj": context.project_id, "rid": review_id},
            )
            .mappings()
            .all()
        )
        return [_comment_from_row(r) for r in rows]

    def list_activities(
        self, *, context: AuthorizationContext, limit: int = 50
    ) -> list[ActivityRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM collaboration.activities
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY created_at DESC LIMIT :lim
            """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "lim": max(1, min(200, limit)),
                },
            )
            .mappings()
            .all()
        )
        return [_act_from_row(r) for r in rows]

    def inspect_conflict_rebase(
        self,
        *,
        context: AuthorizationContext,
        source_id: UUID,
        base_content_revision: str,
        draft_operations: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        # The mutation scope binds the current project authorization and serialization
        # lock. The source row remains pinned for this read-only advisory report.
        src = (
            self._session.execute(
                text("""
                SELECT content_revision, lifecycle, validation_state, kind
                FROM spatial.data_sources
                WHERE organization_id = :org AND project_id = :proj AND id = :src
                FOR SHARE
            """),
                {"org": context.organization_id, "proj": context.project_id, "src": source_id},
            )
            .mappings()
            .first()
        )
        if src is None:
            raise PlatformNotFoundError("data source not found")
        if (
            src["lifecycle"] != "active"
            or src["validation_state"] != "ready"
            or src["kind"] == "reference_fixture"
        ):
            raise PlatformValidationError("source is not editable", code="SOURCE_NOT_READY")

        validated = validate_rebase_draft(draft_operations)
        current = str(src["content_revision"])
        params = {
            "org": context.organization_id,
            "proj": context.project_id,
            "src": source_id,
        }
        # Revision hashes are opaque: != base does NOT mean "after base".
        # Walk backward from the pinned current revision through the immutable
        # changeset chain, until the caller's exact base is reached. A missing
        # link (e.g. another publication path), invalid base or oversized history
        # cannot authorize reapplication and must require a fresh draft.
        chain_ids: list[UUID] = []
        cursor = current
        if cursor != base_content_revision:
            history = (
                self._session.execute(
                    text("""
                    SELECT id, base_content_revision, resulting_content_revision
                    FROM editing.changesets
                    WHERE organization_id = :org AND project_id = :proj AND source_id = :src
                    ORDER BY resulting_catalog_revision DESC
                    LIMIT 2001
                """),
                    params,
                )
                .mappings()
                .all()
            )
            for row in history:
                if cursor == base_content_revision:
                    break
                if len(chain_ids) >= 2000 or str(row["resulting_content_revision"]) != cursor:
                    break
                chain_ids.append(row["id"])
                cursor = str(row["base_content_revision"])
            if cursor != base_content_revision:
                raise PlatformConflictError(
                    "cannot prove a continuous edit history from the requested base; refresh",
                    code="REBASE_HISTORY_UNAVAILABLE",
                    details={"current_content_revision": current, "draft_preserved": True},
                )
        feature_ids = [str(op["feature_id"]) for op in validated]
        intervening = (
            self._session.execute(
                text("""
                SELECT DISTINCT feature_id FROM editing.changeset_operations
                WHERE organization_id = :org AND project_id = :proj
                  AND changeset_id = ANY(CAST(:ids AS uuid[]))
                  AND feature_id = ANY(CAST(:feature_ids AS varchar[]))
            """),
                {**params, "ids": chain_ids, "feature_ids": feature_ids},
            )
            .scalars()
            .all()
            if chain_ids
            else []
        )
        existing = (
            self._session.execute(
                text("""
                SELECT feature_id FROM spatial.reference_features
                WHERE organization_id = :org AND project_id = :proj AND source_id = :src
                  AND feature_id = ANY(CAST(:feature_ids AS varchar[]))
            """),
                {**params, "feature_ids": feature_ids},
            )
            .scalars()
            .all()
        )
        return analyze_draft_conflicts(
            draft_operations=validated,
            intervening_changed_feature_ids={str(x) for x in intervening},
            current_content_revision=current,
            existing_feature_ids={str(x) for x in existing},
        )
