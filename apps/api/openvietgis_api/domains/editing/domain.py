"""R006 Editing & Change History pure domain types and validation."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.spatial.domain import (
    FieldType,
    GeometryFamily,
    SourceField,
    SpatialValidationError,
    canonical_attribute_value,
)

_FEATURE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_OP_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class EditOpType(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class EditOperationInput:
    op_type: EditOpType
    feature_id: str
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ChangesetOperationRecord:
    id: UUID
    ordinal: int
    op_type: EditOpType
    feature_id: str
    before_geometry: dict[str, Any] | None
    after_geometry: dict[str, Any] | None
    before_properties: dict[str, Any] | None
    after_properties: dict[str, Any] | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ChangesetRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    source_id: UUID
    actor_type: str
    actor_id: UUID
    actor_display_snapshot: str
    operation_id: str
    base_content_revision: str
    resulting_content_revision: str
    base_catalog_revision: int
    resulting_catalog_revision: int
    summary: str
    status: str
    operation_count: int
    audit_event_id: UUID
    reverted_from_changeset_id: UUID | None
    created_at: datetime
    operations: tuple[ChangesetOperationRecord, ...] = ()


def validate_operation_id(operation_id: str) -> str:
    cleaned = operation_id.strip()
    if not _OP_ID_RE.match(cleaned):
        raise PlatformValidationError(
            "operation_id must be 1..128 URL-safe characters",
            code="INVALID_OPERATION_ID",
        )
    return cleaned


def validate_feature_id(feature_id: str) -> str:
    cleaned = feature_id.strip()
    if not _FEATURE_ID_RE.match(cleaned):
        raise PlatformValidationError(
            f"invalid feature_id {feature_id!r}",
            code="INVALID_FEATURE_ID",
        )
    return cleaned


def validate_geometry_payload(
    geometry: dict[str, Any] | None,
    expected_family: GeometryFamily,
) -> tuple[str, Any]:
    if not isinstance(geometry, dict):
        raise PlatformValidationError("geometry object is required", code="MISSING_GEOMETRY")
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype != expected_family.value:
        raise PlatformValidationError(
            f"geometry type {gtype!r} does not match source family {expected_family.value!r}",
            code="GEOMETRY_FAMILY_MISMATCH",
        )
    if gtype == "Point":
        _validate_pos(coords)
    elif gtype == "LineString":
        if not isinstance(coords, list) or len(coords) < 2:
            raise PlatformValidationError(
                "LineString requires at least 2 positions", code="INVALID_GEOMETRY"
            )
        for p in coords:
            _validate_pos(p)
    elif gtype == "Polygon":
        if not isinstance(coords, list) or len(coords) < 1:
            raise PlatformValidationError(
                "Polygon requires at least 1 linear ring", code="INVALID_GEOMETRY"
            )
        for ring in coords:
            if not isinstance(ring, list) or len(ring) < 4:
                raise PlatformValidationError(
                    "Polygon ring requires at least 4 positions", code="INVALID_GEOMETRY"
                )
            for p in ring:
                _validate_pos(p)
            if ring[0] != ring[-1]:
                raise PlatformValidationError(
                    "Polygon ring must be closed (no silent repair)",
                    code="INVALID_GEOMETRY",
                )
    else:
        raise PlatformValidationError(
            f"unsupported geometry type {gtype!r}", code="UNSUPPORTED_GEOMETRY"
        )
    return gtype, coords


def _validate_pos(pos: Any) -> None:
    if not isinstance(pos, (list, tuple)) or len(pos) != 2:
        raise PlatformValidationError(
            "only 2D XY coordinates are supported", code="UNSUPPORTED_DIMENSIONS"
        )
    x, y = pos[0], pos[1]
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, (int, float))
        or not isinstance(y, (int, float))
    ):
        raise PlatformValidationError("coordinates must be finite numbers", code="INVALID_GEOMETRY")
    if not (math.isfinite(float(x)) and math.isfinite(float(y))):
        raise PlatformValidationError("coordinates must be finite numbers", code="INVALID_GEOMETRY")


def geometry_to_wkt(geometry: Mapping[str, Any]) -> str:
    gtype = str(geometry["type"])
    coords: Any = geometry["coordinates"]
    if gtype == "Point":
        return f"POINT({float(coords[0])!r} {float(coords[1])!r})"
    if gtype == "LineString":
        pts = ", ".join(f"{float(p[0])!r} {float(p[1])!r}" for p in coords)
        return f"LINESTRING({pts})"
    rings = []
    for ring in coords:
        pts = ", ".join(f"{float(p[0])!r} {float(p[1])!r}" for p in ring)
        rings.append(f"({pts})")
    return f"POLYGON({', '.join(rings)})"


def validate_typed_attributes(
    properties: Mapping[str, Any] | None,
    fields: Sequence[SourceField],
) -> dict[str, Any]:
    raw = dict(properties or {})
    field_map = {f.field_id: f for f in fields}
    unknown = sorted(set(raw.keys()) - set(field_map.keys()))
    if unknown:
        raise PlatformValidationError(
            f"unknown attribute fields: {', '.join(unknown)}",
            code="SCHEMA_MISMATCH",
            details={"unknown_fields": unknown},
        )
    out: dict[str, Any] = {}
    for field in fields:
        val = raw.get(field.field_id)
        try:
            # Retain numeric JSON compatibility, but use the Core canonical
            # representation before publishing: e.g. 1000.0 -> "1000".
            if field.type == FieldType.DECIMAL and type(val) in (int, float):
                val = Decimal(str(val))
            out[field.field_id] = canonical_attribute_value(field, val)
        except (SpatialValidationError, InvalidOperation) as exc:
            raise PlatformValidationError(
                f"field {field.field_id!r} does not match {field.type.value}: {exc}",
                code="SCHEMA_MISMATCH",
                details={"field": field.field_id},
            ) from exc
    return out


def changeset_request_digest(
    *,
    base_content_revision: str,
    summary: str,
    operations: Sequence[EditOperationInput],
    reverted_from_changeset_id: UUID | None,
    base_schema_revision: str | None = None,
) -> str:
    """Canonical request identity; legacy omitted schema preserves its exact digest."""
    try:
        payload = json.dumps(
            {
                "base": base_content_revision,
                **(
                    {"base_schema": base_schema_revision}
                    if base_schema_revision is not None
                    else {}
                ),
                "summary": summary,
                "reverted_from": str(reverted_from_changeset_id)
                if reverted_from_changeset_id
                else None,
                "operations": [
                    {
                        "op_type": op.op_type.value,
                        "feature_id": validate_feature_id(op.feature_id),
                        "geometry": op.geometry,
                        "properties": op.properties,
                    }
                    for op in operations
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PlatformValidationError(
            "changeset must contain finite JSON values",
            code="INVALID_CHANGESET_REQUEST",
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def compute_content_revision(
    source_id: UUID,
    base_revision: str,
    operations_fingerprint: Sequence[Mapping[str, Any]],
) -> str:
    payload = json.dumps(
        {
            "source_id": str(source_id),
            "base": base_revision,
            "ops": list(operations_fingerprint),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def snap_point_to_candidates(
    target: tuple[float, float],
    vertices: Sequence[tuple[float, float]],
    segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
    tolerance: float,
) -> dict[str, Any]:
    """Pure deterministic 2D vertex/segment snapping helper (R006 first-slice)."""
    tx, ty = target
    best_dist = tolerance
    best_point: tuple[float, float] = (tx, ty)
    snapped_kind = "none"

    for vx, vy in vertices:
        d = math.hypot(tx - vx, ty - vy)
        if d <= best_dist:
            best_dist = d
            best_point = (vx, vy)
            snapped_kind = "vertex"

    if snapped_kind == "none":
        for (ax, ay), (bx, by) in segments:
            dx, dy = bx - ax, by - ay
            len_sq = dx * dx + dy * dy
            if len_sq == 0.0:
                continue
            t = max(0.0, min(1.0, ((tx - ax) * dx + (ty - ay) * dy) / len_sq))
            px, py = ax + t * dx, ay + t * dy
            d = math.hypot(tx - px, ty - py)
            if d <= best_dist:
                best_dist = d
                best_point = (px, py)
                snapped_kind = "segment"

    return {
        "snapped": snapped_kind != "none",
        "kind": snapped_kind,
        "point": [best_point[0], best_point[1]],
        "distance": best_dist if snapped_kind != "none" else None,
    }
