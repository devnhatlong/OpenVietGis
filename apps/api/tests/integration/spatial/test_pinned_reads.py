"""US3 pinned reads and controlled refresh under real restricted-role transactions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.rls import bind_authenticated_actor
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.spatial import service
from openvietgis_api.domains.spatial.domain import CatalogOperation
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import AccessWorld, seed_access_world
from tests.integration.spatial.test_layers import (
    _counts,
    _create,
    _detail,
    _wait_for_blocked_runtime_query,
)
from tests.integration.spatial.test_layers import (
    _path as _layer_path,
)
from tests.integration.spatial.test_sources import (
    _changes,
    _client,
    _error,
    _get,
    _register,
    _rows,
)
from tests.integration.spatial.test_sources import (
    _path as _source_path,
)


def _pins(source):
    return {key: source[key] for key in ("content_revision", "schema_revision")}


def _revision(source):
    return {"catalog_revision": source["catalog_revision"], **_pins(source)}


def _setup(client: TestClient, world: AccessWorld):
    source_id = _register(client, _source_path(world), "reference_points_5899")["resource_id"]
    layer_id = _create(client, world, source_id, "Pinned layer")["resource_id"]
    url = f"{_layer_path(world)}/{layer_id}/features"
    source = _get(client, _source_path(world), source_id)
    layer = _detail(client, _layer_path(world), layer_id)
    assert _pins(layer["source"]) == _pins(source)
    first = _page(client, url, source, limit=2)
    assert len(first["items"]) == 2 and first["next_after_feature_id"]
    return source, layer_id, url, first


def _page(client: TestClient, url: str, source, **query):
    response = client.get(url, params=_pins(source) | query)
    assert response.status_code == 200, response.text
    page = response.json()
    assert _pins(page["context"]) == _pins(source)
    assert page["context"]["source_id"] == source["id"]
    assert page["context"]["project_id"] == source["project_id"]
    assert page["context"]["organization_id"] == source["organization_id"]
    assert page["context"]["layer_id"] == url.split("/")[-2]
    return page


def _feature_detail(client: TestClient, url: str, source, feature_id: str):
    response = client.get(f"{url}/{feature_id}", params=_pins(source))
    assert response.status_code == 200, response.text
    result = response.json()
    assert _pins(result["context"]) == _pins(source)
    return result


def _refresh(world: AccessWorld, source_id: str, variant: str):
    """Call only an internal test seam; never use owner SQL to mutate a fixture."""
    context = AuthorizationContext(
        Actor("human", world.owner_user_id, "Owner"),
        world.organization_id,
        project_id=world.project_id,
    )
    with get_session_factory()() as session:
        bind_authenticated_actor(session, context.actor)
        assert tuple(
            session.execute(
                text("""
                SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user
                """)
            ).one()
        ) == ("openvietgis_runtime", False, False)
        result = service.SpatialFeatureService(
            SqlSpatialRepository(session)
        ).refresh_reference_fixture_for_test(
            context=context, source_id=UUID(source_id), variant=variant
        )
        session.commit()
        return result


def _assert_committed_pins(source, page):
    # Every persisted row's pins and actual feature attributes must agree with
    # the authorized HTTP metadata and results, including the unreturned rows.
    rows = _rows(source["id"])
    assert len(rows) == source["feature_count"] == 4
    assert all(_pins(row) == _pins(source) for row in rows)
    with get_admin_engine().begin() as connection:
        fields = (
            connection.execute(
                text("""
                SELECT field_id,name,ordinal,type,nullable,schema_revision
                FROM spatial.source_fields
                WHERE organization_id=:org AND project_id=:project AND source_id=:source
                ORDER BY ordinal
                """),
                {
                    "org": source["organization_id"],
                    "project": source["project_id"],
                    "source": source["id"],
                },
            )
            .mappings()
            .all()
        )
    assert fields
    assert all(field["schema_revision"] == source["schema_revision"] for field in fields)
    assert source["schema"]["schema_revision"] == source["schema_revision"]
    assert [
        {key: value for key, value in field.items() if key != "schema_revision"} for field in fields
    ] == source["schema"]["fields"]
    by_id = {row["feature_id"]: row for row in rows}
    for feature in page["items"]:
        assert set(feature["attributes"]) == {field["field_id"] for field in fields}
        assert feature["attributes"] == by_id[feature["feature_id"]]["attributes"]
    return rows


def _assert_stale(client: TestClient, url: str, pins, first):
    feature_id = first["items"][0]["feature_id"]
    for target, query in (
        (url, {}),
        (url, {"after_feature_id": first["next_after_feature_id"]}),
        (f"{url}/{feature_id}", {}),
    ):
        response = client.get(target, params=_pins(pins) | query)
        _error(response, 409, "STALE_READ_PIN")
        assert set(response.json()) == {"code", "detail"}


@pytest.mark.parametrize("variant", ["content", "schema"])
def test_refresh_changes_only_affected_pins_and_metadata_renames_preserve_them(
    migrated_database: None, variant: str
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        original, layer_id, url, first = _setup(client, world)
        native = _rows(original["id"])
        whole = _page(client, url, original)
        assert len(whole["items"]) == 4
        feature_id = first["items"][0]["feature_id"]
        old_detail = _feature_detail(client, url, original, feature_id)
        assert old_detail == {"context": first["context"], "feature": first["items"][0]}

        renamed = client.patch(
            f"{_source_path(world)}/{original['id']}",
            json={"name": "Renamed source", "expected_revision": 1},
        )
        assert renamed.status_code == 200, renamed.text
        renamed_layer = client.patch(
            f"{_layer_path(world)}/{layer_id}",
            json={"name": "Renamed layer", "expected_revision": 1},
        )
        assert renamed_layer.status_code == 200, renamed_layer.text
        source = _get(client, _source_path(world), original["id"])
        assert source["catalog_revision"] == 2
        assert _pins(source) == _pins(original)
        assert source["schema"] == original["schema"]
        assert _rows(source["id"]) == native
        assert _page(client, url, source, limit=2) == first
        assert _feature_detail(client, url, source, feature_id) == old_detail
        continued = _page(
            client, url, original, limit=2, after_feature_id=first["next_after_feature_id"]
        )
        assert first["items"] + continued["items"] == whole["items"]
        assert continued["next_after_feature_id"] is None

        before = _counts(world)
        result = _refresh(world, source["id"], variant)
        current = _get(client, _source_path(world), source["id"])
        assert current["catalog_revision"] == 3
        assert current["validation_state"] == "ready"
        assert result.source.id == UUID(source["id"])
        assert result.source.catalog_revision == current["catalog_revision"]
        assert result.source.content_revision == current["content_revision"]
        assert result.source.schema_revision == current["schema_revision"]
        assert _counts(world) == (*before[:-2], before[-2] + 1, before[-1] + 1)
        assert _pins(_detail(client, _layer_path(world), layer_id)["source"]) == _pins(current)

        affected, unaffected = (
            ("content_revision", "schema_revision")
            if variant == "content"
            else ("schema_revision", "content_revision")
        )
        assert current[affected] != source[affected]
        assert current[unaffected] == source[unaffected]
        changes = _changes(
            world,
            {
                "resource_id": source["id"],
                "change_id": str(result.change.id),
                "prior_revision": _revision(source),
                "new_revision": _revision(current),
            },
            "refresh_reference_fixture",
        )
        assert changes["catalog_revision"] == (2, 3)
        assert changes[affected] == (source[affected], current[affected])
        assert unaffected not in changes

        # Old affected pin with current unaffected pin is stale, independently
        # on first page, continuation, and detail; no partial feature output.
        _assert_stale(client, url, current | {affected: source[affected]}, first)
        new_page = _page(client, url, current)
        assert len(new_page["items"]) == 4
        assert [item["feature_id"] for item in new_page["items"]] == [
            item["feature_id"] for item in whole["items"]
        ]
        assert new_page["next_after_feature_id"] is None
        rows = _assert_committed_pins(current, new_page)
        for feature in new_page["items"]:
            assert _feature_detail(client, url, current, feature["feature_id"]) == {
                "context": new_page["context"],
                "feature": feature,
            }
        if variant == "content":
            assert current["schema"] == source["schema"]
            assert new_page["items"] != whole["items"]
        else:
            # A non-interpretive field metadata change alters only the schema
            # pin; feature IDs, attributes, native geometry and content remain.
            assert current["schema"]["fields"] != source["schema"]["fields"]
            assert new_page["items"] == whole["items"]
            assert [
                {key: value for key, value in row.items() if key != "schema_revision"}
                for row in rows
            ] == [
                {key: value for key, value in row.items() if key != "schema_revision"}
                for row in native
            ]


@pytest.mark.parametrize("winner", ["reader", "refresh"])
def test_read_and_refresh_lock_prevents_mixed_revision(
    migrated_database: None, monkeypatch: pytest.MonkeyPatch, winner: str
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as setup:
        source, _, url, first = _setup(setup, world)
        old_page = _page(setup, url, source)

    ready = Event()
    release = Event()
    prepare = SqlSpatialRepository.prepare_scope
    append = SqlSpatialRepository.append_change

    def pause_reader(self, *, context, permission, mutation):
        prepare(self, context=context, permission=permission, mutation=mutation)
        if winner == "reader" and not mutation and context.project_id == world.project_id:
            # Real acquired share lock, before any feature rows are returned.
            ready.set()
            assert release.wait(20), "test did not release read transaction"

    def pause_refresh(self, change, audit, *, context):
        append(self, change, audit, context=context)
        if winner == "refresh" and change.operation == CatalogOperation.REFRESH_REFERENCE_FIXTURE:
            # All real mutation/evidence writes made, but transaction not committed.
            ready.set()
            assert release.wait(20), "test did not release refresh transaction"

    with _client(world.owner_user_id) as reader:

        def read():
            return reader.get(url, params=_pins(source))

        def refresh():
            return _refresh(world, source["id"], "content")

        with monkeypatch.context() as patch:
            patch.setattr(SqlSpatialRepository, "prepare_scope", pause_reader)
            patch.setattr(SqlSpatialRepository, "append_change", pause_refresh)
            with ThreadPoolExecutor(max_workers=2) as pool:
                winning_call = pool.submit(read if winner == "reader" else refresh)
                try:
                    assert ready.wait(10), "winner never acquired its real transaction boundary"
                    losing_call = pool.submit(refresh if winner == "reader" else read)
                    _wait_for_blocked_runtime_query()
                    assert not losing_call.done()
                finally:
                    release.set()
                winning_result = winning_call.result(timeout=20)
                losing_result = losing_call.result(timeout=20)

    read_response = winning_result if winner == "reader" else losing_result
    if winner == "reader":
        assert read_response.status_code == 200, read_response.text
        assert read_response.json() == old_page
    else:
        _error(read_response, 409, "STALE_READ_PIN")

    with _client(world.owner_user_id) as verify:
        current = _get(verify, _source_path(world), source["id"])
        assert current["catalog_revision"] == source["catalog_revision"] + 1
        assert current["schema_revision"] == source["schema_revision"]
        assert current["content_revision"] != source["content_revision"]
        _assert_stale(verify, url, source, first)
        new_page = _page(verify, url, current)
        assert new_page["items"] != old_page["items"]
        _assert_committed_pins(current, new_page)


def test_failed_refresh_rolls_back_manifest_pins_and_evidence(
    migrated_database: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        source, _, url, _ = _setup(client, world)
        old_page = _page(client, url, source)
        old_rows = _rows(source["id"])
        before = _counts(world)
        append = SqlSpatialRepository.append_change

        def fail_after_append(self, change, audit, *, context):
            append(self, change, audit, context=context)
            if change.operation == CatalogOperation.REFRESH_REFERENCE_FIXTURE:
                raise RuntimeError("synthetic evidence transaction failure")

        with monkeypatch.context() as patch:
            patch.setattr(SqlSpatialRepository, "append_change", fail_after_append)
            with pytest.raises(RuntimeError, match="synthetic evidence transaction failure"):
                _refresh(world, source["id"], "schema")

        assert _get(client, _source_path(world), source["id"]) == source
        assert _rows(source["id"]) == old_rows
        assert _counts(world) == before
        assert _page(client, url, source) == old_page
        _assert_committed_pins(source, old_page)
