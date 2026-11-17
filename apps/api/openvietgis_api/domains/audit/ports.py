from __future__ import annotations

from typing import Protocol

from openvietgis_api.domains.audit.domain import AuditEvent


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...
