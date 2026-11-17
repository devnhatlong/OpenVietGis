from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from openvietgis_api.domain.foundation import FoundationSampleRecord


class SqlFoundationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: FoundationSampleRecord) -> FoundationSampleRecord:
        self._session.execute(
            text(
                """
                INSERT INTO foundation.sample_records (id, label, created_at, updated_at)
                VALUES (:id, :label, :created_at, :updated_at)
                """
            ),
            {
                "id": record.id,
                "label": record.label,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            },
        )
        return record

    def get(self, record_id: UUID) -> FoundationSampleRecord | None:
        row = (
            self._session.execute(
                text(
                    """
                    SELECT id, label, created_at, updated_at
                    FROM foundation.sample_records
                    WHERE id = :id
                    """
                ),
                {"id": record_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return FoundationSampleRecord(
            id=row["id"],
            label=row["label"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
