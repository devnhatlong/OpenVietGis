"""Deterministic three-source reconciliation and manual case queue."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformNotFoundError,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.house_numbering.domain import (
    EvidenceCandidate,
    classify_reconciliation,
    match_certificate,
)
from modules.house_numbering.persistence import HouseNumberingRepository


class HouseNumberingReconciliation:
    def __init__(self, session: Session, context: AuthorizationContext) -> None:
        self.session = session
        self.context = context
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        self.org = context.organization_id
        self.project = context.project_id
        self.actor = context.actor.actor_id
        self.repo = HouseNumberingRepository(session, context)

    def _prepare(self, access: str = "read") -> None:
        self.repo.prepare(access)

    def evidence(self, *, building_id: UUID | None = None) -> list[dict[str, Any]]:
        self._prepare("read")
        sql = """
            SELECT * FROM house_numbering.evidence
            WHERE organization_id=:org AND project_id=:project
        """
        params: dict[str, Any] = {"org": self.org, "project": self.project}
        if building_id is not None:
            sql += " AND building_id=:building"
            params["building"] = building_id
        sql += " ORDER BY evidence_date DESC NULLS LAST,created_at DESC,id DESC"
        return [
            dict(row)
            for row in self.session.execute(text(sql), params).mappings().all()
        ]

    def _case_exists(
        self, *, building_id: UUID | None, case_class: str, evidence_ids: list[UUID]
    ) -> dict[str, Any] | None:
        rows = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.reconcile_cases
                WHERE organization_id=:org AND project_id=:project
                  AND building_id IS NOT DISTINCT FROM :building
                  AND case_class=:class AND status='open'
                ORDER BY created_at DESC
            """),
                {
                    "org": self.org,
                    "project": self.project,
                    "building": building_id,
                    "class": case_class,
                },
            )
            .mappings()
            .all()
        )
        wanted = {str(x) for x in evidence_ids}
        for row in rows:
            if {str(x) for x in row["evidence_ids"]} == wanted:
                return dict(row)
        return None

    def _insert_case(
        self,
        *,
        building_id: UUID | None,
        evidence_ids: list[UUID],
        case_class: str,
        estimated: bool,
    ) -> dict[str, Any]:
        existing = self._case_exists(
            building_id=building_id, case_class=case_class, evidence_ids=evidence_ids
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        row = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.reconcile_cases (
                    id,organization_id,project_id,building_id,evidence_ids,case_class,
                    estimated,status,resolution,revision,created_by_actor_id,updated_by_actor_id,
                    created_at,updated_at
                ) VALUES (
                    :id,:org,:project,:building,CAST(:evidence AS jsonb),:class,
                    :estimated,'open',NULL,1,:actor,:actor,:now,:now
                ) RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": self.org,
                    "project": self.project,
                    "building": building_id,
                    "evidence": json.dumps([str(x) for x in evidence_ids]),
                    "class": case_class,
                    "estimated": estimated,
                    "actor": self.actor,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        return dict(row)

    def rebuild_cases(
        self,
        *,
        removed_building_ids: set[UUID] | None = None,
        estimated_building_ids: set[UUID] | None = None,
    ) -> list[dict[str, Any]]:
        self._prepare("edit")
        removed = removed_building_ids or set()
        estimated = estimated_building_ids or set()
        buildings = (
            self.session.execute(
                text("""
                SELECT id FROM house_numbering.buildings
                WHERE organization_id=:org AND project_id=:project AND state='active'
                ORDER BY id
            """),
                {"org": self.org, "project": self.project},
            )
            .scalars()
            .all()
        )
        all_evidence = self.evidence()
        by_building: dict[UUID, list[dict[str, Any]]] = {}
        unmatched: list[dict[str, Any]] = []
        for ev in all_evidence:
            if ev["building_id"] is None:
                if ev["origin"] == "certificate":
                    unmatched.append(ev)
                continue
            by_building.setdefault(ev["building_id"], []).append(ev)

        results: list[dict[str, Any]] = []
        for building_id in buildings:
            rows = by_building.get(building_id, [])
            latest: dict[str, dict[str, Any]] = {}
            for row in rows:
                latest.setdefault(str(row["origin"]), row)
            certificate = latest.get("certificate")
            cad = latest.get("cad")
            survey = latest.get("survey")
            case_class = classify_reconciliation(
                certificate=str(certificate["raw_number"]) if certificate else None,
                cad=str(cad["raw_number"]) if cad else None,
                survey=str(survey["raw_number"]) if survey else None,
                surveyed=survey is not None,
                exists=building_id not in removed,
                building_linked=True,
            )
            evidence_ids = [row["id"] for row in (certificate, cad, survey) if row]
            results.append(
                self._insert_case(
                    building_id=building_id,
                    evidence_ids=evidence_ids,
                    case_class=case_class,
                    estimated=building_id in estimated,
                )
            )
        for ev in unmatched:
            results.append(
                self._insert_case(
                    building_id=None,
                    evidence_ids=[ev["id"]],
                    case_class="certificate_unmatched",
                    estimated=False,
                )
            )
        self.session.commit()
        return results

    def list_cases(
        self, *, status: str | None = None, case_class: str | None = None
    ) -> list[dict[str, Any]]:
        self._prepare("read")
        sql = """
            SELECT * FROM house_numbering.reconcile_cases
            WHERE organization_id=:org AND project_id=:project
        """
        params: dict[str, Any] = {"org": self.org, "project": self.project}
        if status:
            sql += " AND status=:status"
            params["status"] = status
        if case_class:
            sql += " AND case_class=:class"
            params["class"] = case_class
        sql += " ORDER BY created_at DESC,id DESC"
        return [
            dict(row)
            for row in self.session.execute(text(sql), params).mappings().all()
        ]

    def suggest_unmatched_certificate(self, evidence_id: UUID) -> dict[str, Any]:
        self._prepare("read")
        evidence = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.evidence
                WHERE organization_id=:org AND project_id=:project AND id=:id
                  AND origin='certificate' AND building_id IS NULL
            """),
                {"org": self.org, "project": self.project, "id": evidence_id},
            )
            .mappings()
            .first()
        )
        if evidence is None:
            raise PlatformNotFoundError("unmatched certificate evidence not found")
        if evidence["route_id"] is None:
            return {"building_id": None, "reason": "no_route_scope"}
        candidates: list[EvidenceCandidate] = []
        rows = (
            self.session.execute(
                text("""
                SELECT b.id AS building_id,n.route_id,n.number_text,n.kind
                FROM house_numbering.buildings b
                JOIN house_numbering.address_numbers n
                  ON n.organization_id=b.organization_id AND n.project_id=b.project_id
                 AND n.building_id=b.id AND n.retired_at IS NULL
                WHERE b.organization_id=:org AND b.project_id=:project
                  AND n.route_id=:route
            """),
                {
                    "org": self.org,
                    "project": self.project,
                    "route": evidence["route_id"],
                },
            )
            .mappings()
            .all()
        )
        grouped: dict[UUID, dict[str, str | None]] = {}
        for row in rows:
            item = grouped.setdefault(row["building_id"], {"old": None, "new": None})
            if (
                row["kind"] in {"old", "certificate", "cad", "survey"}
                and item["old"] is None
            ):
                item["old"] = str(row["number_text"])
            if (
                row["kind"] in {"proposed", "submitted", "approved"}
                and item["new"] is None
            ):
                item["new"] = str(row["number_text"])
        for building_id, numbers in grouped.items():
            candidates.append(
                EvidenceCandidate(
                    building_id=str(building_id),
                    route_id=str(evidence["route_id"]),
                    old_number=numbers["old"],
                    new_number=numbers["new"],
                )
            )
        raw = str(evidence["raw_number"] or "").strip()
        match = match_certificate(
            candidates,
            route_id=str(evidence["route_id"]),
            old_number=raw or None,
            new_number=raw or None,
        )
        return {"building_id": match.building_id, "reason": match.reason}

    def resolve_case(
        self,
        case_id: UUID,
        *,
        expected_revision: int,
        status: str,
        resolution: str,
        building_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._prepare("edit")
        if status not in {"resolved", "ignored"}:
            raise PlatformConflictError("case can only be resolved or ignored")
        row = (
            self.session.execute(
                text("""
                UPDATE house_numbering.reconcile_cases
                SET status=:status,resolution=:resolution,
                    building_id=COALESCE(:building,building_id),revision=revision+1,
                    updated_by_actor_id=:actor,updated_at=:now
                WHERE organization_id=:org AND project_id=:project AND id=:id
                  AND revision=:revision AND status='open'
                RETURNING *
            """),
                {
                    "status": status,
                    "resolution": resolution.strip(),
                    "building": building_id,
                    "actor": self.actor,
                    "now": datetime.now(UTC),
                    "org": self.org,
                    "project": self.project,
                    "id": case_id,
                    "revision": expected_revision,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformConflictError(
                "reconcile case is stale or closed", code="STALE_RECONCILE_CASE"
            )
        self.session.commit()
        return dict(row)
