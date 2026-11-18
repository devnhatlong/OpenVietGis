"""US3 logical feature serialization, independent of HTTP or PostGIS."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from openvietgis_api.domains.spatial.domain import (
    DataSource,
    Extent,
    ExtentState,
    FeatureCountState,
    FieldType,
    GeometryDimensions,
    GeometryFamily,
    GeometryState,
    Lifecycle,
    NativeGeometry,
    ReferenceFeature,
    SchemaState,
    SourceField,
    SourceKind,
    SpatialValidationError,
    ValidationState,
)
from openvietgis_api.domains.spatial.service import derive_source_pins, serialize_feature


def _pinned():
    now = datetime(2025, 1, 1, tzinfo=UTC)
    x, y = 106.12345678901234, 20.98765432109876
    source = DataSource(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        name="Synthetic",
        kind=SourceKind.REFERENCE_FIXTURE,
        reference_key="reference_point_4326",
        fixture_version="v1",
        manifest_digest="a" * 64,
        source_asset_id=None,
        lifecycle=Lifecycle.ACTIVE,
        validation_state=ValidationState.READY,
        validation_reason=None,
        source_crs=4326,
        stored_crs=4326,
        schema_state=SchemaState.KNOWN,
        geometry_family=GeometryFamily.POINT,
        dimensions=GeometryDimensions.XY,
        feature_count_state=FeatureCountState.KNOWN,
        feature_count=1,
        extent_state=ExtentState.AVAILABLE,
        extent=Extent(x, y, x, y, 4326),
        catalog_revision=1,
        content_revision="b" * 64,
        schema_revision="c" * 64,
        created_at=now,
        updated_at=now,
        retired_at=None,
    )
    values = (
        ("fld_text", FieldType.TEXT, False, ""),
        ("fld_int", FieldType.INTEGER, False, 0),
        ("fld_decimal", FieldType.DECIMAL, False, "123.4567890123456789"),
        ("fld_bool", FieldType.BOOLEAN, False, False),
        ("fld_time", FieldType.TIMESTAMP, False, "2025-01-01T00:00:00Z"),
        ("fld_null", FieldType.TEXT, True, None),
    )
    fields = tuple(
        SourceField(
            source.organization_id,
            source.project_id,
            source.id,
            key,
            key,
            index,
            kind,
            nullable,
            source.schema_revision,
        )
        for index, (key, kind, nullable, _) in enumerate(values)
    )
    feature = ReferenceFeature(
        source.organization_id,
        source.project_id,
        source.id,
        "feature_001",
        {key: value for key, _, _, value in values},
        NativeGeometry("Point", (x, y), 4326),
        GeometryState.PRESENT,
        source.content_revision,
        source.schema_revision,
    )
    return derive_source_pins(source, fields, (feature,))


def test_exact_logical_attributes_and_native_coordinate_precision() -> None:
    pinned = _pinned()
    feature = pinned.features[0]
    wire = serialize_feature(pinned.source, pinned.fields, feature, include_geometry=True)
    assert wire["feature_id"] == "feature_001"
    assert wire["attributes"] == dict(feature.attributes)
    assert type(wire["attributes"]["fld_int"]) is int
    assert type(wire["attributes"]["fld_bool"]) is bool
    assert wire["geometry_state"] == "present"
    assert wire["geometry"]["type"] == "Point"
    assert wire["geometry"]["coordinates"] == (106.12345678901234, 20.98765432109876)
    assert wire["geometry"]["coordinate_reference"]["code"] == 4326
    without = serialize_feature(pinned.source, pinned.fields, feature, include_geometry=False)
    assert without == {key: value for key, value in wire.items() if key != "geometry"}


@pytest.mark.parametrize(
    "bad",
    [
        {"fld_int": False},
        {"fld_decimal": "123.0"},
        {"fld_text": None},
        {"fld_extra": "unexpected"},
    ],
)
def test_corrupt_logical_attribute_fails_closed(bad: dict) -> None:
    pinned = _pinned()
    feature = pinned.features[0]
    corrupted = replace(feature, attributes=dict(feature.attributes) | bad)
    with pytest.raises(SpatialValidationError):
        serialize_feature(pinned.source, pinned.fields, corrupted, include_geometry=False)


def test_mismatched_snapshot_and_missing_attribute_fail_closed() -> None:
    pinned = _pinned()
    feature = pinned.features[0]
    removed = {key: value for key, value in feature.attributes.items() if key != "fld_null"}
    for corrupted in (
        replace(feature, content_revision="d" * 64),
        replace(feature, project_id=uuid4()),
        replace(feature, attributes=removed),
    ):
        with pytest.raises(SpatialValidationError):
            serialize_feature(pinned.source, pinned.fields, corrupted, include_geometry=True)
