"""R011 RLS-enforced repository for team activity feed, change reviews, comments & conflicts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import (
    ORGANIZATION_ROLE_PERMISSIONS,
    RESOURCE_ROLE_PERMISSIONS,
)
from openvietgis_api.domains.collaboration.activity_cursor import (
    ActivityCursor,
    cursor_scope,
    decode_cursor,
    encode_cursor,
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
    PlatformDomainError,
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


# Keep both streams anchored to immutable editing history and the current
# scoped source. Do not mirror a changeset into collaboration.activities:
# projection avoids duplicate events on replay and covers legacy edits.
_EDIT_ACTIVITY = """
    SELECT cs.id, cs.organization_id, cs.project_id,
        cs.actor_type, cs.actor_id, cs.actor_display_snapshot AS actor_display,
        CASE WHEN cs.status='reverted' THEN 'changeset.reverted'
             ELSE 'changeset.committed' END AS event_kind,
        'changeset' AS resource_type, cs.id AS resource_id,
        cs.resulting_content_revision AS revision_ref, cs.summary,
        jsonb_build_object('source_id', cs.source_id,
            'changeset_id', cs.id, 'base_content_revision', cs.base_content_revision,
            'operation_count', cs.operation_count,
            'reverted_from_changeset_id', cs.reverted_from_changeset_id) AS metadata,
        cs.created_at, 1 AS stream
    FROM editing.changesets cs
    JOIN spatial.data_sources src ON src.organization_id=cs.organization_id
        AND src.project_id=cs.project_id AND src.id=cs.source_id
    WHERE cs.organization_id=:org AND cs.project_id=:proj
        AND cs.status IN ('committed','reverted') AND cs.created_at<=:cutoff
"""
_REVIEW_ACTIVITY = """
    SELECT a.*, 0 AS stream
    FROM collaboration.activities a
    JOIN collaboration.change_reviews r ON r.organization_id=a.organization_id
        AND r.project_id=a.project_id AND r.id=a.resource_id
        AND r.content_revision=a.revision_ref
    JOIN editing.changesets cs ON cs.organization_id=r.organization_id
        AND cs.project_id=r.project_id AND cs.id=r.changeset_id
        AND cs.source_id=r.source_id AND cs.resulting_content_revision=r.content_revision
    JOIN spatial.data_sources src ON src.organization_id=cs.organization_id
        AND src.project_id=cs.project_id AND src.id=cs.source_id
    WHERE a.organization_id=:org AND a.project_id=:proj
        AND a.resource_type='change_review'
        AND a.event_kind IN ('review.requested','review.commented',
                             'review.approved','review.changes_requested')
        AND a.created_at<=:cutoff
"""


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
        operation_id: UUID | None = None,
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
        # Reuse the immutable comment ID as a scoped idempotency receipt.
        # Compatibility: requests without an operation ID still create a new
        # comment. Scoped deterministic IDs cannot collide across actors,
        # reviews or tenants for the same client-generated operation UUID.
        comment_id = (
            uuid4()
            if operation_id is None
            else uuid5(
                NAMESPACE_URL,
                "openvietgis:r011:comment:v1:"
                + ":".join(
                    str(value)
                    for value in (
                        context.organization_id,
                        context.project_id,
                        context.actor.actor_type,
                        context.actor.actor_id,
                        review_id,
                        operation_id,
                    )
                ),
            )
        )
        if operation_id is not None:
            existing = (
                self._session.execute(
                    text("""
                    SELECT * FROM collaboration.review_comments
                    WHERE organization_id=:org AND project_id=:proj AND id=:id
                """),
                    {"org": context.organization_id, "proj": context.project_id, "id": comment_id},
                )
                .mappings()
                .first()
            )
            if existing is not None:
                if (
                    existing["author_actor_id"] != context.actor.actor_id
                    or existing["review_id"] != review_id
                    or existing["body"] != clean_body
                    or existing["feature_id"] != feature_id
                    or existing["changeset_id"] != rev["changeset_id"]
                    or existing["content_revision"] != rev["content_revision"]
                ):
                    raise PlatformConflictError(
                        "comment operation_id already used for different intent",
                        code="COMMENT_OPERATION_CONFLICT",
                    )
                return _comment_from_row(existing)
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
                    "id": comment_id,
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
            metadata={"feature_id": feature_id, "comment_id": str(comment_id)},
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

    def _activity_rows(self, sql: str, params: dict[str, Any]) -> list[RowMapping]:
        try:
            self._session.execute(text("SELECT set_config('statement_timeout','2000ms',true)"))
            return list(self._session.execute(text(sql), params).mappings().all())
        except SQLAlchemyError:
            self._session.rollback()
            raise PlatformDomainError(
                "activity read unavailable; refresh or retry safely",
                code="ACTIVITY_READ_UNAVAILABLE",
                status_code=503,
            ) from None

    def list_activities(
        self, *, context: AuthorizationContext, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[ActivityRecord], datetime, str | None]:
        # A shared project row lock waits for earlier edit/review commits;
        # all supported writers take an exclusive project lock before creating
        # their event timestamps. The first-page cutoff is after this lock.
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        now = datetime.now(UTC)
        scope = cursor_scope(context)
        position = decode_cursor(cursor, scope, now) if cursor is not None else None
        cutoff = position.cutoff if position else now
        if type(limit) is not int or not 1 <= limit <= 200:
            raise PlatformValidationError("activity limit must be 1..200")
        params: dict[str, Any] = {
            "org": context.organization_id,
            "proj": context.project_id,
            "cutoff": cutoff,
            "lookahead": limit + 1,
        }
        edit_sql, review_sql = _EDIT_ACTIVITY, _REVIEW_ACTIVITY
        if position:
            params.update(
                {
                    "after_at": position.created_at,
                    "after_id": position.id,
                    "after_stream": position.stream,
                }
            )
            # Reject a stale/forged boundary if it is not currently visible.
            # The token has no authority independent of actual scoped history.
            boundary_sql = (
                edit_sql + " AND cs.id=:after_id AND cs.created_at=:after_at"
                if position.stream == 1
                else review_sql + " AND a.id=:after_id AND a.created_at=:after_at"
            )
            if not self._activity_rows(
                "SELECT 1 FROM (" + boundary_sql + ") AS boundary LIMIT 1", params
            ):
                raise PlatformValidationError(
                    "activity continuation unavailable; refresh the activity list",
                    code="INVALID_ACTIVITY_CURSOR",
                )
            edit_sql += " AND (cs.created_at,1,cs.id)<(:after_at,:after_stream,:after_id)"
            review_sql += " AND (a.created_at,0,a.id)<(:after_at,:after_stream,:after_id)"
        # Each branch returns only a bounded lookahead; the global merge is
        # at most 2*(limit+1) rows. No aggregate counts or moving offsets.
        order = " ORDER BY created_at DESC, stream DESC, id DESC LIMIT :lookahead"
        query = "(" + edit_sql + order + ") UNION ALL (" + review_sql + order + ")" + order
        rows = self._activity_rows(query, params)
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = page[-1]
            next_cursor = encode_cursor(
                ActivityCursor(cutoff, last["created_at"], last["stream"], last["id"]), scope
            )
        return [_act_from_row(r) for r in page], cutoff, next_cursor

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
