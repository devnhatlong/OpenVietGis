from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import pytest

from openvietgis_api.adapters.formats.geopackage import write_geopackage
from openvietgis_api.adapters.formats.offline_snapshot import (
    embed_snapshot,
    extract_snapshot,
    validate_bbox,
    validate_offline_ops,
)
from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.spatial.domain import FieldType, NativeGeometry
from openvietgis_api.domains.transfers.domain import ExportFieldMapping


def sample_snapshot() -> dict:
    return {
        "organization_id": str(uuid4()),
        "project_id": str(uuid4()),
        "source_id": str(uuid4()),
        "schema_revision": "a" * 64,
        "geometry_family": "Point",
        "fields": [{"field_id": "value", "name": "Value", "type": "decimal", "nullable": False}],
        "features": [{"feature_id": "point1", "properties": {"value": "123456789.123456789"}}],
        "aoi_bbox": {"min_x": 105, "min_y": 20, "max_x": 106, "max_y": 21},
    }


def test_snapshot_projection_preserves_exact_precision_and_integrity() -> None:
    snapshot = sample_snapshot()
    original = snapshot["features"][0]["properties"]
    gpkg, _, _ = write_geopackage(
        layer_name="field_layer",
        crs_code=4326,
        geometry_family="Point",
        field_mappings=[ExportFieldMapping("value", "Value", "value", FieldType.DECIMAL)],
        features=[("point1", original, NativeGeometry("Point", (105.1, 20.1), 4326))],
    )
    compiled, digest = embed_snapshot(gpkg, snapshot)
    assert compiled.startswith(b"SQLite format 3\x00")
    payload = extract_snapshot(compiled, digest)
    assert hashlib.sha256(payload).hexdigest() == digest
    assert json.loads(payload) == snapshot
    with pytest.raises(PlatformValidationError, match="missing or invalid"):
        extract_snapshot(compiled, "0" * 64)
    with pytest.raises(PlatformValidationError, match="missing or invalid"):
        extract_snapshot(gpkg, digest)


def test_intent_must_use_issued_scope_and_canonical_value() -> None:
    s = sample_snapshot()
    update = {"op_type": "update", "feature_id": "point1", "properties": {"value": "12.5"}}
    create = {
        "op_type": "create",
        "feature_id": "point2",
        "properties": {"value": "0"},
        "geometry": {"type": "Point", "coordinates": [105.5, 20.5]},
    }
    validate_offline_ops(s, [update, create])
    bad = [
        {**update, "feature_id": "not-in-package"},
        {**update, "properties": {"value": "12.50"}},
        {**update, "properties": {"value": 12.5}},
        {**update, "properties": {"value": None}},
        {**update, "properties": {"unknown": "1"}},
        {**update, "geometry": create["geometry"]},
        {**update, "op_type": "delete"},
        {**create, "geometry": {"type": "Point", "coordinates": [107, 20.5]}},
    ]
    for operation in bad:
        with pytest.raises(PlatformValidationError):
            validate_offline_ops(s, [operation])
    with pytest.raises(PlatformValidationError):
        validate_offline_ops(s, [update, update])


def test_identified_operations_are_canonical_and_unique() -> None:
    s = sample_snapshot()
    operation_id = str(uuid4())
    update = {
        "op_type": "update",
        "feature_id": "point1",
        "properties": {"value": "12.5"},
        "client_operation_id": operation_id,
    }
    create = {
        "op_type": "create",
        "feature_id": "capture1",
        "geometry": {"type": "Point", "coordinates": [105.5, 20.5]},
        "properties": {"value": "0"},
        "client_operation_id": str(uuid4()),
    }
    validate_offline_ops(s, [update, create])
    for invalid in (
        None,
        "",
        "not-uuid",
        "00000000-0000-0000-0000-000000000000",
        "A" * 36,
        "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
    ):
        with pytest.raises(PlatformValidationError):
            validate_offline_ops(s, [{**update, "client_operation_id": invalid}])
    with pytest.raises(PlatformValidationError):
        validate_offline_ops(s, [update, {**create, "client_operation_id": operation_id}])
    for bad_label in (" draft", "bad/id", "a" * 129):
        with pytest.raises(PlatformValidationError):
            validate_offline_ops(s, [{**create, "feature_id": bad_label}])


def test_core_feature_identity_has_all_scope_dimensions() -> None:
    from openvietgis_api.domains.field.domain import offline_core_feature_id

    scope = {
        key: uuid4()
        for key in (
            "actor_id",
            "organization_id",
            "project_id",
            "package_id",
            "source_id",
            "client_operation_id",
        )
    }
    expected = offline_core_feature_id(**scope)
    assert expected.startswith("field-core-")
    assert offline_core_feature_id(**scope) == expected
    for key in scope:
        assert offline_core_feature_id(**{**scope, key: uuid4()}) != expected


def test_invalid_bounds_rejected() -> None:
    with pytest.raises(PlatformValidationError):
        validate_bbox({"min_x": 1, "min_y": 1, "max_x": 0, "max_y": 2})
    with pytest.raises(PlatformValidationError):
        validate_bbox({"min_x": float("nan"), "min_y": 1, "max_x": 2, "max_y": 2})
