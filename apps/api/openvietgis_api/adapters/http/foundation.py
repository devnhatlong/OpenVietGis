from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.foundation_repository import SqlFoundationRepository
from openvietgis_api.application.foundation_service import FoundationService
from openvietgis_api.domain.foundation import FoundationSampleRecord

router = APIRouter()


class FoundationRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("label must not be blank")
        return normalized


class FoundationRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    label: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: FoundationSampleRecord) -> "FoundationRecordResponse":
        return cls(
            id=record.id,
            label=record.label,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


@router.post("/foundation-records", status_code=201, response_model=FoundationRecordResponse)
def create_foundation_record(payload: FoundationRecordCreate) -> FoundationRecordResponse:
    with get_session_factory()() as session:
        service = FoundationService(SqlFoundationRepository(session))
        record = service.create(payload.label)
        session.commit()
        return FoundationRecordResponse.from_domain(record)


@router.get("/foundation-records/{record_id}", response_model=FoundationRecordResponse)
def get_foundation_record(record_id: UUID) -> FoundationRecordResponse:
    with get_session_factory()() as session:
        service = FoundationService(SqlFoundationRepository(session))
        record = service.get(record_id)
        return FoundationRecordResponse.from_domain(record)