"""US5 independent CRS/domain controls; no projection implementation as oracle."""

from __future__ import annotations

from itertools import product

import pytest

from openvietgis_api.domains.spatial import crs
from openvietgis_api.domains.spatial.domain import (
    GeometryDimensions,
    NativeGeometry,
    SpatialValidationError,
    validate_ready_geometry,
)
from tests.fixtures.spatial_controls import (
    CLOSED_REGION_BOUNDARIES,
    DIRECTED_CONTROL_SETS,
    OUT_OF_DOMAIN_CONTROLS,
    WEB_MERCATOR_MAX_COORDINATE_METRE,
    WEB_MERCATOR_OUTPUT_EPSILON_METRE,
)


def test_exact_registry_matches_independent_control_evidence() -> None:
    expected = {(edge.source_code, edge.target_code): edge for edge in DIRECTED_CONTROL_SETS}
    assert len(expected) == len(DIRECTED_CONTROL_SETS) == 8
    assert sum(len(edge.controls) for edge in expected.values()) == 44
    for source, target in product((4326, 3857, 4756, 5899, 3405, 3406, 0, 999999), repeat=2):
        actual = crs.get_transformation_profile(source, target)
        if (source, target) not in expected:
            assert actual is None
            continue
        control = expected[source, target]
        assert actual is not None
        assert actual.operation_id == control.operation_id
        assert actual.evidence_id == control.evidence_id
        assert actual.tolerance == control.tolerance
        assert actual.tolerance_unit == control.tolerance_unit
        assert actual.requires_trusted_fixture == bool({source, target} & {4756, 5899})
        assert all(
            item.source_xy != item.expected_xy
            for item in control.controls
            if item.point_id != "origin"
        )


@pytest.mark.parametrize("code", [True, 4326.0, "4326", None])
def test_no_coercion_of_crs_identity_or_edges(code) -> None:
    assert crs.get_crs_profile(code) is None
    assert crs.get_coordinate_reference(code) is None
    assert crs.get_transformation_profile(code, 3857) is None
    assert crs.get_transformation_profile(3857, code) is None


@pytest.mark.parametrize("region", CLOSED_REGION_BOUNDARIES, ids=lambda region: region.region_id)
def test_closed_operation_domain_has_no_input_epsilon(region) -> None:
    expected_edges = {
        "web-mercator": ((4326, 3857), (3857, 4326)),
        "quang-ninh-geographic": ((4326, 4756), (4756, 4326)),
        "quang-ninh-tm3": ((4326, 5899), (4756, 5899), (5899, 4326), (5899, 4756)),
    }
    for source, target in expected_edges[region.region_id]:
        edge = crs.get_transformation_profile(source, target)
        assert edge is not None
        assert all(edge.geographic_bounds.contains(*xy) for xy in region.inside)
        assert all(not edge.geographic_bounds.contains(*xy) for xy in region.outside)
        assert not edge.geographic_bounds.contains(float("inf"), region.min_y)
        assert not edge.geographic_bounds.contains(region.min_x, float("nan"))
        assert not edge.geographic_bounds.contains(True, region.min_y)
        assert not edge.geographic_bounds.contains(region.min_x, region.min_y, epsilon=-1.0)


@pytest.mark.parametrize("control", OUT_OF_DOMAIN_CONTROLS, ids=lambda control: control.control_id)
def test_distinguish_native_geometry_domain_from_operation_domain(control) -> None:
    if control.valid_native:
        geometry = NativeGeometry("Point", control.source_xy, control.source_code)
        assert validate_ready_geometry(geometry) == (control.source_xy,)
        edge = crs.get_transformation_profile(control.source_code, control.target_code)
        assert edge is not None
        # Projected TM-3 needs the approved inverse projection before checking
        # regional bounds. That explicit runtime check belongs to T053.
        if control.source_code != 5899:
            assert not edge.geographic_bounds.contains(*control.source_xy)
    else:
        with pytest.raises(SpatialValidationError):
            validate_ready_geometry(NativeGeometry("Point", control.source_xy, control.source_code))


@pytest.mark.parametrize(
    "family,coordinates,srid,dimensions",
    [
        ("Point", (107.15, 20.71, 2), 4756, GeometryDimensions.XYZ),
        ("Point", (107.15, 20.71, 2), 4756, GeometryDimensions.XYM),
        ("Point", (), 4756, GeometryDimensions.XY),
        ("Point", (20.71, 107.15), 4756, GeometryDimensions.XY),
        ("Point", (500000, 2000000), 3405, GeometryDimensions.XY),
        ("Point", (500000, 2000000), 3406, GeometryDimensions.XY),
        ("LineString", ((107.15, 20.71), (107.16, 91.0)), 4326, GeometryDimensions.XY),
        ("LineString", ((179, 10), (-179, 10)), 4326, GeometryDimensions.XY),
        ("Polygon", (((0, 0), (1, 0), (1, 91), (0, 0)),), 4326, GeometryDimensions.XY),
        ("MultiPoint", ((107.15, 20.71), (107.16, 20.71)), 4756, GeometryDimensions.XY),
    ],
)
def test_reject_unreadable_geometry_all_vertices(family, coordinates, srid, dimensions) -> None:
    with pytest.raises(SpatialValidationError):
        validate_ready_geometry(NativeGeometry(family, coordinates, srid, dimensions))


def test_web_mercator_output_roundoff_is_not_a_native_input_permit() -> None:
    profile = crs.get_readable_crs_profile(3857)
    assert profile is not None and profile.native_bounds is not None
    maximum = WEB_MERCATOR_MAX_COORDINATE_METRE
    outside = maximum + 1e-7
    assert profile.native_bounds.contains(maximum, -maximum)
    assert not profile.native_bounds.contains(outside, 0)
    assert profile.native_bounds.contains(outside, 0, epsilon=WEB_MERCATOR_OUTPUT_EPSILON_METRE)
    with pytest.raises(SpatialValidationError):
        validate_ready_geometry(NativeGeometry("Point", (outside, 0), 3857))
