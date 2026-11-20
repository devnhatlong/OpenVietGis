"""R008 Spatial Processing & Durable Jobs pure domain definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import PlatformValidationError


class AlgorithmId(StrEnum):
    BUFFER = "buffer"
    CLIP = "clip"
    DISSOLVE = "dissolve"


class ProcessingStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AlgorithmDescriptor:
    id: AlgorithmId
    name: str
    description: str
    required_inputs: tuple[str, ...]
    parameters_schema: dict[str, Any]


ALGORITHM_REGISTRY: dict[AlgorithmId, AlgorithmDescriptor] = {
    AlgorithmId.BUFFER: AlgorithmDescriptor(
        id=AlgorithmId.BUFFER,
        name="Buffer",
        description="Creates metric buffers around geometries and publishes a new Polygon layer.",
        required_inputs=("input_layer_id",),
        parameters_schema={
            "distance_meters": {"type": "number", "min": 0.1, "max": 500000.0},
            "quad_segs": {"type": "integer", "min": 2, "max": 16, "default": 8},
        },
    ),
    AlgorithmId.CLIP: AlgorithmDescriptor(
        id=AlgorithmId.CLIP,
        name="Clip",
        description="Clips input layer features to an authorized overlay polygon layer.",
        required_inputs=("input_layer_id", "overlay_layer_id"),
        parameters_schema={},
    ),
    AlgorithmId.DISSOLVE: AlgorithmDescriptor(
        id=AlgorithmId.DISSOLVE,
        name="Dissolve",
        description="Unions features globally or grouped by an attribute field into a new layer.",
        required_inputs=("input_layer_id",),
        parameters_schema={
            "group_by_field": {"type": "string", "nullable": True},
        },
    ),
}


@dataclass(frozen=True, slots=True)
class ProcessingJobRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    algorithm_id: AlgorithmId
    operation_id: str
    status: ProcessingStatus
    actor_type: str
    actor_id: UUID
    input_refs: dict[str, Any]
    parameters: dict[str, Any]
    output_name: str
    output_crs: int
    engine_version: str
    attempt_count: int
    output_source_id: UUID | None
    output_layer_id: UUID | None
    output_content_revision: str | None
    feature_count: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


def validate_algorithm_parameters(
    algorithm_id: AlgorithmId,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    if algorithm_id == AlgorithmId.BUFFER:
        raw_dist = parameters.get("distance_meters")
        if raw_dist is None or isinstance(raw_dist, bool):
            raise PlatformValidationError(
                "buffer requires numeric distance_meters > 0", code="INVALID_PARAMETERS"
            )
        dist = float(raw_dist)
        if not (0.1 <= dist <= 500_000.0):
            raise PlatformValidationError(
                "distance_meters must be between 0.1 and 500000", code="INVALID_PARAMETERS"
            )
        quad_segs = int(parameters.get("quad_segs", 8))
        if not (2 <= quad_segs <= 16):
            raise PlatformValidationError(
                "quad_segs must be between 2 and 16", code="INVALID_PARAMETERS"
            )
        return {"distance_meters": dist, "quad_segs": quad_segs}
    if algorithm_id == AlgorithmId.CLIP:
        return {}
    if algorithm_id == AlgorithmId.DISSOLVE:
        group_field = parameters.get("group_by_field")
        if group_field is not None and not isinstance(group_field, str):
            raise PlatformValidationError(
                "group_by_field must be a field id string or null", code="INVALID_PARAMETERS"
            )
        return {
            "group_by_field": group_field.strip()
            if isinstance(group_field, str) and group_field.strip()
            else None
        }
    raise PlatformValidationError(
        f"unsupported algorithm {algorithm_id!r}", code="INVALID_ALGORITHM"
    )
