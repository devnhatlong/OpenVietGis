from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from openvietgis_api.domains.tenancy.domain import ActorType, ResourceRole, ResourceScopeKind


@dataclass(frozen=True, slots=True)
class ResourceGrant:
    id: UUID
    organization_id: UUID
    subject_kind: str
    membership_id: UUID | None
    service_principal_id: UUID | None
    scope_kind: ResourceScopeKind
    workspace_id: UUID | None
    project_id: UUID | None
    role: ResourceRole
    created_at: datetime
    created_by_actor_type: ActorType
    created_by_actor_id: UUID | None
    revoked_at: datetime | None
