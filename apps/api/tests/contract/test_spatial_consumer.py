"""API-only independent consumer for SC-003/SC-008.

This consumer knows public routes, the frozen wire contract and synthetic test
controls, not the server's fixture implementation, persistence or R004. The
same function runs against the ASGI contract harness and restricted PostGIS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from tests.contract.test_spatial_catalog import ORG, PROJECT, response_payload
from tests.contract.test_spatial_features import (
    FeatureHTTP,
    feature_http,  # noqa: F401
)

PROJECT_PATH = "/organizations/{organization_id}/projects/{project_id}"
SOURCES = PROJECT_PATH + "/spatial/sources"
SOURCE = SOURCES + "/{source_id}"
LAYERS = PROJECT_PATH + "/layers"
LAYER = LAYERS + "/{layer_id}"
PAGE = LAYER + "/features"
DETAIL = PAGE + "/{feature_id}"

CHOSEN_LAYER = "Consumer-selected reference"
EXPECTED_FIELDS = {
    "fld_feature_code": ("text", False),
    "fld_name": ("text", False),
    "fld_rank": ("integer", False),
    "fld_measure": ("decimal", True),
    "fld_active": ("boolean", False),
    "fld_observed_at": ("timestamp", True),
    "fld_note": ("text", True),
}


def _walk_catalog(client: TestClient, template: str, scope: dict[str, str]) -> list[dict]:
    result: list[dict] = []
    cursor = None
    # This independent consumer follows only server-supplied public cursors.
    # Bound the walk and verify strict advancement to avoid endless retries.
    for _ in range(10):
        params = {"limit": 1}
        if cursor is not None:
            params["after_id"] = cursor
        page = response_payload(
            client.get("/api/v1" + template.format(**scope), params=params),
            "GET",
            template,
            200,
        )
        assert len(page["items"]) <= 1
        for item in page["items"]:
            assert cursor is None or UUID(item["id"]) > UUID(cursor)
            result.append(item)
        cursor = page["next_after_id"]
        if cursor is None:
            return result
        assert page["items"] and cursor == page["items"][-1]["id"]
    raise AssertionError("catalog cursor did not terminate")


def _assert_typed_attributes(attributes: dict, fields: dict[str, tuple[str, bool]]) -> None:
    assert set(attributes) == set(fields)
    for field_id, (kind, nullable) in fields.items():
        value = attributes[field_id]
        if value is None:
            assert nullable
        elif kind == "integer":
            assert type(value) is int and -(2**31) <= value < 2**31
        elif kind == "boolean":
            assert type(value) is bool
        elif kind == "text":
            assert type(value) is str
        elif kind == "decimal":
            assert type(value) is str and Decimal(value).is_finite()
            assert not ("e" in value.lower() or value == "-0")
            assert "." not in value or not value.endswith("0")
        elif kind == "timestamp":
            assert type(value) is str and value.endswith("Z")
            assert datetime.fromisoformat(value).tzinfo == UTC
        else:
            raise AssertionError(f"unsupported public field type: {kind}")


def exercise_consumer(
    client: TestClient,
    organization_id: UUID,
    project_id: UUID,
    *,
    csrf: dict[str, str] | None = None,
) -> None:
    scope = {"organization_id": str(organization_id), "project_id": str(project_id)}

    # Fixture setup itself uses only public HTTP. Neither created resource ID is
    # passed to the consumer's later discovery: it starts with the Project scope.
    for key, source_name, layer_name in (
        ("reference_empty_4326", "Empty distractor", "Other layer"),
        ("reference_points_4326", "Point reference", CHOSEN_LAYER),
    ):
        registered = response_payload(
            client.post(
                "/api/v1" + SOURCES.format(**scope),
                json={"reference_key": key, "name": source_name},
                headers=csrf,
            ),
            "POST",
            SOURCES,
            201,
        )
        assert registered["validation_state"] == "ready"
        response_payload(
            client.post(
                "/api/v1" + LAYERS.format(**scope),
                json={"source_id": registered["resource_id"], "name": layer_name},
                headers=csrf,
            ),
            "POST",
            LAYERS,
            201,
        )

    layers = _walk_catalog(client, LAYERS, scope)
    sources = _walk_catalog(client, SOURCES, scope)
    assert len(layers) == len(sources) == 2
    selected = next(layer for layer in layers if layer["name"] == CHOSEN_LAYER)
    detail_scope = scope | {"layer_id": selected["id"]}
    layer = response_payload(
        client.get("/api/v1" + LAYER.format(**detail_scope)), "GET", LAYER, 200
    )
    assert layer == selected
    source = response_payload(
        client.get("/api/v1" + SOURCE.format(**scope, source_id=layer["source_id"])),
        "GET",
        SOURCE,
        200,
    )
    assert source == layer["source"]
    assert source == next(item for item in sources if item["id"] == source["id"])
    assert source["validation_state"] == "ready"
    assert source["feature_count_state"] == "known" and source["feature_count"] == 4000
    assert source["extent_state"] == "available"
    capabilities = {item["name"]: item for item in layer["capabilities"]}
    assert {
        name
        for name, item in capabilities.items()
        if item["available"] and item["actor_authorized"]
    } == {
        "metadata_read",
        "feature_read",
        "render",
        "style",
        "export",
        "query",
        "analysis",
        "offline",
    }

    schema = source["schema"]
    assert schema["state"] == "known" and schema["schema_revision"] == source["schema_revision"]
    assert (schema["geometry_family"], schema["dimensions"]) == ("Point", "XY")
    # Never derive identity from display name or field order.
    fields = {field["field_id"]: (field["type"], field["nullable"]) for field in schema["fields"]}
    assert fields == EXPECTED_FIELDS
    pins = {name: source[name] for name in ("content_revision", "schema_revision")}
    crs = source["stored_crs"]["code"]
    assert crs == 4326

    records: dict[str, dict[Any, Any]] = {}
    read_context = None
    cursor = None
    # Choose a page length not dividing 4,000 to exercise short terminal page.
    for _ in range(42):
        params = pins | {"limit": 97, "response_crs": crs}
        if cursor is not None:
            params["after_feature_id"] = cursor
        page = response_payload(
            client.get("/api/v1" + PAGE.format(**detail_scope), params=params),
            "GET",
            PAGE,
            200,
        )
        context = page["context"]
        if read_context is None:
            read_context = context
            assert context == {
                **detail_scope,
                "source_id": source["id"],
                **pins,
                "geometry_included": True,
                "response_crs": {
                    key: source["stored_crs"][key]
                    for key in ("authority", "code", "coordinate_order", "x_axis", "y_axis", "unit")
                },
                "transformation": None,
            }
        assert read_context == context
        assert len(page["items"]) <= 97
        previous = cursor
        for feature in page["items"]:
            feature_id = feature["feature_id"]
            assert feature_id not in records
            assert previous is None or previous < feature_id
            previous = feature_id
            _assert_typed_attributes(feature["attributes"], fields)
            assert feature["geometry_state"] == "present"
            assert feature["geometry"]["type"] == "Point"
            assert feature["geometry"]["coordinate_reference"] == context["response_crs"]
            records[feature_id] = feature
        cursor = page["next_after_feature_id"]
        if cursor is None:
            break
        assert len(page["items"]) == 97 and cursor == previous
    else:
        raise AssertionError("feature keyset cursor did not terminate")
    assert list(records) == [f"point-{number:06d}" for number in range(1, 4001)]

    # Frozen, independent wire expectations: preserve zero, empty string,
    # explicit null and typed boolean/decimal/timestamp, not inferred values.
    assert records["point-000001"]["attributes"] == {
        "fld_feature_code": "point-000001",
        "fld_name": "Point 000001",
        "fld_rank": 1,
        "fld_measure": "0",
        "fld_active": False,
        "fld_observed_at": "2025-01-01T00:00:00Z",
        "fld_note": "",
    }
    assert records["point-000002"]["attributes"]["fld_measure"] == "-0.37"
    assert records["point-000005"]["attributes"]["fld_note"] is None
    assert records["point-000007"]["attributes"]["fld_measure"] is None
    chosen = "point-000011"
    assert records[chosen]["attributes"] == {
        "fld_feature_code": chosen,
        "fld_name": "Point 000011",
        "fld_rank": 11,
        "fld_measure": "3.7",
        "fld_active": False,
        "fld_observed_at": None,
        "fld_note": "",
    }
    assert records[chosen]["geometry"]["coordinates"] == [106.61, 10.7]
    detail_url = "/api/v1" + DETAIL.format(**detail_scope, feature_id=chosen)
    feature = response_payload(
        client.get(detail_url, params=pins | {"response_crs": crs}),
        "GET",
        DETAIL,
        200,
    )
    assert feature == {"context": read_context, "feature": records[chosen]}

    # Incompatible tokens are domain conflicts, not an alternative feature.
    # Actual committed incompatible refreshes are exercised separately in T036.
    for name, token in pins.items():
        wrong = ("0" if token[0] != "0" else "1") + token[1:]
        stale = response_payload(
            client.get(detail_url, params=pins | {name: wrong}), "GET", DETAIL, 409
        )
        assert stale["code"] == "STALE_READ_PIN"
        assert set(stale) == {"code", "detail"}


def test_independent_contract_consumer(feature_http: FeatureHTTP) -> None:  # noqa: F811
    exercise_consumer(feature_http.client, ORG, PROJECT, csrf=feature_http.csrf)
