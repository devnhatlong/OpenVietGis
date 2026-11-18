from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.bootstrap.domain import InstallationState


class PlatformRepository(Protocol):
    def get_installation_state(
        self,
        *,
        for_update: bool = False,
    ) -> InstallationState: ...

    def is_initialized(self) -> bool: ...

    def mark_initialized(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> InstallationState: ...
