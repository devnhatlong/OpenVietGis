"""R014 Generic Internal Extension Framework domain (ADR-008: zero vertical knowledge)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import PlatformValidationError

_EXT_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,99}$")
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SUPPORTED_API_RANGE = "1.x"


@dataclass(frozen=True, slots=True)
class ExtensionManifestRecord:
    id: UUID
    organization_id: UUID
    extension_key: str
    version: str
    api_compatibility: str
    display_name: str
    description: str
    permissions: list[str]
    commands: list[dict[str, Any]]
    capabilities: list[str]
    entity_schemas: dict[str, dict[str, Any]]
    enabled: bool
    registered_by_actor_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectActivationRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    manifest_id: UUID
    extension_key: str
    status: str
    activated_by_actor_id: UUID
    activated_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ExtensionDataRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    extension_key: str
    entity_name: str
    payload: dict[str, Any]
    linked_layer_id: UUID | None
    linked_feature_id: str | None
    created_by_actor_id: UUID
    created_at: datetime
    updated_at: datetime


def validate_manifest_contract(
    *,
    extension_key: str,
    version: str,
    api_compatibility: str,
    permissions: list[str],
    entity_schemas: dict[str, dict[str, Any]],
) -> None:
    """Validate versioned extension manifest & permission namespace isolation."""
    if not _EXT_KEY_RE.match(extension_key):
        raise PlatformValidationError(
            "extension_key must match ^[a-z][a-z0-9_-]{1,99}$",
            code="INVALID_EXTENSION_KEY",
        )
    if not _SEMVER_RE.match(version):
        raise PlatformValidationError("version must be semver X.Y.Z", code="INVALID_VERSION")
    if api_compatibility != _SUPPORTED_API_RANGE:
        raise PlatformValidationError(
            f"unsupported api_compatibility {api_compatibility!r}; "
            f"expected {_SUPPORTED_API_RANGE!r}",
            code="INCOMPATIBLE_EXTENSION_API",
        )
    prefix = f"ext.{extension_key}."
    for perm in permissions:
        if not perm.startswith(prefix):
            raise PlatformValidationError(
                f"permission {perm!r} must be namespaced under {prefix!r}",
                code="INVALID_PERMISSION_NAMESPACE",
            )
    if not entity_schemas:
        raise PlatformValidationError(
            "manifest must declare at least one entity_schema", code="EMPTY_SCHEMAS"
        )


def validate_record_against_schema(
    *,
    entity_name: str,
    payload: dict[str, Any],
    entity_schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Validate an extension record payload strictly against the manifest's declared fields."""
    schema = entity_schemas.get(entity_name)
    if schema is None:
        raise PlatformValidationError(
            f"unknown entity {entity_name!r} for this extension", code="UNKNOWN_ENTITY"
        )
    fields: dict[str, Any] = schema.get("fields", {})
    unknown = sorted(set(payload.keys()) - set(fields.keys()))
    if unknown:
        raise PlatformValidationError(
            f"unknown fields in extension record: {', '.join(unknown)}",
            code="SCHEMA_MISMATCH",
        )
    cleaned: dict[str, Any] = {}
    for fname, spec in fields.items():
        req = bool(spec.get("required", False))
        ftype = str(spec.get("type", "text"))
        val = payload.get(fname)
        if val is None:
            if req:
                raise PlatformValidationError(
                    f"missing required field {fname!r}", code="SCHEMA_MISMATCH"
                )
            cleaned[fname] = None
            continue
        if ftype == "integer" and (isinstance(val, bool) or not isinstance(val, int)):
            raise PlatformValidationError(
                f"field {fname!r} expects integer", code="SCHEMA_MISMATCH"
            )
        if ftype == "number" and (isinstance(val, bool) or not isinstance(val, (int, float))):
            raise PlatformValidationError(f"field {fname!r} expects number", code="SCHEMA_MISMATCH")
        if ftype == "boolean" and not isinstance(val, bool):
            raise PlatformValidationError(
                f"field {fname!r} expects boolean", code="SCHEMA_MISMATCH"
            )
        if ftype == "text" and not isinstance(val, str):
            raise PlatformValidationError(f"field {fname!r} expects text", code="SCHEMA_MISMATCH")
        cleaned[fname] = val
    return cleaned
