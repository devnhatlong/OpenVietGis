from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domain.foundation import FoundationSampleRecord


class FoundationRepository(Protocol):
    def add(self, record: FoundationSampleRecord) -> FoundationSampleRecord: ...

    def get(self, record_id: UUID) -> FoundationSampleRecord | None: ...
