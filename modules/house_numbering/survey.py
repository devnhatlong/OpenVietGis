"""Offline-safe field survey, assignment and progress services."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.module_sdk import put_module_artifact, read_module_artifact
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.house_numbering.domain import SurveyResult, summarize_progress
from modules.house_numbering.persistence import HouseNumberingRepository

_ALLOWED_CONDITIONS = {"house", "vacant", "removed", "other"}
_ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png"}


class HouseNumberingSurveyService:
    def __init__(self, session: Session, context: AuthorizationContext) -> None:
        self.session = session
        self.context = context
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        self.org = context.organization_id
        self.project = context.project_id
        self.actor = context.actor.actor_id
        self.repo = HouseNumberingRepository(session, context)

    def upload_photo(self, *, content_type: str, data: bytes) -> dict[str, Any]:
        self.repo.prepare("edit")
        ext = _ALLOWED_IMAGE_TYPES.get(content_type)
        if ext is None:
            raise PlatformValidationError(
                "survey photo must be JPEG or PNG", code="PHOTO_TYPE"
            )
        if not data or len(data) > 15 * 1024 * 1024:
            raise PlatformValidationError(
                "survey photo size is invalid", code="PHOTO_SIZE"
            )
        artifact = put_module_artifact(
            self.context,
            namespace="house-numbering-survey-photos",
            filename=f"survey-photo.{ext}",
            content_type=content_type,
            data=data,
        )
        self.repo.audit(
            "house_numbering.survey.photo_upload",
            "house_numbering_photo",
            artifact.id,
            {"sha256": artifact.sha256, "byte_size": artifact.byte_size},
        )
        self.session.commit()
        return {
            "id": str(artifact.id),
            "content_type": artifact.content_type,
            "byte_size": artifact.byte_size,
            "sha256": artifact.sha256,
        }

    def create_assignment(
        self,
        *,
        scope_kind: str,
        scope_id: UUID,
        assignee_actor_id: UUID,
        starts_on: date,
        ends_on: date | None,
        target_count: int | None,
    ) -> dict[str, Any]:
        self.repo.prepare("manage")
        if scope_kind not in {"area", "route"}:
            raise PlatformValidationError("assignment scope must be area or route")
        if ends_on is not None and ends_on < starts_on:
            raise PlatformValidationError("assignment end date precedes start date")
        if target_count is not None and target_count < 0:
            raise PlatformValidationError("target_count must be nonnegative")
        now = datetime.now(UTC)
        row = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.assignments (
                    id,organization_id,project_id,scope_kind,scope_id,assignee_actor_id,
                    target_count,starts_on,ends_on,revision,created_by_actor_id,created_at,updated_at
                ) VALUES (
                    :id,:org,:project,:kind,:scope,:assignee,:target,:starts,:ends,1,:actor,:now,:now
                ) RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": self.org,
                    "project": self.project,
                    "kind": scope_kind,
                    "scope": scope_id,
                    "assignee": assignee_actor_id,
                    "target": target_count,
                    "starts": starts_on,
                    "ends": ends_on,
                    "actor": self.actor,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self.repo.audit(
            "house_numbering.assignment.create",
            "house_numbering_assignment",
            row["id"],
            {"assignee_actor_id": str(assignee_actor_id), "scope_kind": scope_kind},
        )
        self.session.commit()
        return dict(row)

    def reassign(
        self,
        assignment_id: UUID,
        *,
        expected_revision: int,
        assignee_actor_id: UUID,
    ) -> dict[str, Any]:
        self.repo.prepare("manage")
        row = (
            self.session.execute(
                text("""
                UPDATE house_numbering.assignments
                SET assignee_actor_id=:assignee,revision=revision+1,updated_at=:now
                WHERE organization_id=:org AND project_id=:project AND id=:id
                  AND revision=:revision
                RETURNING *
            """),
                {
                    "assignee": assignee_actor_id,
                    "now": datetime.now(UTC),
                    "org": self.org,
                    "project": self.project,
                    "id": assignment_id,
                    "revision": expected_revision,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformConflictError(
                "assignment is stale or missing", code="STALE_ASSIGNMENT"
            )
        self.repo.audit(
            "house_numbering.assignment.reassign",
            "house_numbering_assignment",
            assignment_id,
            {"assignee_actor_id": str(assignee_actor_id)},
        )
        self.session.commit()
        return dict(row)

    def list_assignments(self) -> list[dict[str, Any]]:
        self.repo.prepare("read")
        rows = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.assignments
                WHERE organization_id=:org AND project_id=:project
                ORDER BY starts_on DESC,created_at DESC,id DESC
            """),
                {"org": self.org, "project": self.project},
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def _validate_photos(self, photo_ids: list[UUID]) -> None:
        if len(photo_ids) > 12 or len(set(photo_ids)) != len(photo_ids):
            raise PlatformValidationError(
                "invalid survey photo list", code="PHOTO_LIST"
            )
        for artifact_id in photo_ids:
            try:
                read_module_artifact(
                    self.context,
                    namespace="house-numbering-survey-photos",
                    artifact_id=artifact_id,
                )
            except (FileNotFoundError, RuntimeError) as exc:
                raise PlatformValidationError(
                    f"survey photo {artifact_id} is unavailable", code="PHOTO_MISSING"
                ) from exc

    def sync(self, operations: list[dict[str, Any]]) -> dict[str, Any]:
        self.repo.prepare("edit")
        if not operations or len(operations) > 500:
            raise PlatformValidationError(
                "offline sync batch must contain 1..500 operations"
            )
        applied: list[str] = []
        replayed: list[str] = []
        conflicts: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for item in operations:
            try:
                client_uuid = UUID(str(item["client_uuid"]))
                building_id = (
                    UUID(str(item["building_id"])) if item.get("building_id") else None
                )
            except (KeyError, ValueError) as exc:
                raise PlatformValidationError(
                    "invalid offline survey identifiers"
                ) from exc
            condition = str(item.get("condition", ""))
            if condition not in _ALLOWED_CONDITIONS:
                raise PlatformValidationError("invalid survey condition")
            x, y, crs = item.get("x"), item.get("y"), item.get("crs_code")
            if any(value is not None for value in (x, y, crs)) and not all(
                value is not None for value in (x, y, crs)
            ):
                raise PlatformValidationError(
                    "survey coordinate requires x, y and crs_code"
                )
            photo_ids = [UUID(str(v)) for v in item.get("photo_artifact_ids", [])]
            self._validate_photos(photo_ids)

            existing = (
                self.session.execute(
                    text("""
                    SELECT * FROM house_numbering.surveys
                    WHERE organization_id=:org AND project_id=:project AND client_uuid=:client
                """),
                    {"org": self.org, "project": self.project, "client": client_uuid},
                )
                .mappings()
                .first()
            )
            canonical_photos = [str(v) for v in photo_ids]
            if existing is not None:
                same = (
                    existing["building_id"] == building_id
                    and existing["condition"] == condition
                    and (
                        existing["point_x"] == x
                        or x is None
                        and existing["point_x"] is None
                    )
                    and (
                        existing["point_y"] == y
                        or y is None
                        and existing["point_y"] is None
                    )
                    and existing["crs_code"] == crs
                    and [str(v) for v in existing["photo_artifact_ids"]]
                    == canonical_photos
                )
                if same:
                    replayed.append(str(existing["id"]))
                    continue
                conflicts.append(
                    {
                        "client_uuid": str(client_uuid),
                        "code": "CLIENT_UUID_PAYLOAD_CONFLICT",
                    }
                )
                continue

            if building_id is not None:
                self.repo.get_building(building_id)
                accepted = (
                    self.session.execute(
                        text("""
                        SELECT id,client_uuid FROM house_numbering.surveys
                        WHERE organization_id=:org AND project_id=:project
                          AND building_id=:building AND state='accepted' LIMIT 1
                    """),
                        {
                            "org": self.org,
                            "project": self.project,
                            "building": building_id,
                        },
                    )
                    .mappings()
                    .first()
                )
                if accepted is not None:
                    conflicts.append(
                        {
                            "client_uuid": str(client_uuid),
                            "code": "BUILDING_ALREADY_ACCEPTED",
                            "existing_survey_id": str(accepted["id"]),
                        }
                    )
                    continue
            survey_id = uuid4()
            self.session.execute(
                text("""
                    INSERT INTO house_numbering.surveys (
                        id,organization_id,project_id,client_uuid,building_id,point_x,point_y,
                        crs_code,photo_artifact_ids,condition,state,recorded_by_actor_id,
                        submitted_by_actor_id,revision,created_at,updated_at
                    ) VALUES (
                        :id,:org,:project,:client,:building,:x,:y,:crs,CAST(:photos AS jsonb),
                        :condition,'submitted',:actor,:actor,1,:now,:now
                    )
                """),
                {
                    "id": survey_id,
                    "org": self.org,
                    "project": self.project,
                    "client": client_uuid,
                    "building": building_id,
                    "x": x,
                    "y": y,
                    "crs": crs,
                    "photos": json.dumps(canonical_photos),
                    "condition": condition,
                    "actor": self.actor,
                    "now": now,
                },
            )
            applied.append(str(survey_id))
        self.repo.audit(
            "house_numbering.survey.sync",
            "house_numbering_survey_batch",
            uuid4(),
            {
                "applied": len(applied),
                "replayed": len(replayed),
                "conflicts": len(conflicts),
            },
        )
        self.session.commit()
        return {"applied": applied, "replayed": replayed, "conflicts": conflicts}

    def review(
        self,
        survey_id: UUID,
        *,
        expected_revision: int,
        decision: str,
    ) -> dict[str, Any]:
        self.repo.prepare("manage")
        if decision not in {"accepted", "rejected"}:
            raise PlatformValidationError(
                "survey decision must be accepted or rejected"
            )
        current = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.surveys
                WHERE organization_id=:org AND project_id=:project AND id=:id
                FOR UPDATE
            """),
                {"org": self.org, "project": self.project, "id": survey_id},
            )
            .mappings()
            .first()
        )
        if current is None:
            raise PlatformNotFoundError("survey not found")
        if (
            int(current["revision"]) != expected_revision
            or current["state"] != "submitted"
        ):
            raise PlatformConflictError(
                "survey is stale or not reviewable", code="STALE_SURVEY"
            )
        if decision == "accepted" and current["building_id"] is not None:
            other = self.session.execute(
                text("""
                    SELECT id FROM house_numbering.surveys
                    WHERE organization_id=:org AND project_id=:project AND building_id=:building
                      AND state='accepted' AND id<>:id LIMIT 1
                """),
                {
                    "org": self.org,
                    "project": self.project,
                    "building": current["building_id"],
                    "id": survey_id,
                },
            ).scalar_one_or_none()
            if other is not None:
                raise PlatformConflictError(
                    "another accepted survey exists for building",
                    code="SURVEY_REVIEW_CONFLICT",
                )
        row = (
            self.session.execute(
                text("""
                UPDATE house_numbering.surveys
                SET state=:state,revision=revision+1,updated_at=:now
                WHERE organization_id=:org AND project_id=:project AND id=:id
                RETURNING *
            """),
                {
                    "state": decision,
                    "now": datetime.now(UTC),
                    "org": self.org,
                    "project": self.project,
                    "id": survey_id,
                },
            )
            .mappings()
            .one()
        )
        self.repo.audit(
            "house_numbering.survey.review",
            "house_numbering_survey",
            survey_id,
            {"decision": decision},
        )
        self.session.commit()
        return dict(row)

    def list_surveys(self, *, state: str | None = None) -> list[dict[str, Any]]:
        self.repo.prepare("read")
        sql = """
            SELECT * FROM house_numbering.surveys
            WHERE organization_id=:org AND project_id=:project
        """
        params: dict[str, Any] = {"org": self.org, "project": self.project}
        if state:
            sql += " AND state=:state"
            params["state"] = state
        sql += " ORDER BY created_at DESC,id DESC"
        return [
            dict(row)
            for row in self.session.execute(text(sql), params).mappings().all()
        ]

    def report_rows(self) -> list[dict[str, Any]]:
        self.repo.prepare("read")
        rows = (
            self.session.execute(
                text("""
                SELECT b.id AS building_id,r.name AS route_name,n.number_text AS house_number,
                       s.condition,s.state,s.updated_at
                FROM house_numbering.buildings b
                LEFT JOIN house_numbering.routes r
                  ON r.organization_id=b.organization_id AND r.project_id=b.project_id AND r.id=b.route_id
                LEFT JOIN LATERAL (
                    SELECT number_text FROM house_numbering.address_numbers n
                    WHERE n.organization_id=b.organization_id AND n.project_id=b.project_id
                      AND n.building_id=b.id AND n.retired_at IS NULL
                    ORDER BY CASE n.kind WHEN 'approved' THEN 1 WHEN 'submitted' THEN 2 ELSE 3 END,
                             n.created_at DESC LIMIT 1
                ) n ON true
                LEFT JOIN LATERAL (
                    SELECT condition,state,updated_at FROM house_numbering.surveys s
                    WHERE s.organization_id=b.organization_id AND s.project_id=b.project_id
                      AND s.building_id=b.id
                    ORDER BY s.updated_at DESC,s.id DESC LIMIT 1
                ) s ON true
                WHERE b.organization_id=:org AND b.project_id=:project AND b.state='active'
                ORDER BY r.name,n.number_text,b.id
            """),
                {"org": self.org, "project": self.project},
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def progress(self) -> dict[str, Any]:
        self.repo.prepare("read")
        target = self.session.execute(
            text("""
                SELECT COALESCE(sum(target_count),0)
                FROM house_numbering.assignments
                WHERE organization_id=:org AND project_id=:project
                  AND starts_on<=CURRENT_DATE AND (ends_on IS NULL OR ends_on>=CURRENT_DATE)
            """),
            {"org": self.org, "project": self.project},
        ).scalar_one()
        rows = (
            self.session.execute(
                text("""
                SELECT DISTINCT ON (building_id) building_id,condition,state,updated_at
                FROM house_numbering.surveys
                WHERE organization_id=:org AND project_id=:project
                  AND building_id IS NOT NULL
                ORDER BY building_id,updated_at DESC,id DESC
            """),
                {"org": self.org, "project": self.project},
            )
            .mappings()
            .all()
        )
        surveys = [
            SurveyResult(
                str(row["building_id"]),
                "other" if row["condition"] == "removed" else str(row["condition"]),
                str(row["state"]),
            )
            for row in rows
        ]
        summary = summarize_progress(surveys, target=int(target) if target else None)
        summary["removed"] = sum(
            1
            for row in rows
            if row["state"] == "accepted" and row["condition"] == "removed"
        )
        summary["submitted_pending"] = sum(
            1 for row in rows if row["state"] == "submitted"
        )
        return summary
