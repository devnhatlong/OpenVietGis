"""US5 contract-first test for scoped CRS discovery; use the actual ASGI adapter."""

from __future__ import annotations

import pytest

from tests.contract.test_spatial_catalog import (
    BEARER,
    EDIT,
    ORG,
    PROJECT,
    READ,
    UNKNOWN,
    CatalogHTTP,
    catalog,  # noqa: F401
    error,
    response_payload,
)
from tests.fixtures.spatial_controls import DIRECTED_CONTROL_SETS


@pytest.fixture
def harness(request: pytest.FixtureRequest) -> CatalogHTTP:
    return request.getfixturevalue("catalog")


BASE = "/organizations/{organization_id}/projects/{project_id}/spatial/crs-profiles"


def _url(*, org=ORG, project=PROJECT) -> str:
    return "/api/v1" + BASE.format(organization_id=org, project_id=project)


def test_crs_discovery_exact_finite_registry_and_current_read(harness: CatalogHTTP) -> None:
    repo = harness.repository
    repo.human_permissions = {READ}
    repo.service_permissions = {READ}
    body = response_payload(harness.client.get(_url()), "GET", BASE, 200)
    harness.permission(READ, False)
    assert set(body) == {"organization_id", "project_id", "profiles", "transformations"}
    assert body["organization_id"] == str(ORG)
    assert body["project_id"] == str(PROJECT)
    profiles = {item["code"]: item for item in body["profiles"]}
    assert len(profiles) == len(body["profiles"]) == 6
    assert set(profiles) == {4326, 3857, 4756, 5899, 3405, 3406}
    for code, item in profiles.items():
        assert item["authority"] == "EPSG"
        assert item["coordinate_order"] == "xy"
        assert item["native_axes"] == (
            ["latitude", "longitude"] if code in (4326, 4756) else ["easting", "northing"]
        )
        assert item["disposition"] == ("definition_only" if code in (3405, 3406) else "readable")
    actual = {(edge["source_code"], edge["target_code"]): edge for edge in body["transformations"]}
    assert len(actual) == len(body["transformations"]) == len(DIRECTED_CONTROL_SETS) == 8
    for control in DIRECTED_CONTROL_SETS:
        operation = actual[control.source_code, control.target_code]
        assert operation["operation_id"] == control.operation_id
        assert operation["evidence_id"] == control.evidence_id
        assert operation["tolerance"] == control.tolerance
        assert operation["tolerance_unit"] == control.tolerance_unit
        assert "pipeline" not in operation and "steps" not in operation
    repo.archived = True
    assert response_payload(harness.client.get(_url()), "GET", BASE, 200) == body
    assert (
        response_payload(
            harness.client.get(_url(), headers={"Authorization": "Bearer " + BEARER}),
            "GET",
            BASE,
            200,
        )
        == body
    )
    harness.permission(READ, False)
    assert not repo.lookups


def test_crs_discovery_does_not_bypass_current_access_or_scope(harness: CatalogHTTP) -> None:
    repo = harness.repository
    response_payload(harness.client.get(_url()), "GET", BASE, 200)
    repo.human_permissions = {EDIT}
    repo.service_permissions = {EDIT}
    for headers in ({}, {"Authorization": "Bearer " + BEARER}):
        error(harness.client.get(_url(), headers=headers), "GET", BASE, 403)
        error(harness.client.get(_url(project=UNKNOWN), headers=headers), "GET", BASE, 404)
        if not headers:
            error(harness.client.get(_url(org=UNKNOWN), headers=headers), "GET", BASE, 404)
    assert not repo.lookups
