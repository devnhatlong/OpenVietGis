"""Bounded native read encoding and controlled test fixture pins."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from struct import pack
from uuid import uuid4

import pytest

from openvietgis_api.adapters.persistence.spatial_fixtures import (
    derive_test_fixture_refresh,
    get_reference_fixture,
    materialize_reference_fixture,
)
from openvietgis_api.adapters.persistence.spatial_repository import _read_native_wkb
from openvietgis_api.domains.spatial.domain import (
    Extent,
    ExtentState,
    SpatialValidationError,
    ValidationState,
    validate_ready_geometry,
)
from openvietgis_api.domains.spatial.service import PinnedSource, verify_source_pins


def test_native_wkb_preserves_binary64_and_exact_shape() -> None:
    x, y = 106.12345678901234, 20.98765432109876
    point = _read_native_wkb(pack("<BIdd", 1, 1, x, y), 4326)
    assert point.coordinates == (x, y)
    assert point.srid == 4326
    line = _read_native_wkb(pack("<BIIdddd", 1, 2, 2, x, y, x + 1, y + 1), 4326)
    assert line.coordinates == ((x, y), (x + 1, y + 1))
    polygon = _read_native_wkb(
        pack("<BIIIdddddddd", 1, 3, 1, 4, x, y, x + 1, y, x, y + 1, x, y),
        4326,
    )
    assert polygon.coordinates == (((x, y), (x + 1, y), (x, y + 1), (x, y)),)
    for geometry in (point, line, polygon):
        assert validate_ready_geometry(geometry)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        pack("<BI", 0, 1),
        pack("<BII", 1, 2, 4097),
        pack("<BII", 1, 3, 1025),
        pack("<BIdd", 1, 1, float("nan"), 0.0),
        pack("<BIdd", 1, 1, 1.0, 2.0) + b"extra",
        pack("<BI", 1, 4),
    ],
)
def test_invalid_native_wkb_fails_closed(raw: bytes) -> None:
    with pytest.raises(SpatialValidationError):
        _read_native_wkb(raw, 4326)


def test_controlled_refresh_only_changes_one_pin() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    original = materialize_reference_fixture(
        "reference_points_5899",
        organization_id=uuid4(),
        project_id=uuid4(),
        source_id=uuid4(),
        name="Synthetic control",
        now=now,
    )
    fixture = get_reference_fixture("reference_points_5899")
    assert fixture is not None and fixture.expected_native_bounds is not None
    source = replace(
        original.source,
        validation_state=ValidationState.READY,
        validation_reason=None,
        extent_state=ExtentState.AVAILABLE,
        extent=Extent(*fixture.expected_native_bounds, 5899),
    )
    prior = PinnedSource(source, original.fields, original.features)
    verify_source_pins(prior.source, prior.fields, prior.features)
    changed = derive_test_fixture_refresh(prior, variant="content", now=now + timedelta(seconds=1))
    assert changed.source.catalog_revision == 2
    assert changed.source.content_revision != source.content_revision
    assert changed.source.schema_revision == source.schema_revision
    assert changed.features[0].attributes != prior.features[0].attributes
    assert [f.geometry for f in changed.features] == [f.geometry for f in prior.features]
    next_snapshot = derive_test_fixture_refresh(
        changed, variant="schema", now=now + timedelta(seconds=2)
    )
    assert next_snapshot.source.catalog_revision == 3
    assert next_snapshot.source.content_revision == changed.source.content_revision
    assert next_snapshot.source.schema_revision != changed.source.schema_revision
    assert [f.attributes for f in next_snapshot.features] == [
        f.attributes for f in changed.features
    ]
    verify_source_pins(next_snapshot.source, next_snapshot.fields, next_snapshot.features)
    with pytest.raises(SpatialValidationError):
        derive_test_fixture_refresh(next_snapshot, variant="arbitrary", now=now)
