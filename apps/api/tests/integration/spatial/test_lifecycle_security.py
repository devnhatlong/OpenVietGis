"""US4 lifecycle and current-authority acceptance over real restricted HTTP.

Previously authorized feature pins/cursors are inputs, never authority. All
lifecycle changes, grants and revocations use the R002 HTTP API. Owner SQL
only observes committed evidence and proves the existing authorization lock.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlServicePrincipalRepository,
)
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.service_identity.test_service_authorization import (
    _issue_manager_credential,
    _service_client,
)
from tests.integration.spatial.test_layers import (
    _counts,
    _layers,
)
from tests.integration.spatial.test_layers import (
    _path as _layer_path,
)
from tests.integration.spatial.test_pinned_reads import _pins, _setup
from tests.integration.spatial.test_sources import _client, _error, _rows
from tests.integration.spatial.test_sources import (
    _path as _source_path,
)
from tests.integration.tenancy.test_p1_http_access_gate import _viewer_grant


def _root(world):
    return f"/api/v1/organizations/{world.organization_id}"


def _project(world):
    return f"{_root(world)}/projects/{world.project_id}"


def _history(world):
    return f"{_project(world)}/spatial/changes"


def _snapshot(world, source_id):
    # Count all catalog evidence and all spatial audit events (not just
    # successes), and compare the actual committed data, including revisions.
    scope = {"org": world.organization_id, "project": world.project_id}
    with get_admin_engine().begin() as connection:
        sources = (
            connection.execute(
                text("""
                SELECT to_jsonb(s) FROM spatial.data_sources s
                WHERE organization_id=:org AND project_id=:project ORDER BY id
            """),
                scope,
            )
            .scalars()
            .all()
        )
        fields = (
            connection.execute(
                text("""
                SELECT to_jsonb(f) FROM spatial.source_fields f
                WHERE organization_id=:org AND project_id=:project
                ORDER BY source_id, field_id
            """),
                scope,
            )
            .scalars()
            .all()
        )
        changes = (
            connection.execute(
                text("""
                SELECT to_jsonb(c) FROM spatial.catalog_changes c
                WHERE organization_id=:org AND project_id=:project ORDER BY id
            """),
                scope,
            )
            .scalars()
            .all()
        )
        audit = (
            connection.execute(
                text("""
                SELECT to_jsonb(a) FROM audit.audit_events a
                WHERE organization_id=:org AND resource_type IN ('data_source','layer')
                ORDER BY id
            """),
                scope,
            )
            .scalars()
            .all()
        )
    return _counts(world), sources, fields, _rows(source_id), _layers(world), changes, audit


def _reads(world, source, layer_id, url, first):
    return (
        (_source_path(world), {}),
        (f"{_source_path(world)}/{source['id']}", {}),
        (_layer_path(world), {}),
        (f"{_layer_path(world)}/{layer_id}", {}),
        (url, _pins(source) | {"limit": 2}),
        (
            url,
            _pins(source) | {"limit": 2, "after_feature_id": first["next_after_feature_id"]},
        ),
        (f"{url}/{first['items'][0]['feature_id']}", _pins(source)),
        (f"{_project(world)}/spatial/crs-profiles", {}),
    )


def _writes(world, source, layer_id):
    source_url = f"{_source_path(world)}/{source['id']}"
    layer_url = f"{_layer_path(world)}/{layer_id}"
    return (
        (
            "POST",
            _source_path(world),
            {"reference_key": "reference_empty_4326", "name": "Denied registration"},
        ),
        ("PATCH", source_url, {"expected_revision": 1, "name": "Denied source rename"}),
        (
            "PATCH",
            source_url,
            {
                "expected_revision": 1,
                "declared_crs": {"authority": "EPSG", "code": 4326, "coordinate_order": "xy"},
            },
        ),
        ("POST", f"{source_url}/retire", {"expected_revision": 1}),
        ("POST", _layer_path(world), {"source_id": source["id"], "name": "Denied layer"}),
        ("PATCH", layer_url, {"expected_revision": 1, "name": "Denied layer rename"}),
        ("POST", f"{layer_url}/retire", {"expected_revision": 1}),
    )


def _read_all(client, routes):
    results = []
    for url, params in routes:
        response = client.get(url, params=params)
        assert response.status_code == 200, response.text
        results.append(response.json())
    return results


def _denied(response, status, source, layer_id):
    assert response.status_code == status, response.text
    assert set(response.json()) == {"detail"}
    assert isinstance(response.json()["detail"], str)
    for secret in (source["id"], layer_id, *_pins(source).values()):
        assert secret not in response.text


def _deny_reads(client, routes, status, source, layer_id):
    for url, params in routes:
        _denied(client.get(url, params=params), status, source, layer_id)


def test_archived_project_preserves_reads_but_checks_permission_before_state(
    migrated_database: None,
):
    world = seed_access_world()
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as viewer:
        source, layer_id, url, first = _setup(owner, world)
        _viewer_grant(owner, world)
        reads = _reads(world, source, layer_id, url, first)
        expected = _read_all(owner, reads)
        assert _read_all(viewer, reads) == expected
        assert owner.patch(_project(world), json={"status": "archived"}).status_code == 200
        before = _snapshot(world, source["id"])

        assert _read_all(owner, reads) == expected
        assert _read_all(viewer, reads) == expected
        # Source retire even has an active Layer dependency; archived state
        # must win for an authorized manager and permission denial must win
        # for a viewer before disclosing anything about resource/state.
        for method, path, payload in _writes(world, source, layer_id):
            _denied(viewer.request(method, path, json=payload), 403, source, layer_id)
            _error(owner.request(method, path, json=payload), 409, "PROJECT_NOT_WRITABLE")

        absent_source = f"{_source_path(world)}/{uuid4()}"
        absent_layer = f"{_layer_path(world)}/{uuid4()}"
        for path in (absent_source, absent_layer):
            payload = {"expected_revision": 1, "name": "Absent"}
            _denied(viewer.patch(path, json=payload), 403, source, layer_id)
            _error(owner.patch(path, json=payload), 409, "PROJECT_NOT_WRITABLE")

        history = _read_all(owner, ((_history(world), {}),))[0]
        assert {(entry["resource_id"], entry["operation"]) for entry in history["items"]} == {
            (source["id"], "register_source"),
            (layer_id, "create_layer"),
        }
        assert _read_all(viewer, ((_history(world), {}),)) == [history]
        assert _snapshot(world, source["id"]) == before
        assert owner.patch(_project(world), json={"status": "active"}).status_code == 200
        assert _read_all(viewer, reads + ((_history(world), {}),)) == expected + [history]


@pytest.mark.parametrize(("transition", "status"), [("deleted", 404), ("suspended", 403)])
def test_project_deleted_or_organization_suspended_hides_even_pinned_reads(
    migrated_database: None, transition, status
):
    world = seed_access_world()
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as viewer:
        source, layer_id, url, first = _setup(owner, world)
        _viewer_grant(owner, world)
        reads = _reads(world, source, layer_id, url, first)
        expected = _read_all(viewer, reads)
        target = _project(world) if transition == "deleted" else _root(world)
        if transition == "deleted":
            assert owner.patch(target, json={"status": "archived"}).status_code == 200
        changed = owner.patch(target, json={"status": transition})
        assert changed.status_code == 200, changed.text
        before = _snapshot(world, source["id"])

        all_reads = reads + ((_history(world), {}),)
        for actor in (owner, viewer):
            for path, params in all_reads:
                result = actor.get(path, params=params)
                _denied(result, status, source, layer_id)
                if transition == "deleted":
                    # A deleted Project is indistinguishable from an unknown
                    # Project, even with genuine IDs and pins in the request.
                    absent = path.replace(str(world.project_id), str(uuid4()), 1)
                    missing = actor.get(absent, params=params)
                    assert missing.status_code == result.status_code
                    assert missing.json() == result.json()
            for method, path, payload in _writes(world, source, layer_id):
                _denied(actor.request(method, path, json=payload), status, source, layer_id)

        assert _snapshot(world, source["id"]) == before
        restored = owner.patch(target, json={"status": "active"})
        assert restored.status_code == 200, restored.text
        assert _read_all(viewer, reads) == expected


@pytest.mark.parametrize(
    ("transition", "status"), [("grant", 403), ("suspended", 404), ("revoked", 404)]
)
def test_old_pins_do_not_cache_grant_or_membership_authority(
    migrated_database: None, transition, status
):
    world = seed_access_world()
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as viewer:
        source, layer_id, url, first = _setup(owner, world)
        grant_id = _viewer_grant(owner, world)
        reads = _reads(world, source, layer_id, url, first)
        _read_all(viewer, reads)
        session = viewer.cookies.get("ovg_session")
        if transition == "grant":
            assert owner.post(f"{_root(world)}/grants/{grant_id}/revoke").status_code == 204
        else:
            changed = owner.patch(
                f"{_root(world)}/members/{world.member_membership_id}",
                json={"status": transition},
            )
            assert changed.status_code == 200, changed.text
        before = _snapshot(world, source["id"])
        _deny_reads(viewer, reads + ((_history(world), {}),), status, source, layer_id)
        for method, path, payload in _writes(world, source, layer_id):
            _denied(viewer.request(method, path, json=payload), status, source, layer_id)
        assert viewer.get("/api/v1/me").status_code == 200
        assert viewer.cookies.get("ovg_session") == session
        assert _snapshot(world, source["id"]) == before


def test_workspace_reassignment_rechecks_inherited_grants_with_same_old_pins(
    migrated_database: None,
):
    world = seed_access_world()
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as viewer:
        source, layer_id, url, first = _setup(owner, world)
        inherited = _viewer_grant(owner, world, workspace_id=world.workspace_a_id)
        reads = _reads(world, source, layer_id, url, first) + ((_history(world), {}),)
        expected = _read_all(viewer, reads)
        session = viewer.cookies.get("ovg_session")
        moved = owner.patch(_project(world), json={"workspace_id": str(world.workspace_b_id)})
        assert moved.status_code == 200, moved.text
        before = _snapshot(world, source["id"])
        _deny_reads(viewer, reads, 403, source, layer_id)
        assert _snapshot(world, source["id"]) == before

        direct = _viewer_grant(owner, world)
        assert _read_all(viewer, reads) == expected
        # The direct grant survives another move; the original inherited
        # grant never follows the project to the new Workspace.
        created = owner.post(
            f"{_root(world)}/workspaces",
            json={"name": "Another Workspace", "slug": f"another-{uuid4().hex}"},
        )
        assert created.status_code == 201, created.text
        moved = owner.patch(_project(world), json={"workspace_id": created.json()["id"]})
        assert moved.status_code == 200, moved.text
        assert _read_all(viewer, reads) == expected
        assert owner.post(f"{_root(world)}/grants/{direct}/revoke").status_code == 204
        _deny_reads(viewer, reads, 403, source, layer_id)
        # Moving back re-enables only the still-current inherited grant.
        moved = owner.patch(_project(world), json={"workspace_id": str(world.workspace_a_id)})
        assert moved.status_code == 200, moved.text
        assert _read_all(viewer, reads) == expected
        assert owner.post(f"{_root(world)}/grants/{inherited}/revoke").status_code == 204
        _deny_reads(viewer, reads, 403, source, layer_id)
        assert viewer.cookies.get("ovg_session") == session
        assert _snapshot(world, source["id"]) == before


def test_retired_resources_hide_old_pins_and_ordinary_metadata_but_keep_history(
    migrated_database: None,
):
    world = seed_access_world()
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as viewer:
        source, layer_id, url, first = _setup(owner, world)
        _viewer_grant(owner, world)
        reads = _reads(world, source, layer_id, url, first)
        _read_all(viewer, reads)
        layer_url = f"{_layer_path(world)}/{layer_id}"
        source_url = f"{_source_path(world)}/{source['id']}"
        retired_layer = owner.post(f"{layer_url}/retire", json={"expected_revision": 1})
        assert retired_layer.status_code == 200, retired_layer.text
        before = _snapshot(world, source["id"])
        for actor in (owner, viewer):
            # Layer retirement invalidates ordinary detail and all feature
            # lookups, even while its Source is still active and unchanged.
            for path, params in reads[3:7]:
                result = actor.get(path, params=params)
                _denied(result, 404, source, layer_id)
                missing = actor.get(path.replace(layer_id, str(uuid4()), 1), params=params)
                assert missing.status_code == 404
                assert missing.json() == result.json()
            assert _read_all(actor, ((_layer_path(world), {}),))[0]["items"] == []
            assert _read_all(actor, ((source_url, {}),))[0] == source
        assert _snapshot(world, source["id"]) == before

        retired_source = owner.post(f"{source_url}/retire", json={"expected_revision": 1})
        assert retired_source.status_code == 200, retired_source.text
        before = _snapshot(world, source["id"])
        for actor in (owner, viewer):
            result = actor.get(source_url)
            _denied(result, 404, source, layer_id)
            missing = actor.get(f"{_source_path(world)}/{uuid4()}")
            assert missing.status_code == 404
            assert missing.json() == result.json()
            _deny_reads(actor, reads[3:7], 404, source, layer_id)
            assert _read_all(actor, ((_source_path(world), {}),))[0]["items"] == []
            assert _read_all(actor, ((_layer_path(world), {}),))[0]["items"] == []
            history = _read_all(actor, ((_history(world), {}),))[0]["items"]
            assert {(item["resource_id"], item["operation"]) for item in history} == {
                (source["id"], "register_source"),
                (layer_id, "create_layer"),
                (source["id"], "retire_source"),
                (layer_id, "retire_layer"),
            }
            assert {retired_layer.json()["change_id"], retired_source.json()["change_id"]} <= {
                item["id"] for item in history
            }
        for path in (source_url, layer_url):
            _denied(
                owner.patch(path, json={"expected_revision": 2, "name": "Retired"}),
                404,
                source,
                layer_id,
            )
            _denied(
                owner.post(f"{path}/retire", json={"expected_revision": 2}), 404, source, layer_id
            )
        assert _snapshot(world, source["id"]) == before


def _service_action(client, action, source, layer_id, url, first):
    if action == "page":
        return client.get(
            url, params=_pins(source) | {"after_feature_id": first["next_after_feature_id"]}
        )
    if action == "detail":
        return client.get(f"{url}/{first['items'][0]['feature_id']}", params=_pins(source))
    assert action == "rename"
    return client.patch(
        url.removesuffix("/features"),
        json={"expected_revision": 1, "name": f"Service rename {layer_id}"},
    )


@pytest.mark.parametrize("action", ["page", "detail", "rename"])
@pytest.mark.parametrize("revoke_principal", [False, True])
def test_revoke_between_bearer_lookup_and_spatial_gate_denies_stale_auth(
    migrated_database: None, monkeypatch, action, revoke_principal
):
    world = seed_access_world()
    looked_up, resume = Event(), Event()
    original = SqlServicePrincipalRepository.get_credential_for_authentication

    def pause_after_lookup(self, *, organization_id, credential_id):
        resolved = original(self, organization_id=organization_id, credential_id=credential_id)
        if resolved is not None:
            looked_up.set()
            assert resume.wait(timeout=15), "credential lookup was not resumed"
        return resolved

    monkeypatch.setattr(
        SqlServicePrincipalRepository, "get_credential_for_authentication", pause_after_lookup
    )
    with _client(world.owner_user_id) as owner:
        source, layer_id, url, first = _setup(owner, world)
        principal_id, credential_id, secret = _issue_manager_credential(
            owner, _root(world), world.project_id
        )
        path = f"{_root(world)}/service-principals/{principal_id}"
        if not revoke_principal:
            path += f"/credentials/{credential_id}"
        before = _snapshot(world, source["id"])

        def request():
            with _service_client(secret) as service:
                return _service_action(service, action, source, layer_id, url, first)

        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(request)
            try:
                assert looked_up.wait(timeout=10), "request never reached real credential lookup"
                revoked = owner.post(f"{path}/revoke")
                assert revoked.status_code == 204, revoked.text
            finally:
                resume.set()
            result = pending.result(timeout=15)
        _denied(result, 401, source, layer_id)
        _denied(request(), 401, source, layer_id)
        assert _snapshot(world, source["id"]) == before
        with get_admin_engine().connect() as connection:
            credential = connection.execute(
                text("SELECT revoked_at,last_used_at FROM org.service_credentials WHERE id=:id"),
                {"id": credential_id},
            ).one()
            assert credential.last_used_at is None
            if revoke_principal:
                assert (
                    connection.execute(
                        text("SELECT status FROM org.service_principals WHERE id=:id"),
                        {"id": principal_id},
                    ).scalar_one()
                    == "revoked"
                )
            else:
                assert credential.revoked_at is not None


@pytest.mark.parametrize("action", ["page", "rename"])
def test_spatial_request_winning_org_lock_finishes_before_revocation(
    migrated_database: None, monkeypatch, action
):
    world = seed_access_world()
    touched, resume = Event(), Event()
    original = SqlServicePrincipalRepository.record_credential_use

    def pause_after_touch(self, credential, *, context):
        recorded = original(self, credential, context=context)
        if recorded:
            touched.set()
            assert resume.wait(timeout=15), "credential use was not resumed"
        return recorded

    monkeypatch.setattr(SqlServicePrincipalRepository, "record_credential_use", pause_after_touch)
    with _client(world.owner_user_id) as owner:
        source, layer_id, url, first = _setup(owner, world)
        principal_id, credential_id, secret = _issue_manager_credential(
            owner, _root(world), world.project_id
        )
        before = _snapshot(world, source["id"])

        def request():
            with _service_client(secret) as service:
                return _service_action(service, action, source, layer_id, url, first)

        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(request)
            try:
                assert touched.wait(timeout=10), "request never recorded real credential use"
                with (
                    get_admin_engine().connect() as connection,
                    pytest.raises(OperationalError) as caught,
                ):
                    connection.execute(
                        text("SELECT id FROM org.organizations WHERE id=:id FOR UPDATE NOWAIT"),
                        {"id": world.organization_id},
                    )
                assert getattr(caught.value.orig, "sqlstate", None) == "55P03"
            finally:
                resume.set()
            result = pending.result(timeout=15)
        assert result.status_code == 200, result.text
        if action == "page":
            assert result.json()["items"]
            assert _pins(result.json()["context"]) == _pins(source)
            assert _snapshot(world, source["id"]) == before
        else:
            assert result.json()["new_revision"] == {"layer_revision": 2}
            assert _counts(world) == before[0][:-2] + (before[0][-2] + 1, before[0][-1] + 1)
            assert _rows(source["id"]) == before[3]

        revoked = owner.post(
            f"{_root(world)}/service-principals/{principal_id}/credentials/{credential_id}/revoke"
        )
        assert revoked.status_code == 204, revoked.text
        after = _snapshot(world, source["id"])
        _denied(request(), 401, source, layer_id)
        assert _snapshot(world, source["id"]) == after
