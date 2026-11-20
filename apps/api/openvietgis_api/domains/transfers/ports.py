"""Ports and domain errors for R005 Import/Export and Durable Jobs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.spatial.domain import (
    DataSource,
    NativeGeometry,
    ReferenceFeature,
    SourceField,
)
from openvietgis_api.domains.transfers.domain import (
    ArtifactState,
    DerivedArtifact,
    ExportFieldMapping,
    InspectedMember,
    JobStatus,
    ParsedMemberData,
    SourceAsset,
    TransferFormat,
    TransferJob,
)


class TransferError(Exception):
    """Base error with safe customer-facing code and message."""

    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class TransferLimitExceededError(TransferError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=413)


class TransferFormatError(TransferError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=422)


class TransferValidationError(TransferError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=422)


class TransferConflictError(TransferError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=409)


class TransferNotFoundError(TransferError):
    def __init__(self, message: str = "Transfer resource not found.") -> None:
        super().__init__("TRANSFER_NOT_FOUND", message, status_code=404)


class TransferArtifactUnavailableError(TransferError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=410)


class ObjectStorePort(Protocol):
    def put_bytes(self, storage_key: str, data: bytes) -> tuple[str, int]:
        """Atomically store immutable bytes and return (sha256, byte_size)."""

    def get_bytes(self, storage_key: str, *, expected_sha256: str) -> bytes:
        """Read immutable bytes and verify integrity against expected SHA-256."""

    def delete_object(self, storage_key: str) -> None:
        """Remove an unreferenced staged object safely."""


class FormatCodecPort(Protocol):
    def detect_format(self, data: bytes) -> TransferFormat:
        """Detect format strictly from file content/structure, never extension."""

    def list_members(
        self, fmt: TransferFormat, data: bytes, *, encoding: str | None = None
    ) -> tuple[InspectedMember, ...]:
        """List all members with eligibility and detected CRS/encoding."""

    def parse_member(
        self,
        fmt: TransferFormat,
        data: bytes,
        *,
        member_name: str,
        declared_crs: int | None = None,
        declared_encoding: str | None = None,
    ) -> ParsedMemberData:
        """Fully parse and validate all records in the selected member."""

    def write_dataset(
        self,
        fmt: TransferFormat,
        *,
        layer_name: str,
        crs_code: int,
        geometry_family: str,
        field_mappings: Sequence[ExportFieldMapping],
        features: Sequence[tuple[str, dict[str, Any], NativeGeometry]],
    ) -> tuple[bytes, str, str]:
        """Write dataset bytes and return (payload_bytes, filename_extension, content_type)."""


class TransferRepository(Protocol):
    def verify_project_authority(self, *, context: AuthorizationContext, write: bool) -> None:
        """Enforce active organization, project lifecycle and permission."""

    def create_source_asset(
        self, *, context: AuthorizationContext, asset: SourceAsset
    ) -> SourceAsset: ...

    def get_source_asset(
        self, *, context: AuthorizationContext, asset_id: UUID
    ) -> SourceAsset | None: ...

    def get_job_by_operation(
        self, *, context: AuthorizationContext, operation_id: UUID, lock: bool = False
    ) -> TransferJob | None: ...

    def get_job(
        self, *, context: AuthorizationContext, job_id: UUID, lock: bool = False
    ) -> TransferJob | None: ...

    def list_jobs(
        self, *, context: AuthorizationContext, limit: int = 50
    ) -> tuple[TransferJob, ...]: ...

    def create_job(self, *, context: AuthorizationContext, job: TransferJob) -> TransferJob: ...

    def record_attempt(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        attempt_number: int,
        status: str,
        started_at: datetime,
        finished_at: datetime | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None: ...

    def update_job(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        status: JobStatus,
        attempt_count: int | None = None,
        target_source_id: UUID | None = None,
        target_layer_id: UUID | None = None,
        source_content_revision: str | None = None,
        source_schema_revision: str | None = None,
        artifact_id: UUID | None = None,
        inspection_report: dict[str, Any] | None = None,
        result_report: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> TransferJob: ...

    def validate_and_transform_geometries(
        self,
        *,
        context: AuthorizationContext,
        geometries: Sequence[NativeGeometry],
        source_crs: int,
        target_crs: int,
        expected_family: str,
    ) -> tuple[NativeGeometry, ...]:
        """Validate PostGIS ST_IsValid and run approved R003 PROJ transform if CRS differs."""

    def publish_imported_source_and_layer(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        asset: SourceAsset,
        source: DataSource,
        fields: Sequence[SourceField],
        features: Sequence[ReferenceFeature],
        layer_id: UUID,
        layer_name: str,
        result_report: dict[str, Any],
    ) -> TransferJob:
        """Atomically publish DataSource, fields, features, Layer, CatalogChange, Audit, Job."""

    def load_pinned_export_source(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        expected_content_revision: str,
        expected_schema_revision: str,
    ) -> tuple[DataSource, tuple[SourceField, ...], tuple[ReferenceFeature, ...], str]:
        """Load complete pinned source features; returns (source, fields, features, layer_name)."""

    def publish_export_artifact(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        artifact: DerivedArtifact,
        result_report: dict[str, Any],
    ) -> TransferJob:
        """Atomically record DerivedArtifact, AuditEvent, and Job succeeded."""

    def get_artifact(
        self, *, context: AuthorizationContext, artifact_id: UUID
    ) -> DerivedArtifact | None: ...

    def mark_artifact_state(
        self, *, context: AuthorizationContext, artifact_id: UUID, state: ArtifactState
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
