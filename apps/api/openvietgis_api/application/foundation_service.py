from __future__ import annotations

from uuid import UUID

from openvietgis_api.domain.foundation import FoundationSampleRecord
from openvietgis_api.ports.foundation_repository import FoundationRepository


class FoundationRecordNotFoundError(Exception):
    pass


class FoundationService:
    def __init__(self, repository: FoundationRepository) -> None:
        self._repository = repository

    def create(self, label: str) -> FoundationSampleRecord:
        record = FoundationSampleRecord.create(label)
        return self._repository.add(record)

    def get(self, record_id: UUID) -> FoundationSampleRecord:
        record = self._repository.get(record_id)
        if record is None:
            raise FoundationRecordNotFoundError(
                f"Foundation sample record {record_id} was not found"
            )
        return record
