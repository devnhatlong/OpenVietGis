from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from openvietgis_api.domains.tenancy.domain import ActorType


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    organization_id: UUID | None
    actor_type: ActorType
    actor_id: UUID | None
    actor_display_snapshot: str
    action: str
    resource_type: str | None
    resource_id: UUID | None
    outcome: AuditOutcome
    metadata: dict[str, Any]
    created_at: datetime
