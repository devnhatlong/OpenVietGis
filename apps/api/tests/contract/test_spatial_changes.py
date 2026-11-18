"""US4 change-history HTTP contract, before the history read implementation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.domains.spatial.domain import CatalogChange
from tests.contract.test_spatial_catalog import (
    BEARER,
    EDIT,
    HUMAN,
    ORG,
    PROJECT,
    READ,
    SERVICE,
    UNKNOWN,
    VALIDATION_ERROR,
    error,
    response_payload,
)
from tests.contract.test_spatial_catalog import DETAIL as SOURCE_DETAIL
from tests.contract.test_spatial_catalog import RETIRE as SOURCE_RETIRE
from tests.contract.test_spatial_catalog import url as source_url
from tests.contract.test_spatial_layers import (
    BASE as LAYER_BASE,
)
from tests.contract.test_spatial_layers import (
    RETIRE as LAYER_RETIRE,
)
from tests.contract.test_spatial_layers import LayerHTTP, layers  # noqa: F401
from tests.contract.test_spatial_layers import url as layer_url

BASE = "/organizations/{organization_id}/projects/{project_id}/spatial/changes"


def _url(*, org=ORG, project=PROJECT) -> str:
    return "/api/v1" + BASE.format(organization_id=org, project_id=project)


@pytest.fixture
def history(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    harness: LayerHTTP = request.getfixturevalue("layers")
    calls: list[tuple[UUID | None, int]] = []

    def list_changes(_self, *, context, after_id, limit):
        harness.repository._assert_scope(context)
        assert 1 <= limit <= 101
        calls.append((after_id, limit))
        return [
            change
            for change, _ in sorted(harness.repository.changes, key=lambda item: item[0].id)
            if after_id is None or change.id > after_id
        ][:limit]

    monkeypatch.setattr(SqlSpatialRepository, "list_changes", list_changes, raising=False)
    return harness, calls


def _page(harness: LayerHTTP, **params):
    return response_payload(harness.client.get(_url(), params=params), "GET", BASE, 200)


def _expected(change: CatalogChange) -> dict:
    return {
        "id": str(change.id),
        "organization_id": str(change.organization_id),
        "project_id": str(change.project_id),
        "resource_type": change.resource_type.value,
        "resource_id": str(change.resource_id),
        "actor_type": change.actor_type.value,
        "actor_id": str(change.actor_id),
        "actor_display_snapshot": change.actor_display_snapshot,
        "operation": change.operation.value,
        "created_at": change.created_at,
        "audit_event_id": str(change.audit_event_id),
        "prior_revision": change.prior_revision.to_wire() if change.prior_revision else None,
        "new_revision": change.new_revision.to_wire(),
        "changes": [value.to_wire() for value in change.changes],
    }


def test_empty_history_default_bound_and_current_scope(history) -> None:
    harness, calls = history
    assert _page(harness) == {
        "organization_id": str(ORG),
        "project_id": str(PROJECT),
        "items": [],
        "next_after_id": None,
    }
    harness.permission(READ, False)
    assert calls == [(None, 101)]


def test_history_preserves_actual_evidence_retirement_and_complete_keyset(history) -> None:
    harness, calls = history
    source_id = harness.register("reference_empty_4326", "Original")["resource_id"]
    layer_id = harness.create(source_id, "Original layer")["resource_id"]
    renamed = response_payload(
        harness.client.patch(
            source_url(SOURCE_DETAIL, source_id=source_id),
            json={"name": "Renamed source", "expected_revision": 1},
            headers=harness.csrf,
        ),
        "PATCH",
        SOURCE_DETAIL,
        200,
    )
    created_service = response_payload(
        harness.client.post(
            layer_url(),
            json={"source_id": source_id, "name": "Service layer"},
            headers={"Authorization": "Bearer " + BEARER},
        ),
        "POST",
        LAYER_BASE,
        201,
    )
    for target in (layer_id, created_service["resource_id"]):
        response_payload(
            harness.client.post(
                layer_url(LAYER_RETIRE, layer_id=target),
                json={"expected_revision": 1},
                headers=harness.csrf,
            ),
            "POST",
            LAYER_RETIRE,
            200,
        )
    retired = response_payload(
        harness.client.post(
            source_url(SOURCE_RETIRE, source_id=source_id),
            json={"expected_revision": 2},
            headers=harness.csrf,
        ),
        "POST",
        SOURCE_RETIRE,
        200,
    )
    assert harness.layer_list()["items"] == []
    expected = [
        _expected(change)
        for change, _ in sorted(harness.repository.changes, key=lambda pair: pair[0].id)
    ]
    assert len(expected) == 7
    seen = []
    cursor = None
    while True:
        page = _page(harness, limit=2, **({"after_id": cursor} if cursor else {}))
        assert (page["organization_id"], page["project_id"]) == (str(ORG), str(PROJECT))
        assert len(page["items"]) <= 2
        for item in page["items"]:
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            seen.append(item)
        cursor = page["next_after_id"]
        if cursor is None:
            break
        assert cursor == page["items"][-1]["id"]
    assert seen == expected
    assert len({item["id"] for item in seen}) == 7
    assert all(limit == 3 for _, limit in calls)
    by_id = {entry["id"]: entry for entry in seen}
    rename = by_id[renamed["change_id"]]
    assert rename["actor_id"] == str(HUMAN)
    assert rename["changes"] == [
        {"field": "catalog_revision", "old_value": 1, "new_value": 2},
        {"field": "name", "old_value": "Original", "new_value": "Renamed source"},
    ]
    assert by_id[created_service["change_id"]]["actor_id"] == str(SERVICE)
    assert by_id[retired["change_id"]]["operation"] == "retire_source"
    assert _page(harness, after_id=seen[-1]["id"])["items"] == []


def test_history_requires_read_permission_before_repository_and_reauthorizes(history) -> None:
    harness, calls = history
    harness.register("reference_empty_4326")
    assert _page(harness)["items"]
    calls.clear()
    harness.repository.human_permissions = {EDIT}
    harness.repository.service_permissions = {EDIT}
    for headers in ({}, {"Authorization": "Bearer " + BEARER}):
        error(harness.client.get(_url(), headers=headers), "GET", BASE, 403)
        for path in (_url(org=UNKNOWN), _url(project=UNKNOWN)):
            error(harness.client.get(path, headers=headers), "GET", BASE, 404)
    assert calls == []
    harness.repository.human_permissions = {READ}
    harness.repository.archived = True
    assert _page(harness)["items"]
    assert len(calls) == 1


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"after_id": "invalid-secret"}])
def test_invalid_history_queries_are_sanitized(history, params) -> None:
    harness, calls = history
    response = harness.client.get(_url(), params=params)
    assert response_payload(response, "GET", BASE, 422) == VALIDATION_ERROR
    assert calls == []
