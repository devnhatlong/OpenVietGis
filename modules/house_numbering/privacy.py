"""Protected household data with explicit purpose, access gate and immutable access log."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from modules.house_numbering.persistence import HouseNumberingRepository


class HouseNumberingPrivateData:
    def __init__(self, session: Session, context: AuthorizationContext) -> None:
        self.session = session
        self.context = context
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        self.org = context.organization_id
        self.project = context.project_id
        self.actor = context.actor.actor_id
        self.repo = HouseNumberingRepository(session, context)

    def _log(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        metadata: dict[str, Any],
    ) -> None:
        self.session.execute(
            text("""
                INSERT INTO house_numbering.access_log (
                    id,organization_id,project_id,actor_id,action,resource_type,
                    resource_id,metadata,created_at
                ) VALUES (
                    :id,:org,:project,:actor,:action,:type,:resource,CAST(:metadata AS jsonb),:now
                )
            """),
            {
                "id": uuid4(),
                "org": self.org,
                "project": self.project,
                "actor": self.actor,
                "action": action,
                "type": resource_type,
                "resource": resource_id,
                "metadata": json.dumps(metadata),
                "now": datetime.now(UTC),
            },
        )

    def upsert(
        self,
        *,
        building_id: UUID,
        purpose: str,
        consent: bool,
        lawful_basis_ref: str | None,
        protected_data: dict[str, Any],
        expires_at: datetime | None,
        record_id: UUID | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        self.repo.enable_private_access()
        self.repo.get_building(building_id)
        if not purpose.strip() or len(purpose) > 500:
            raise PlatformValidationError("private-data purpose is required")
        if len(json.dumps(protected_data, ensure_ascii=False)) > 64_000:
            raise PlatformValidationError("protected household payload is too large")
        now = datetime.now(UTC)
        if record_id is None:
            record_id = uuid4()
            row = (
                self.session.execute(
                    text("""
                    INSERT INTO house_numbering.restricted_households (
                        id,organization_id,project_id,building_id,purpose,consent,lawful_basis_ref,
                        protected_data,expires_at,revision,created_by_actor_id,updated_by_actor_id,
                        created_at,updated_at
                    ) VALUES (
                        :id,:org,:project,:building,:purpose,:consent,:basis,CAST(:data AS jsonb),
                        :expires,1,:actor,:actor,:now,:now
                    ) RETURNING *
                """),
                    {
                        "id": record_id,
                        "org": self.org,
                        "project": self.project,
                        "building": building_id,
                        "purpose": purpose.strip(),
                        "consent": consent,
                        "basis": lawful_basis_ref,
                        "data": json.dumps(protected_data, ensure_ascii=False),
                        "expires": expires_at,
                        "actor": self.actor,
                        "now": now,
                    },
                )
                .mappings()
                .one()
            )
            action = "private.create"
        else:
            if expected_revision is None:
                raise PlatformValidationError(
                    "expected_revision required for private-data update"
                )
            row = (
                self.session.execute(
                    text("""
                    UPDATE house_numbering.restricted_households
                    SET building_id=:building,purpose=:purpose,consent=:consent,
                        lawful_basis_ref=:basis,protected_data=CAST(:data AS jsonb),
                        expires_at=:expires,revision=revision+1,updated_by_actor_id=:actor,updated_at=:now
                    WHERE organization_id=:org AND project_id=:project AND id=:id
                      AND revision=:revision
                    RETURNING *
                """),
                    {
                        "building": building_id,
                        "purpose": purpose.strip(),
                        "consent": consent,
                        "basis": lawful_basis_ref,
                        "data": json.dumps(protected_data, ensure_ascii=False),
                        "expires": expires_at,
                        "actor": self.actor,
                        "now": now,
                        "org": self.org,
                        "project": self.project,
                        "id": record_id,
                        "revision": expected_revision,
                    },
                )
                .mappings()
                .first()
            )
            if row is None:
                raise PlatformConflictError(
                    "protected household record is stale", code="STALE_PRIVATE_RECORD"
                )
            action = "private.update"
        self._log(
            action=action,
            resource_type="restricted_household",
            resource_id=record_id,
            metadata={"building_id": str(building_id), "purpose": purpose[:100]},
        )
        self.session.commit()
        return dict(row)

    def read_for_building(
        self, building_id: UUID, *, purpose: str
    ) -> list[dict[str, Any]]:
        self.repo.enable_private_access()
        if not purpose.strip():
            raise PlatformValidationError("access purpose required")
        rows = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.restricted_households
                WHERE organization_id=:org AND project_id=:project AND building_id=:building
                  AND (expires_at IS NULL OR expires_at>now())
                ORDER BY created_at DESC,id DESC
            """),
                {"org": self.org, "project": self.project, "building": building_id},
            )
            .mappings()
            .all()
        )
        self._log(
            action="private.read",
            resource_type="restricted_household",
            resource_id=None,
            metadata={
                "building_id": str(building_id),
                "purpose": purpose[:100],
                "count": len(rows),
            },
        )
        self.session.commit()
        return [dict(row) for row in rows]

    def read(self, record_id: UUID, *, purpose: str) -> dict[str, Any]:
        self.repo.enable_private_access()
        row = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.restricted_households
                WHERE organization_id=:org AND project_id=:project AND id=:id
                  AND (expires_at IS NULL OR expires_at>now())
            """),
                {"org": self.org, "project": self.project, "id": record_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("protected household record not found")
        self._log(
            action="private.read",
            resource_type="restricted_household",
            resource_id=record_id,
            metadata={"purpose": purpose[:100]},
        )
        self.session.commit()
        return dict(row)
