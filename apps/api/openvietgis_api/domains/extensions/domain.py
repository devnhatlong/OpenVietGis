"""R014 Generic Internal Extension Framework domain (ADR-008: zero vertical knowledge)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import PlatformValidationError

_EXT_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,99}$")
_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SUPPORTED_API_RANGE = "1.x"
_SUPPORTED_FIELD_TYPES = {"text", "integer", "number", "boolean"}


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
    ui_contributions: list[dict[str, Any]]
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
    revision: int
    activated_by_actor_id: UUID
    activated_at: datetime
    disabled_by_actor_id: UUID | None
    disabled_at: datetime | None
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
    revision: int
    operation_id: UUID | None
    created_by_actor_id: UUID
    updated_by_actor_id: UUID
    created_at: datetime
    updated_at: datetime


def validate_manifest_contract(
    *,
    extension_key: str,
    version: str,
    api_compatibility: str,
    permissions: list[str],
    commands: list[dict[str, Any]],
    capabilities: list[str],
    entity_schemas: dict[str, dict[str, Any]],
    ui_contributions: list[dict[str, Any]],
) -> None:
    """Validate a versioned, namespaced and declarative extension manifest."""
    if not _EXT_KEY_RE.fullmatch(extension_key):
        raise PlatformValidationError(
            "extension_key must match ^[a-z][a-z0-9_-]{1,99}$",
            code="INVALID_EXTENSION_KEY",
        )
    if not _SEMVER_RE.fullmatch(version):
        raise PlatformValidationError("version must be semver X.Y.Z", code="INVALID_VERSION")
    if api_compatibility != _SUPPORTED_API_RANGE:
        raise PlatformValidationError(
            "unsupported api_compatibility "
            f"{api_compatibility!r}; expected {_SUPPORTED_API_RANGE!r}",
            code="INCOMPATIBLE_EXTENSION_API",
        )

    prefix = f"ext.{extension_key}."
    if len(set(permissions)) != len(permissions):
        raise PlatformValidationError("duplicate extension permission", code="INVALID_MANIFEST")
    for perm in permissions:
        if not isinstance(perm, str) or not perm.startswith(prefix) or len(perm) > 200:
            raise PlatformValidationError(
                f"permission {perm!r} must be namespaced under {prefix!r}",
                code="INVALID_PERMISSION_NAMESPACE",
            )

    command_ids: set[str] = set()
    for command in commands:
        if not isinstance(command, dict):
            raise PlatformValidationError("command must be an object", code="INVALID_MANIFEST")
        cid = command.get("id")
        label = command.get("label")
        required = command.get("required_permission")
        if (
            not isinstance(cid, str)
            or not _ID_RE.fullmatch(cid)
            or cid in command_ids
            or not isinstance(label, str)
            or not label.strip()
        ):
            raise PlatformValidationError(
                "invalid or duplicate command declaration", code="INVALID_MANIFEST"
            )
        if required is not None and required not in permissions:
            raise PlatformValidationError(
                f"command {cid!r} references undeclared permission",
                code="INVALID_MANIFEST",
            )
        command_ids.add(cid)

    if len(set(capabilities)) != len(capabilities):
        raise PlatformValidationError("duplicate extension capability", code="INVALID_MANIFEST")
    for capability in capabilities:
        if not isinstance(capability, str) or not _ID_RE.fullmatch(capability):
            raise PlatformValidationError("invalid extension capability", code="INVALID_MANIFEST")

    if not entity_schemas:
        raise PlatformValidationError(
            "manifest must declare at least one entity_schema", code="EMPTY_SCHEMAS"
        )
    for entity_name, schema in entity_schemas.items():
        if not _ID_RE.fullmatch(entity_name) or not isinstance(schema, dict):
            raise PlatformValidationError("invalid entity schema", code="INVALID_MANIFEST")
        fields = schema.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise PlatformValidationError("entity schema requires fields", code="INVALID_MANIFEST")
        for field_name, field_spec in fields.items():
            if (
                not _ID_RE.fullmatch(field_name)
                or not isinstance(field_spec, dict)
                or field_spec.get("type", "text") not in _SUPPORTED_FIELD_TYPES
                or ("required" in field_spec and not isinstance(field_spec["required"], bool))
            ):
                raise PlatformValidationError(
                    "invalid entity field declaration", code="INVALID_MANIFEST"
                )

    contribution_ids: set[str] = set()
    for contribution in ui_contributions:
        if not isinstance(contribution, dict):
            raise PlatformValidationError(
                "UI contribution must be an object", code="INVALID_MANIFEST"
            )
        cid = contribution.get("id")
        slot = contribution.get("slot")
        label = contribution.get("label")
        route_suffix = contribution.get("route_suffix")
        if (
            not isinstance(cid, str)
            or not _ID_RE.fullmatch(cid)
            or cid in contribution_ids
            or slot not in {"project_tool", "project_panel", "project_route"}
            or not isinstance(label, str)
            or not label.strip()
            or not isinstance(route_suffix, str)
            or not route_suffix.startswith("/")
            or ".." in route_suffix
        ):
            raise PlatformValidationError("invalid UI contribution", code="INVALID_MANIFEST")
        required = contribution.get("required_permission")
        if required is not None and required not in permissions:
            raise PlatformValidationError(
                f"UI contribution {cid!r} references undeclared permission",
                code="INVALID_MANIFEST",
            )
        contribution_ids.add(cid)


def validate_record_against_schema(
    *,
    entity_name: str,
    payload: dict[str, Any],
    entity_schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Validate an extension record payload strictly against declared fields."""
    schema = entity_schemas.get(entity_name)
    if schema is None:
        raise PlatformValidationError(
            f"unknown entity {entity_name!r} for this extension", code="UNKNOWN_ENTITY"
        )
    fields: dict[str, Any] = schema.get("fields", {})
    unknown = sorted(set(payload) - set(fields))
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
