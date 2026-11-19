"""Finite R004 render profile, independent from actor/lifecycle availability."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from openvietgis_api.adapters.persistence.spatial_fixtures import (
    get_reference_fixture,
    materialize_reference_fixture,
)
from openvietgis_api.domains.spatial.domain import (
    Extent,
    ExtentState,
    Layer,
    Lifecycle,
    ValidationState,
)
from openvietgis_api.domains.spatial.service import layer_capabilities, source_render_supported


def source(key):
    candidate = materialize_reference_fixture(
        key,
        organization_id=uuid4(),
        project_id=uuid4(),
        source_id=uuid4(),
        name="Render capability",
        now=datetime.now(UTC),
    ).source
    fixture = get_reference_fixture(key)
    assert fixture is not None
    extent = (
        Extent(*fixture.expected_native_bounds, fixture.stored_crs)
        if fixture.expected_native_bounds is not None
        else None
    )
    return replace(
        candidate,
        validation_state=ValidationState.READY,
        validation_reason=None,
        extent=extent,
        extent_state=ExtentState.AVAILABLE if extent else ExtentState.EMPTY,
    )


@pytest.mark.parametrize(
    "key",
    [
        "reference_points_4326",
        "reference_lines_4326",
        "reference_polygons_4326",
        "reference_points_3857",
        "reference_points_4756",
        "reference_points_4756_hvs",
        "reference_points_5899",
        "reference_empty_4326",
    ],
)
def test_supported_finite_profiles_have_explicit_permission_and_no_edit(key):
    value = source(key)
    assert source_render_supported(value)
    layer = Layer(
        uuid4(),
        value.organization_id,
        value.project_id,
        value.id,
        "Layer",
        Lifecycle.ACTIVE,
        1,
        value.created_at,
        value.updated_at,
        None,
    )
    flags = {cap.name: cap for cap in layer_capabilities(layer, value, actor_authorized=False)}
    for name in ("render", "style"):
        assert flags[name].technical_supported and flags[name].available
        assert flags[name].required_permission == "project.read"
        assert not flags[name].actor_authorized
    assert not flags["edit"].technical_supported


def test_latitude86_is_readable_but_never_advertised_as_renderable():
    value = source("reference_points_4326_webmerc_out_of_area")
    assert value.readable
    assert not source_render_supported(value)
