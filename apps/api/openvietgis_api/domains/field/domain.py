"""R013 Field & Offline package and outbox sync domain."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

MAX_OFFLINE_PACKAGE_FEATURES = 5000
MAX_OFFLINE_TTL_HOURS = 24 * 14


@dataclass(frozen=True, slots=True)
class OfflinePackageRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str
    profile: str
    aoi_bbox: dict[str, float]
    crs_code: int
    layer_pins: list[dict[str, object]]
    feature_count: int
    storage_key: str
    sha256: str
    byte_size: int
    expires_at: datetime
    revoked_at: datetime | None
    created_by_actor_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SyncBatchRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    package_id: UUID
    operation_id: str
    status: str
    submitted_ops_count: int
    applied_changeset_ids: list[str]
    conflicts: list[dict[str, object]]
    actor_id: UUID
    created_at: datetime
    operation_receipts: list[dict[str, object]] = field(default_factory=list)


def offline_core_feature_id(
    *,
    actor_id: UUID,
    organization_id: UUID,
    project_id: UUID,
    package_id: UUID,
    source_id: UUID,
    client_operation_id: UUID,
) -> str:
    """Server-owned deterministic feature identity, independent of local draft label/group."""
    scope = (
        actor_id,
        organization_id,
        project_id,
        package_id,
        source_id,
        client_operation_id,
    )
    digest = hashlib.sha256(
        ("ovg-field-feature-v1:" + ":".join(str(item) for item in scope)).encode("ascii")
    ).hexdigest()
    return f"field-core-{digest[:48]}"
