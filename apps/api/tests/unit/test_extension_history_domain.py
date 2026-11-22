"""R014 portable semantics are bounded and metadata transitions opt in explicitly."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from openvietgis_api.domains.extensions.domain import (
    ExtensionManifestRecord,
    bundle_digest,
    canonical_bytes,
    validate_manifest_contract,
    validate_record_against_schema,
    validate_stored_manifest_for_mutation,
    verify_transition,
)
from openvietgis_api.domains.platform_errors import PlatformConflictError, PlatformValidationError

SCHEMA = {
    "thing": {
        "fields": {
            "name": {"type": "text", "required": True},
            "value": {"type": "number"},
            "count": {"type": "integer"},
            "flag": {"type": "boolean"},
        }
    }
}


def sample() -> ExtensionManifestRecord:
    return ExtensionManifestRecord(
        id=uuid4(),
        organization_id=uuid4(),
        extension_key="example_extension",
        version="1.0.0",
        api_compatibility="1.x",
        display_name="Example",
        description="",
        permissions=["ext.example_extension.read"],
        commands=[
            {"id": "read", "label": "Read", "required_permission": "ext.example_extension.read"}
        ],
        capabilities=["record_list"],
        entity_schemas=SCHEMA,
        enabled=True,
        registered_by_actor_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def test_schema_typed_nullable_and_finite():
    assert validate_record_against_schema(
        entity_name="thing",
        payload={"name": "Địa chỉ", "value": 1.75, "count": 0, "flag": False},
        entity_schemas=SCHEMA,
    ) == {"name": "Địa chỉ", "value": 1.75, "count": 0, "flag": False}
    assert validate_record_against_schema(
        entity_name="thing",
        payload={"name": "x"},
        entity_schemas=SCHEMA,
    ) == {"name": "x", "value": None, "count": None, "flag": None}


@pytest.mark.parametrize(
    "bad",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": 1e20},
        {"count": True},
        {"count": 9007199254740992},
        {"flag": "false"},
        {"name": "\0"},
        {"unknown": 1},
    ],
)
def test_invalid_portable_attribute(bad):
    with pytest.raises(PlatformValidationError):
        validate_record_against_schema(
            entity_name="thing", payload={"name": "x", **bad}, entity_schemas=SCHEMA
        )


def test_canonical_digest_preserves_semantic_numbers_and_unicode():
    assert bundle_digest({"a": 12.0, "b": False, "text": "Hà Nội"}) == bundle_digest(
        {
            "text": "Hà Nội",
            "b": False,
            "a": 12,
        }
    )
    assert bundle_digest({"a": False}) != bundle_digest({"a": 0})
    with pytest.raises(PlatformValidationError):
        canonical_bytes({"unsafe": 10**1000})
    with pytest.raises(PlatformValidationError):
        canonical_bytes({"table": "x" * 100}, limit=20)


def test_metadata_only_version_transition_checks_effective_contract():
    old = sample()
    verify_transition(old, replace(old, id=uuid4(), version="1.1.0", display_name="Changed label"))
    for bad in [
        replace(old, version="2.0.0"),
        replace(old, version="0.9.0"),
        old,
        replace(old, version="1.1.0", permissions=["ext.example_extension.extra"]),
        replace(
            old, version="1.1.0", entity_schemas={"other": {"fields": {"name": {"type": "text"}}}}
        ),
        replace(old, version="1.1.0", enabled=False),
    ]:
        with pytest.raises(PlatformConflictError):
            verify_transition(old, bad)


def test_manifest_does_not_accept_executable_or_conflicting_contributions():
    old = sample()
    args = dict(
        extension_key=old.extension_key,
        version=old.version,
        api_compatibility=old.api_compatibility,
        permissions=old.permissions,
        entity_schemas=old.entity_schemas,
        commands=old.commands,
        capabilities=old.capabilities,
    )
    validate_manifest_contract(**args)
    for change in [
        {"version": "01.0.0"},
        {"permissions": old.permissions * 2},
        {"commands": old.commands * 2},
        {"commands": [{**old.commands[0], "script": "arbitrary"}]},
        {"commands": [{**old.commands[0], "required_permission": "project.manage"}]},
        {"entity_schemas": {"thing": {"fields": {"x": {"type": "binary"}}}}},
        {"capabilities": ["record_list", "record_list"]},
    ]:
        with pytest.raises(PlatformValidationError):
            validate_manifest_contract(**{**args, **change})


def test_retained_legacy_manifest_requires_revalidation_for_mutation():
    current = sample()
    validate_stored_manifest_for_mutation(current)
    legacy = replace(current, commands=[{"id": "read", "label": "Read"}])
    for bad in (
        legacy,
        replace(current, commands=[{**current.commands[0], "script": "untrusted"}]),
        replace(current, permissions=["project.manage"]),
        replace(current, version="legacy"),
    ):
        with pytest.raises(PlatformConflictError) as error:
            validate_stored_manifest_for_mutation(bad)
        assert error.value.code == "EXTENSION_MANIFEST_REVALIDATION_REQUIRED"
