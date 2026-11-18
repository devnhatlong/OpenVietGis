"""US4 CatalogChange acceptance through actual restricted-runtime HTTP and SQL.

Only the project-scoped HTTP API makes product changes. Administrative queries
observe committed evidence and real lock waits; runtime SQL verifies immutable
grants against a real change row. No mocked history, mutation or transaction.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from openvietgis_api.adapters.persistence.db import get_engine
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.domains.spatial.domain import CatalogOperation
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import AccessWorld, seed_access_world
from tests.integration.service_identity.test_service_authorization import (
    _issue_manager_credential,
    _service_client,
)
from tests.integration.spatial.test_layers import (
    _counts,
    _create,
    _detail,
    _mutated,
    _wait_for_blocked_runtime_query,
)
from tests.integration.spatial.test_layers import _path as _layer_path
from tests.integration.spatial.test_migration_rls import _assert_denied, _bind
from tests.integration.spatial.test_sources import (
    _changes,
    _client,
    _error,
    _get,
    _metadata,
    _register,
    _rows,
)
from tests.integration.spatial.test_sources import _path as _source_path

CHANGE_KEYS = {
    "id",
    "organization_id",
    "project_id",
    "resource_type",
    "resource_id",
    "actor_type",
    "actor_id",
    "actor_display_snapshot",
    "operation",
    "created_at",
    "audit_event_id",
    "prior_revision",
    "new_revision",
    "changes",
}


def _change_path(world: AccessWorld, project: UUID | None = None) -> str:
    return (
        f"/api/v1/organizations/{world.organization_id}/projects/"
        f"{project or world.project_id}/spatial/changes"
    )


def _page(client: TestClient, world: AccessWorld, *, project: UUID | None = None, **params):
    response = client.get(_change_path(world, project), params=params)
    assert response.status_code == 200, response.text
    page = response.json()
    assert set(page) == {"organization_id", "project_id", "items", "next_after_id"}
    assert page["organization_id"] == str(world.organization_id)
    assert page["project_id"] == str(project or world.project_id)
    items = page["items"]
    assert len(items) <= params.get("limit", 100)
    ids = [UUID(item["id"]) for item in items]
    assert ids == sorted(set(ids))
    if "after_id" in params:
        assert all(item > UUID(params["after_id"]) for item in ids)
    if page["next_after_id"] is not None:
        assert items
        assert len(items) == params.get("limit", 100)
        assert page["next_after_id"] == items[-1]["id"]
    return page


def _all_changes(client: TestClient, world: AccessWorld, *, limit: int = 100):
    items = []
    params = {"limit": limit}
    while True:
        page = _page(client, world, **params)
        items.extend(page["items"])
        if page["next_after_id"] is None:
            break
        params["after_id"] = page["next_after_id"]
        assert len(items) <= 100, "fixture history should terminate"
    ids = [UUID(item["id"]) for item in items]
    assert ids == sorted(set(ids))
    return items


def _assert_change(
    world: AccessWorld,
    item,
    mutation,
    operation: str,
    expected_diff,
    *,
    actor_id: UUID | None = None,
    actor_type: str = "human",
    display_name: str = "Owner",
) -> None:
    """Check the public item, independent expected diff and committed audit join."""
    actor_id = actor_id or world.owner_user_id
    assert set(item) == CHANGE_KEYS
    assert item["id"] == mutation["change_id"]
    assert item["organization_id"] == mutation["organization_id"] == str(world.organization_id)
    assert item["project_id"] == mutation["project_id"] == str(world.project_id)
    assert item["resource_type"] == mutation["resource_type"]
    assert item["resource_id"] == mutation["resource_id"]
    assert item["actor_type"] == actor_type
    assert item["actor_id"] == str(actor_id)
    assert item["actor_display_snapshot"] == display_name
    assert item["operation"] == operation
    assert item["prior_revision"] == mutation["prior_revision"]
    assert item["new_revision"] == mutation["new_revision"]
    created_at = datetime.fromisoformat(item["created_at"])
    assert created_at.utcoffset() == timedelta(0)
    audit_id = UUID(item["audit_event_id"])
    changes = item["changes"]
    assert 1 <= len(changes) <= 100
    assert len({change["field"] for change in changes}) == len(changes)
    for change in changes:
        assert set(change) == {"field", "old_value", "new_value"}
        old, new = change["old_value"], change["new_value"]
        assert type(old) in (str, int, float, bool, type(None))
        assert type(new) in (str, int, float, bool, type(None))
        assert old != new or type(old) is not type(new)
    assert {
        change["field"]: (change["old_value"], change["new_value"]) for change in changes
    } == expected_diff

    with get_admin_engine().begin() as connection:
        row = (
            connection.execute(
                text("""
                SELECT c.actor_type,c.actor_id,c.actor_display_snapshot,c.created_at,
                       c.resource_type,c.resource_id,c.source_id,c.layer_id,
                       c.operation,c.prior_revision,c.new_revision,c.changes,c.audit_event_id,
                       a.actor_type AS audit_actor_type,a.actor_id AS audit_actor_id,
                       a.actor_display_snapshot AS audit_display,a.created_at AS audit_time,
                       a.resource_type AS audit_resource_type,a.resource_id AS audit_resource_id,
                       a.action,a.outcome,a.metadata
                FROM spatial.catalog_changes c JOIN audit.audit_events a
                  ON a.organization_id=c.organization_id AND a.id=c.audit_event_id
                WHERE c.organization_id=:org AND c.project_id=:project AND c.id=:id
            """),
                {
                    "org": world.organization_id,
                    "project": world.project_id,
                    "id": item["id"],
                },
            )
            .mappings()
            .one()
        )
    assert row["actor_type"] == row["audit_actor_type"] == actor_type
    assert row["actor_id"] == row["audit_actor_id"] == actor_id
    assert row["actor_display_snapshot"] == row["audit_display"] == display_name
    assert row["created_at"] == row["audit_time"] == created_at
    assert row["resource_type"] == row["audit_resource_type"] == item["resource_type"]
    assert row["resource_id"] == row["audit_resource_id"] == UUID(item["resource_id"])
    # Internal constrained reference columns must never enter the public wire.
    if item["resource_type"] == "data_source":
        assert row["source_id"] == row["resource_id"] and row["layer_id"] is None
    else:
        assert row["layer_id"] == row["resource_id"] and row["source_id"] is None
    assert row["operation"] == operation
    assert row["prior_revision"] == item["prior_revision"]
    assert row["new_revision"] == item["new_revision"]
    assert row["changes"] == changes
    assert row["audit_event_id"] == audit_id
    assert row["action"] == f"spatial.catalog.{operation}" and row["outcome"] == "success"
    assert row["metadata"] == {
        "project_id": str(world.project_id),
        "catalog_change_id": item["id"],
    }


def _correct(client: TestClient, path: str):
    return client.patch(
        path,
        json={
            "expected_revision": 1,
            "declared_crs": {"authority": "EPSG", "code": 4326, "coordinate_order": "xy"},
        },
    )


def _correction_diff(prior, current):
    return {
        "catalog_revision": (1, 2),
        "source_crs": (3857, 4326),
        "validation_state": (prior["validation_state"], "ready"),
        "validation_reason.code": ("CRS_MISMATCH", None),
        "validation_reason.message": (prior["validation_reason"]["message"], None),
        "extent_state": ("unavailable", "available"),
        "content_revision": (prior["content_revision"], current["content_revision"]),
    }


def test_project_history_exact_wire_values_keyset_and_retired_records(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    source_path, layer_path = _source_path(world), _layer_path(world)
    with _client(world.owner_user_id) as client:
        assert _page(client, world)["items"] == []
        assert _page(client, world)["next_after_id"] is None
        registered = _register(client, source_path, "reference_correctable_crs")
        source_id = registered["resource_id"]
        path = f"{source_path}/{source_id}"
        original = _get(client, source_path, source_id)
        _metadata(world, original, registered, "reference_correctable_crs", "Point", "XY")
        register_diff = _changes(world, registered, "register_source")
        native = _rows(source_id)

        response = _correct(client, path)
        assert response.status_code == 200, response.text
        corrected = response.json()
        source = _get(client, source_path, source_id)
        assert corrected["prior_revision"] == registered["new_revision"]
        assert corrected["new_revision"]["schema_revision"] == original["schema_revision"]
        assert corrected["new_revision"]["content_revision"] != original["content_revision"]
        assert source["validation_state"] == "ready"
        corrected_native = _rows(source_id)
        assert corrected_native[0]["ewkb"] == native[0]["ewkb"]
        assert corrected_native[0]["attributes"] == native[0]["attributes"]
        correction_diff = _correction_diff(original, source)

        response = client.patch(path, json={"expected_revision": 2, "name": "Current source"})
        assert response.status_code == 200, response.text
        renamed_source = response.json()
        assert renamed_source["prior_revision"] == corrected["new_revision"]
        assert renamed_source["new_revision"] == {
            **corrected["new_revision"],
            "catalog_revision": 3,
        }
        created_layer = _create(client, world, source_id, "Initial layer")
        layer_id = created_layer["resource_id"]
        layer = f"{layer_path}/{layer_id}"
        renamed_layer = _mutated(
            client.patch(layer, json={"expected_revision": 1, "name": "Current layer"}),
            world,
            status=200,
            prior=1,
            revision=2,
        )
        retired_layer = _mutated(
            client.post(f"{layer}/retire", json={"expected_revision": 2}),
            world,
            status=200,
            prior=2,
            revision=3,
            lifecycle="retired",
        )
        response = client.post(f"{path}/retire", json={"expected_revision": 3})
        assert response.status_code == 200, response.text
        retired_source = response.json()
        assert retired_source["lifecycle"] == "retired"
        assert retired_source["prior_revision"] == renamed_source["new_revision"]
        assert retired_source["new_revision"] == {
            **renamed_source["new_revision"],
            "catalog_revision": 4,
        }
        assert client.get(path).status_code == client.get(layer).status_code == 404
        assert _rows(source_id) == corrected_native

        expected = (
            (registered, "register_source", register_diff),
            (corrected, "correct_source_crs", correction_diff),
            (
                renamed_source,
                "update_source",
                {"name": ("Reference", "Current source"), "catalog_revision": (2, 3)},
            ),
            (
                created_layer,
                "create_layer",
                {
                    "name": (None, "Initial layer"),
                    "source_id": (None, source_id),
                    "lifecycle": (None, "active"),
                    "layer_revision": (None, 1),
                },
            ),
            (
                renamed_layer,
                "rename_layer",
                {"name": ("Initial layer", "Current layer"), "layer_revision": (1, 2)},
            ),
            (
                retired_layer,
                "retire_layer",
                {"lifecycle": ("active", "retired"), "layer_revision": (2, 3)},
            ),
            (
                retired_source,
                "retire_source",
                {"lifecycle": ("active", "retired"), "catalog_revision": (3, 4)},
            ),
        )
        # Same-organization, independently authorized sibling Project history.
        root = f"/api/v1/organizations/{world.organization_id}"
        sibling_response = client.post(
            f"{root}/projects",
            json={
                "name": "Sibling",
                "slug": f"sibling-{uuid4().hex}",
                "workspace_id": str(world.workspace_a_id),
            },
        )
        assert sibling_response.status_code == 201, sibling_response.text
        sibling = UUID(sibling_response.json()["id"])
        assert _page(client, world, project=sibling)["items"] == []
        sibling_change = _register(
            client, _source_path(world, sibling), "reference_empty_4326", "Sibling only"
        )
        assert [item["id"] for item in _page(client, world, project=sibling)["items"]] == [
            sibling_change["change_id"]
        ]
        default = _page(client, world)
        assert default["next_after_id"] is None
        items = default["items"]
        assert len(items) == len(expected) == 7
        assert _all_changes(client, world, limit=1) == items
        assert _all_changes(client, world, limit=2) == items
        assert _page(client, world, after_id=str(UUID(int=0)))["items"] == items
        assert _page(client, world, after_id=items[-1]["id"])["items"] == []
        assert _page(client, world, after_id=str(UUID(int=(1 << 128) - 1)))["items"] == []
        by_id = {item["id"]: item for item in items}
        assert set(by_id) == {mutation["change_id"] for mutation, _, _ in expected}
        for mutation, operation, diff in expected:
            _assert_change(world, by_id[mutation["change_id"]], mutation, operation, diff)
        assert _counts(world) == (1, 7, 1, 1, 7, 8)  # includes sibling source audit

        for params in ({"limit": 0}, {"limit": 101}, {"after_id": "not-a-valid-id"}):
            invalid = client.get(_change_path(world), params=params)
            assert invalid.status_code == 422, invalid.text
            assert invalid.json() == {
                "detail": [{"loc": [], "msg": "invalid request payload", "type": "value_error"}]
            }


def test_service_actor_snapshot_immutable_after_credential_and_principal_revoke(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    root = f"/api/v1/organizations/{world.organization_id}"
    path = _source_path(world)
    with _client(world.owner_user_id) as owner:
        registered = _register(owner, path, "reference_points_5899")
        source_id = registered["resource_id"]
        principal_id, credential_id, secret = _issue_manager_credential(
            owner,
            root,
            world.project_id,
        )
        with _service_client(secret) as machine:
            response = machine.patch(
                f"{path}/{source_id}", json={"expected_revision": 1, "name": "Automation"}
            )
            assert response.status_code == 200, response.text
            mutation = response.json()
            assert mutation["new_revision"] == {
                **registered["new_revision"],
                "catalog_revision": 2,
            }
            history = _page(machine, world)
            assert secret not in str(history)
            assert credential_id not in str(history)
            item = next(item for item in history["items"] if item["id"] == mutation["change_id"])
        assert (
            owner.post(
                f"{root}/service-principals/{principal_id}/credentials/{credential_id}/revoke"
            ).status_code
            == 204
        )
        assert owner.post(f"{root}/service-principals/{principal_id}/revoke").status_code == 204
        with _service_client(secret) as machine:
            assert machine.get(_change_path(world)).status_code == 401
        after = _page(owner, world)
        assert after == history
        assert secret not in str(after) and credential_id not in str(after)
        _assert_change(
            world,
            item,
            mutation,
            "update_source",
            {"name": ("Reference", "Automation"), "catalog_revision": (1, 2)},
            actor_type="service_principal",
            actor_id=UUID(principal_id),
            display_name="race-fixture",
        )
        assert _counts(world)[-2:] == (2, 2)


def test_noop_stale_denied_or_dependency_conflict_never_append_evidence(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    source_path, layer_path = _source_path(world), _layer_path(world)
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as member:
        source_id = _register(owner, source_path, "reference_points_5899")["resource_id"]
        layer_id = _create(owner, world, source_id, "Initial layer")["resource_id"]
        source_url, layer_url = f"{source_path}/{source_id}", f"{layer_path}/{layer_id}"
        initial_source = _get(owner, source_path, source_id)
        initial_layer = _detail(owner, layer_path, layer_id)
        rows = _rows(source_id)
        before = _counts(world)
        history = _all_changes(owner, world)

        _error(
            owner.patch(source_url, json={"expected_revision": 1, "name": " Reference "}),
            422,
            "NO_CHANGES",
        )
        _error(
            owner.patch(layer_url, json={"expected_revision": 1, "name": " Initial layer "}),
            422,
            "NO_CHANGES",
        )
        _error(
            owner.patch(source_url, json={"expected_revision": 2, "name": "Would change"}),
            409,
            "STALE_CATALOG_REVISION",
        )
        _error(
            owner.patch(layer_url, json={"expected_revision": 2, "name": "Would change"}),
            409,
            "STALE_LAYER_REVISION",
        )
        _error(
            owner.post(f"{source_url}/retire", json={"expected_revision": 1}),
            409,
            "ACTIVE_LAYER_DEPENDENCIES",
        )
        denied = member.patch(layer_url, json={"expected_revision": 1, "name": "Unauthorized"})
        assert denied.status_code == 403, denied.text
        assert member.get(_change_path(world)).status_code == 403
        assert _get(owner, source_path, source_id) == initial_source
        assert _detail(owner, layer_path, layer_id) == initial_layer
        assert _rows(source_id) == rows
        assert _counts(world) == before
        assert _all_changes(owner, world) == history


@pytest.mark.parametrize("operation", ["rename_layer", "correct_source_crs"])
def test_failed_evidence_append_rolls_back_mutation_and_audit(
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    world = seed_access_world()
    source_path, layer_path = _source_path(world), _layer_path(world)
    with _client(world.owner_user_id, raise_server_exceptions=False) as client:
        fixture = (
            "reference_points_5899" if operation == "rename_layer" else "reference_correctable_crs"
        )
        source_id = _register(client, source_path, fixture)["resource_id"]
        source_before = _get(client, source_path, source_id)
        layer_id = None
        layer_before = None
        if operation == "rename_layer":
            layer_id = _create(client, world, source_id, "Before")["resource_id"]
            layer_before = _detail(client, layer_path, layer_id)
        rows_before = _rows(source_id)
        counts_before = _counts(world)
        history_before = _all_changes(client, world)
        append = SqlSpatialRepository.append_change
        inserted = []

        def append_then_fail(self, change, audit, *, context):
            append(self, change, audit, context=context)
            if change.operation == CatalogOperation(operation):
                inserted.append((change.id, change.audit_event_id))
                raise RuntimeError("synthetic failure after real catalog and audit append")

        def mutate():
            if operation == "rename_layer":
                return client.patch(
                    f"{layer_path}/{layer_id}", json={"expected_revision": 1, "name": "After"}
                )
            return _correct(client, f"{source_path}/{source_id}")

        with monkeypatch.context() as patch:
            patch.setattr(SqlSpatialRepository, "append_change", append_then_fail)
            failed = mutate()
            assert failed.status_code == 500, failed.text
        assert len(inserted) == 1
        change_id, audit_id = inserted[0]
        with get_admin_engine().begin() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM spatial.catalog_changes WHERE id=:id"),
                    {"id": change_id},
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM audit.audit_events WHERE id=:id"),
                    {"id": audit_id},
                ).scalar_one()
                == 0
            )
        assert _counts(world) == counts_before
        assert _all_changes(client, world) == history_before
        assert _get(client, source_path, source_id) == source_before
        assert _rows(source_id) == rows_before
        if layer_id is not None:
            assert _detail(client, layer_path, layer_id) == layer_before

        response = mutate()
        assert response.status_code == 200, response.text
        mutation = response.json()
        history = _all_changes(client, world)
        assert len(history) == len(history_before) + 1
        item = next(item for item in history if item["id"] == mutation["change_id"])
        diff = (
            {"name": ("Before", "After"), "layer_revision": (1, 2)}
            if operation == "rename_layer"
            else _correction_diff(source_before, _get(client, source_path, source_id))
        )
        _assert_change(world, item, mutation, operation, diff)
        assert _counts(world) == (*counts_before[:-2], counts_before[-2] + 1, counts_before[-1] + 1)


@pytest.mark.parametrize("resource_type", ["data_source", "layer"])
def test_concurrent_compare_and_set_has_one_winner_and_one_change(
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
    resource_type: str,
) -> None:
    world = seed_access_world()
    source_path, layer_path = _source_path(world), _layer_path(world)
    source_mutation = resource_type == "data_source"
    operation = "update_source" if source_mutation else "rename_layer"
    revision_key = "catalog_revision" if source_mutation else "layer_revision"
    stale = "STALE_CATALOG_REVISION" if source_mutation else "STALE_LAYER_REVISION"
    with _client(world.owner_user_id) as owner:
        registered = _register(owner, source_path, "reference_points_5899")
        source_id = registered["resource_id"]
        resource_id = (
            source_id
            if source_mutation
            else _create(owner, world, source_id, "Reference")["resource_id"]
        )
        path = source_path if source_mutation else layer_path
        before = _counts(world)
        history_before = _all_changes(owner, world)
        rows_before = _rows(source_id)
    url = f"{path}/{resource_id}"
    recording, release = Event(), Event()
    append = SqlSpatialRepository.append_change

    def pause_after_winner_append(self, change, audit, *, context):
        append(self, change, audit, context=context)
        if (
            change.operation == CatalogOperation(operation)
            and change.project_id == world.project_id
        ):
            recording.set()
            assert release.wait(20), "test did not release first transaction"

    with (
        _client(world.owner_user_id) as first,
        _client(world.owner_user_id) as second,
        monkeypatch.context() as patch,
    ):
        patch.setattr(SqlSpatialRepository, "append_change", pause_after_winner_append)
        with ThreadPoolExecutor(max_workers=2) as pool:
            winner = pool.submit(first.patch, url, json={"expected_revision": 1, "name": "Winner"})
            try:
                assert recording.wait(10), "first transaction never reached evidence append"
                loser = pool.submit(
                    second.patch, url, json={"expected_revision": 1, "name": "Loser"}
                )
                _wait_for_blocked_runtime_query()
                assert not loser.done(), "contending transaction escaped the PostgreSQL lock"
            finally:
                release.set()
            winner_response, loser_response = winner.result(timeout=20), loser.result(timeout=20)

    assert winner_response.status_code == 200, winner_response.text
    _error(loser_response, 409, stale)
    mutation = winner_response.json()
    prior = registered["new_revision"] if source_mutation else {"layer_revision": 1}
    assert mutation["resource_id"] == resource_id
    assert mutation["prior_revision"] == prior
    assert mutation["new_revision"] == {**prior, revision_key: 2}
    with _client(world.owner_user_id) as owner:
        history = _all_changes(owner, world)
        item = next(item for item in history if item["id"] == mutation["change_id"])
        assert [entry for entry in history if entry["id"] != item["id"]] == history_before
        _assert_change(
            world,
            item,
            mutation,
            operation,
            {"name": ("Reference", "Winner"), revision_key: (1, 2)},
        )
        current = (
            _get(owner, source_path, resource_id)
            if source_mutation
            else _detail(owner, layer_path, resource_id)
        )
        assert current["name"] == "Winner" and current[revision_key] == 2
        assert _rows(source_id) == rows_before
    assert _counts(world) == (*before[:-2], before[-2] + 1, before[-1] + 1)


def test_runtime_cannot_update_delete_or_truncate_real_change_evidence(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        mutation = _register(client, _source_path(world), "reference_empty_4326")
        history = _page(client, world)
        before = _counts(world)
        change_id = UUID(mutation["change_id"])
        with get_engine().begin() as connection:
            assert tuple(
                connection.execute(
                    text(
                        "SELECT current_user,rolsuper,rolbypassrls FROM pg_roles "
                        "WHERE rolname=current_user"
                    )
                ).one()
            ) == ("openvietgis_runtime", False, False)
            _bind(connection, world.organization_id, world.project_id)
            assert (
                connection.execute(
                    text("SELECT id FROM spatial.catalog_changes WHERE id=:id"),
                    {"id": change_id},
                ).scalar_one()
                == change_id
            )
            for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
                assert not connection.execute(
                    text("SELECT has_table_privilege('spatial.catalog_changes', :privilege)"),
                    {"privilege": privilege},
                ).scalar_one()
            for statement in (
                "UPDATE spatial.catalog_changes SET operation=operation WHERE id=:id",
                "DELETE FROM spatial.catalog_changes WHERE id=:id",
                "TRUNCATE spatial.catalog_changes",
            ):
                _assert_denied(connection, statement, {"id": change_id}, "42501")
        assert _page(client, world) == history
        assert _counts(world) == before
