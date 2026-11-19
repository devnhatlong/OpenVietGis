from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from openvietgis_api.adapters.http.maps import SaveMapRequest, router


def payload():
    return {
        "operation_id": str(uuid4()),
        "expected_revision": 0,
        "layers": [],
        "basemap": "grid",
        "default_viewpoint": {"mode": "preserve"},
    }


def test_map_routes_have_stable_distinct_operation_ids():
    assert {route.operation_id for route in router.routes} == {
        "getMap",
        "saveMap",
        "getMapOperation",
        "listMapHistory",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_revision", True),
        ("expected_revision", 1.5),
        ("expected_revision", -1),
        ("expected_revision", 2**53),
        ("operation_id", 2),
        ("basemap", "https://external.example/secret"),
        ("default_viewpoint", {"mode": "preserve", "value": None}),
        ("default_viewpoint", {"mode": "set"}),
        ("default_viewpoint", {"mode": "clear", "pitch": 8}),
        ("private_renderer_handle", "tenant-secret"),
    ],
)
def test_save_payload_closed_shape_and_semantic_bounds(field, value):
    body = payload()
    body[field] = value
    with pytest.raises(ValidationError):
        SaveMapRequest.model_validate(body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("longitude", True),
        ("latitude", 86),
        ("pitch", 90),
        ("zoom", 23),
        ("crs", "4326"),
        ("crs", 4326.0),
        ("crs", 3857),
        ("longitude", float("nan")),
    ],
)
def test_designated_viewpoint_must_have_valid_explicit_geographic_semantics(field, value):
    body = payload()
    view = {"longitude": 106, "latitude": 11, "zoom": 10, "bearing": 0, "pitch": 0, "crs": 4326}
    view[field] = value
    body["default_viewpoint"] = {"mode": "set", "value": view}
    with pytest.raises(ValidationError):
        SaveMapRequest.model_validate(body)


def test_layer_reference_cannot_carry_unbounded_style_or_duplicate_identity():
    body = payload()
    layer = {
        "layer_id": str(uuid4()),
        "visible": True,
        "style": {"color": "#ff6600", "opacity": 0.8, "width": 2, "radius": 5},
    }
    body["layers"] = [layer, deepcopy(layer)]
    with pytest.raises(ValidationError):
        SaveMapRequest.model_validate(body)
    body["layers"] = [layer]
    layer["style"]["expression"] = "private data"
    with pytest.raises(ValidationError):
        SaveMapRequest.model_validate(body)


def test_numeric_json_spelling_has_equivalent_canonical_intent():
    first = payload()
    first["layers"] = [
        {
            "layer_id": str(uuid4()),
            "visible": True,
            "style": {"color": "#ff6600", "opacity": 1, "width": 2, "radius": 5},
        }
    ]
    second = deepcopy(first)
    second["layers"][0]["style"].update(
        {"color": "#FF6600", "opacity": 1.0, "width": 2.0, "radius": 5.0}
    )
    assert (
        SaveMapRequest.model_validate(first).domain().fingerprint
        == SaveMapRequest.model_validate(second).domain().fingerprint
    )
