from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InstallationState:
    singleton_key: str
    initialized_at: datetime | None
    initial_organization_id: UUID | None
    initialized_by_user_id: UUID | None
    updated_at: datetime
