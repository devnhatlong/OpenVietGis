"""Real restricted-runtime map persistence, replay and recovery regressions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client, _path, _register

pytestmark = pytest.mark.usefixtures("migrated_database")


def _root(world):
    return f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"


def _intent(expected=0, *, layers=None, viewpoint=None):
    return {
        "operation_id": str(uuid4()),
        "expected_revision": expected,
        "layers": layers or [],
        "basemap": "grid",
        "default_viewpoint": viewpoint or {"mode": "preserve"},
    }


def _view(longitude=106.7):
    return {
        "mode": "set",
        "value": {
            "longitude": longitude,
            "latitude": 10.8,
            "zoom": 11,
            "bearing": 0,
            "pitch": 0,
            "crs": 4326,
        },
    }


def _counts(world):
    with get_admin_engine().connect() as connection:
        return tuple(
            connection.execute(
                text(f"SELECT count(*) FROM maps.{table} WHERE project_id=:project"),
                {"project": world.project_id},
            ).scalar_one()
            for table in ("project_maps", "map_operations", "map_revisions")
        )


def test_open_is_read_only_and_first_empty_save_has_exact_minimal_receipt():
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        url = _root(world) + "/map"
        initial = client.get(url)
        assert initial.status_code == 200, initial.text
        assert initial.headers["cache-control"] == "no-store"
        assert initial.json()["configuration_revision"] == 0
        assert initial.json()["configuration"] == {
            "layers": [],
            "basemap": "grid",
            "default_viewpoint": None,
        }
        assert _counts(world) == (0, 0, 0)
        command = _intent()
        saved = client.put(url, json=command)
        assert saved.status_code == 200, saved.text
        assert saved.json() == {
            "map_id": initial.json()["map_id"],
            "operation_id": command["operation_id"],
            "configuration_revision": 1,
        }
        assert _counts(world) == (1, 1, 1)
        assert client.get(url).json()["configuration_revision"] == 1


def test_lost_ack_after_later_save_and_new_session_returns_original_receipt():
    world = seed_access_world()
    url = _root(world) + "/map"
    first = _intent(viewpoint=_view())
    with _client(world.owner_user_id) as client:
        committed = client.put(url, json=first)
        assert committed.status_code == 200, committed.text
        later = client.put(url, json=_intent(1, viewpoint=_view(107.2)))
        assert later.status_code == 200, later.text
    # Fresh authenticated session simulates application/session restart. The
    # client retained original operation+intent when its acknowledgement was lost.
    with _client(world.owner_user_id) as reopened:
        receipt = reopened.get(url + "/operations/" + first["operation_id"])
        assert receipt.status_code == 200 and receipt.json() == committed.json()
        replay = reopened.put(url, json=first)
        assert replay.status_code == 200 and replay.json() == committed.json()
        assert reopened.get(url).json()["configuration_revision"] == 2
        assert _counts(world) == (1, 2, 2)


def test_stale_changed_intent_noop_and_foreign_actor_reuse_are_atomic():
    world = seed_access_world()
    root, url = _root(world), _root(world) + "/map"
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as member:
        issued = owner.post(
            f"/api/v1/organizations/{world.organization_id}/grants",
            json={
                "subject_kind": "membership",
                "subject_id": str(world.member_membership_id),
                "role": "editor",
                "scope_kind": "project",
                "project_id": str(world.project_id),
            },
        )
        assert issued.status_code == 201, issued.text
        original = _intent()
        assert owner.put(url, json=original).status_code == 200
        stale = owner.put(url, json=_intent(0, viewpoint=_view()))
        assert stale.status_code == 409 and stale.json()["code"] == "STALE_MAP_REVISION"
        noop = owner.put(url, json=_intent(1))
        assert noop.status_code == 409 and noop.json()["code"] == "NO_CHANGES"
        changed = owner.put(url, json={**original, "expected_revision": 1})
        assert changed.status_code == 409 and changed.json()["code"] == "OPERATION_INTENT_CONFLICT"
        foreign = member.put(url, json=original)
        assert foreign.status_code == 409
        assert "map_id" not in foreign.json()
        assert member.get(url + "/operations/" + original["operation_id"]).status_code == 404
        assert _counts(world) == (1, 1, 1)
        assert owner.get(root + "/map").json()["configuration_revision"] == 1


def test_designated_viewpoint_preserve_clear_and_safe_history_pagination():
    world = seed_access_world()
    url = _root(world) + "/map"
    with _client(world.owner_user_id) as client:
        assert client.put(url, json=_intent(viewpoint=_view())).status_code == 200
        source = _register(client, _path(world), "reference_points_4326")
        layer = client.post(
            _root(world) + "/layers",
            json={
                "source_id": source["resource_id"],
                "name": "Map Layer",
            },
        )
        assert layer.status_code == 201, layer.text
        layer_id = layer.json()["resource_id"]
        references = [
            {
                "layer_id": layer_id,
                "visible": True,
                "style": {"color": "#112233", "opacity": 0.7, "width": 3, "radius": 6},
            }
        ]
        assert client.put(url, json=_intent(1, layers=references)).status_code == 200
        state = client.get(url).json()
        assert state["configuration"]["default_viewpoint"] == _view()["value"]
        assert (
            client.put(
                url,
                json=_intent(
                    2,
                    layers=references,
                    viewpoint={"mode": "clear"},
                ),
            ).status_code
            == 200
        )
        assert client.get(url).json()["configuration"]["default_viewpoint"] is None
        page = client.get(url + "/history?limit=2")
        assert page.status_code == 200, page.text
        rows = page.json()["items"]
        assert [r["configuration_revision"] for r in rows] == [3, 2]
        assert rows[0]["before_configuration"]["default_viewpoint"] == _view()["value"]
        assert rows[0]["after_configuration"]["default_viewpoint"] is None
        assert rows[0]["actor_id"] == str(world.owner_user_id)
        assert rows[0]["actor_type"] == "human" and rows[0]["created_at"]
        next_page = client.get(
            url + f"/history?limit=2&after_revision={page.json()['next_after_revision']}"
        )
        assert [r["configuration_revision"] for r in next_page.json()["items"]] == [1]
        assert next_page.json()["next_after_revision"] is None
        assert next_page.json()["items"][0]["before_configuration"] is None


def test_precommit_failure_rolls_back_state_operation_history_and_success_audit(monkeypatch):
    world = seed_access_world()
    url = _root(world) + "/map"
    with _client(world.owner_user_id, raise_server_exceptions=False) as client:
        before = _counts(world)

        def fail_append(self, event):
            raise RuntimeError("synthetic pre-commit interruption")

        with monkeypatch.context() as patch:
            patch.setattr(SqlAuditRepository, "append", fail_append)
            command = _intent()
            failed = client.put(url, json=command)
            assert failed.status_code == 500
        assert _counts(world) == before == (0, 0, 0)
        assert client.get(url).json()["configuration_revision"] == 0
        assert client.get(url + "/operations/" + command["operation_id"]).status_code == 404
        recovered = client.put(url, json=command)
        assert recovered.status_code == 200, recovered.text
        assert _counts(world) == (1, 1, 1)
        with get_admin_engine().connect() as connection:
            events = connection.execute(
                text("""
                SELECT count(*) FROM audit.audit_events WHERE organization_id=:org
                AND action='map.configuration.saved'
            """),
                {"org": world.organization_id},
            ).scalar_one()
            assert events == 1


def test_two_concurrent_first_saves_have_one_winner_and_one_stale_conflict():
    world = seed_access_world()
    url = _root(world) + "/map"
    commands = [_intent(viewpoint=_view(106.5)), _intent(viewpoint=_view(107.5))]
    clients = [_client(world.owner_user_id), _client(world.owner_user_id)]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(client.put, url, json=command)
                for client, command in zip(clients, commands, strict=True)
            ]
            responses = [future.result(timeout=30) for future in futures]
        assert sorted(r.status_code for r in responses) == [200, 409]
        denied = next(r for r in responses if r.status_code == 409)
        assert denied.json()["code"] == "STALE_MAP_REVISION"
        assert _counts(world) == (1, 1, 1)
    finally:
        for client in clients:
            client.close()
