from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.audit.domain import AuditEvent
from openvietgis_api.domains.authorization.context import AuthorizationContext


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...

    def list_for_organization(
        self,
        organization_id: UUID,
        *,
        context: AuthorizationContext,
        limit: int,
    ) -> list[AuditEvent]: ...
