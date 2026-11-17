from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class FoundationSampleRecord:
    id: UUID
    label: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, label: str) -> FoundationSampleRecord:
        normalized = label.strip()
        if not normalized:
            raise ValueError("label must not be blank")
        if len(normalized) > 120:
            raise ValueError("label must be 120 characters or fewer")
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            label=normalized,
            created_at=now,
            updated_at=now,
        )
