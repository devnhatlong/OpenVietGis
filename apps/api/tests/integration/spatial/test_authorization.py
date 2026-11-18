"""US4 T043 spatial authorization acceptance via restricted HTTP.

Only the security setup and read-only state oracle use existing integration
fixtures; no product operation is executed with the database owner role.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import AccessWorld, seed_access_world
from tests.integration.service_identity.test_service_authorization import _service_client
from tests.integration.spatial.test_features import _setup
from tests.integration.spatial.test_layers import _counts
from tests.integration.spatial.test_sources import _client, _register
from tests.integration.spatial.test_sources import _path as _source_path


@dataclass(frozen=True)
class Catalog:
    world: AccessWorld
    source_id: str
    retire_source_id: str
    layer_id: str
    feature_id: str
    pins: dict


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    permission: str
    kwargs: dict
    success_status: int = 200

    def send(self, client: TestClient, root: str):
        response = client.request(self.method, root + self.path, **self.kwargs)
        return response


def _org(world: AccessWorld) -> str:
    return f"/api/v1/organizations/{world.organization_id}"


def _root(world: AccessWorld) -> str:
    return f"{_org(world)}/projects/{world.project_id}"


def _catalog(owner: TestClient, world: AccessWorld, key: str) -> Catalog:
    path, source, layer, pins = _setup(owner, world, key)
    page = owner.get(path, params={**pins, "limit": 1})
    assert page.status_code == 200, page.text
    feature_id = page.json()["items"][0]["feature_id"]
    retire_source_id = _register(
        owner, _source_path(world), "reference_empty_4326", "Independent source"
    )["resource_id"]
    return Catalog(world, source["id"], retire_source_id, layer, feature_id, pins)


def _sibling(owner: TestClient, world: AccessWorld) -> AccessWorld:
    response = owner.post(
        f"{_org(world)}/projects",
        json={
            "name": "Second project",
            "slug": f"us4-{uuid4().hex}",
            "workspace_id": str(world.workspace_a_id),
        },
    )
    assert response.status_code == 201, response.text
    return replace(world, project_id=UUID(response.json()["id"]))


def _grant(owner: TestClient, world: AccessWorld, kind: str, subject_id: str, role: str) -> str:
    response = owner.post(
        f"{_org(world)}/grants",
        json={
            "subject_kind": kind,
            "subject_id": subject_id,
            "scope_kind": "project",
            "project_id": str(world.project_id),
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _principal(owner: TestClient, world: AccessWorld) -> str:
    response = owner.post(
        f"{_org(world)}/service-principals", json={"name": "Spatial authorization"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _credential(
    owner: TestClient, world: AccessWorld, principal_id: str, permissions: list[str]
) -> tuple[str, str]:
    response = owner.post(
        f"{_org(world)}/service-principals/{principal_id}/credentials",
        json={"name": f"ceiling-{uuid4().hex}", "permission_ceiling": permissions},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], response.json()["secret"]


def _calls(catalog: Catalog) -> tuple[Call, ...]:
    src = "/spatial/sources"
    source = f"{src}/{catalog.source_id}"
    layer = f"/layers/{catalog.layer_id}"
    feature = f"{layer}/features"
    read, edit, manage = "project.read", "project.edit", "project.manage"
    patch = {"json": {"expected_revision": 1, "name": "Renamed by actor"}}
    retire = {"json": {"expected_revision": 1}}
    return (
        Call("GET", src, read, {}),
        Call(
            "POST",
            src,
            edit,
            {"json": {"reference_key": "reference_unknown_crs", "name": "New source"}},
            201,
        ),
        Call("GET", source, read, {}),
        Call("PATCH", source, edit, patch),
        Call("POST", f"{src}/{catalog.retire_source_id}/retire", manage, retire),
        Call("GET", "/layers", read, {}),
        Call(
            "POST",
            "/layers",
            edit,
            {"json": {"source_id": catalog.source_id, "name": "New layer"}},
            201,
        ),
        Call("GET", layer, read, {}),
        Call("PATCH", layer, edit, patch),
        Call("POST", f"{layer}/retire", edit, {"json": {"expected_revision": 2}}),
        Call("GET", feature, read, {"params": {**catalog.pins, "limit": 1}}),
        Call("GET", f"{feature}/{catalog.feature_id}", read, {"params": catalog.pins}),
    )


def _history() -> Call:
    return Call("GET", "/spatial/changes", "project.read", {"params": {"limit": 10}})


def _snapshot(*catalogs: Catalog) -> tuple:
    # Compare committed catalog rows AND success evidence, not just HTTP status.
    # Audit security-denial events and auth last-use bookkeeping may legitimately
    # change; neither is a successful spatial mutation.
    snapshots = []
    for catalog in catalogs:
        world = catalog.world
        with get_admin_engine().connect() as connection:
            params = {"project": world.project_id, "org": world.organization_id}
            snapshots.append(
                tuple(
                    connection.execute(
                        text(
                            f"SELECT to_jsonb(t) FROM spatial.{table} t "
                            "WHERE project_id=:project AND organization_id=:org "
                            "ORDER BY to_jsonb(t)::text"
                        ),
                        params,
                    )
                    .scalars()
                    .all()
                    for table in (
                        "data_sources",
                        "source_fields",
                        "reference_features",
                        "layers",
                        "catalog_changes",
                    )
                )
            )
        snapshots.append(_counts(world))
    return tuple(snapshots)


def _denied(call: Call, actor: TestClient, root: str, status: int, detail: str | None) -> None:
    response = call.send(actor, root)
    if detail is None:
        detail = f"missing permission: {call.permission}"
    assert response.status_code == status, (call, response.text)
    assert response.json() == {"detail": detail}, (call, response.text)


def _concealed(call: Call, actor: TestClient, root: str, absent: Call, absent_root: str) -> None:
    actual = call.send(actor, root)
    missing = absent.send(actor, absent_root)
    assert actual.status_code == missing.status_code == 404, (call, actual.text, missing.text)
    if root == absent_root:
        detail = "resource not found"
    elif root.split("/")[4] == absent_root.split("/")[4]:
        detail = "project not found"
    else:
        detail = "organization not found"
    assert actual.json() == missing.json() == {"detail": detail}


def _negative_calls(catalog: Catalog) -> tuple[Call, ...]:
    absent = replace(
        catalog,
        source_id=str(uuid4()),
        retire_source_id=str(uuid4()),
        layer_id=str(uuid4()),
        feature_id=f"absent-{uuid4().hex}",
    )
    source = f"/spatial/sources/{catalog.source_id}"
    features = f"/layers/{catalog.layer_id}/features"
    stale_pins = dict(catalog.pins)
    stale_pins["content_revision"] = "0" * 64
    assert stale_pins != catalog.pins
    return (
        _calls(catalog)
        + _calls(absent)
        + (
            Call(
                "POST",
                "/spatial/sources",
                "project.edit",
                {"json": {"reference_key": "reference_points_5899", "name": "Duplicate"}},
            ),
            Call(
                "POST",
                "/spatial/sources",
                "project.edit",
                {"json": {"reference_key": "unknown_fixture", "name": "Unknown"}},
            ),
            Call(
                "PATCH",
                source,
                "project.edit",
                {"json": {"expected_revision": 999, "name": "Stale revision"}},
            ),
            Call("POST", source + "/retire", "project.manage", {"json": {"expected_revision": 1}}),
            Call("GET", features, "project.read", {"params": stale_pins}),
            Call(
                "GET", features + "/" + catalog.feature_id, "project.read", {"params": stale_pins}
            ),
            Call(
                "GET",
                features,
                "project.read",
                {"params": {**catalog.pins, "after_feature_id": absent.feature_id}},
            ),
        )
    )


def _check_all_denied(actor: TestClient, catalog: Catalog, status: int, detail: str | None) -> None:
    before = _snapshot(catalog)
    for call in _negative_calls(catalog):
        _denied(call, actor, _root(catalog.world), status, detail)
    assert _snapshot(catalog) == before


def _check_reads(actor: TestClient, catalog: Catalog) -> None:
    for call in _calls(catalog):
        if call.method == "GET":
            response = call.send(actor, _root(catalog.world))
            assert response.status_code == 200, (call, response.text)


@pytest.mark.parametrize("membership_status", ["suspended", "revoked"])
def test_human_current_membership_and_grant(
    migrated_database: None, membership_status: str
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as member:
        catalog = _catalog(owner, world, "reference_points_5899")
        _check_all_denied(member, catalog, 403, None)

        grant = _grant(owner, world, "membership", str(world.member_membership_id), "viewer")
        _check_reads(member, catalog)
        before = _snapshot(catalog)
        for call in _calls(catalog):
            if call.method != "GET":
                _denied(call, member, _root(world), 403, None)
        assert _snapshot(catalog) == before

        assert owner.post(f"{_org(world)}/grants/{grant}/revoke").status_code == 204
        _check_all_denied(member, catalog, 403, None)

        _grant(owner, world, "membership", str(world.member_membership_id), "manager")
        _check_reads(member, catalog)
        changed = owner.patch(
            f"{_org(world)}/members/{world.member_membership_id}",
            json={"status": membership_status},
        )
        assert changed.status_code == 200, changed.text
        before = _snapshot(catalog)
        absent_root = f"/api/v1/organizations/{uuid4()}/projects/{uuid4()}"
        for call in _calls(catalog):
            _concealed(call, member, _root(world), call, absent_root)
        assert _snapshot(catalog) == before
        assert member.get("/api/v1/me").status_code == 200


def test_service_current_grant_and_credential_ceiling(migrated_database: None) -> None:
    world = seed_access_world()
    root = _root(world)
    with _client(world.owner_user_id) as owner:
        catalog = _catalog(owner, world, "reference_points_5899")
        principal = _principal(owner, world)
        grant = _grant(owner, world, "service_principal", principal, "manager")
        _, read_secret = _credential(owner, world, principal, ["project.read"])
        _, edit_secret = _credential(owner, world, principal, ["project.edit"])
        credential, full_secret = _credential(
            owner, world, principal, ["project.read", "project.edit", "project.manage"]
        )
        with _service_client(read_secret) as reader:
            _check_reads(reader, catalog)
            before = _snapshot(catalog)
            for call in _calls(catalog):
                if call.method != "GET":
                    _denied(call, reader, root, 403, None)
            assert _snapshot(catalog) == before

        # Permission ceiling is intersected with the current effective grant.
        # A bearer needs no CSRF; project.edit permits exactly the edit routes.
        with _service_client(edit_secret) as editor:
            before = _snapshot(catalog)
            for call in _calls(catalog):
                if call.permission != "project.edit":
                    _denied(call, editor, root, 403, None)
            assert _snapshot(catalog) == before

        # The same previously issued bearer loses access immediately on grant
        # revocation, even though its credential ceiling has not changed.
        with _service_client(full_secret) as service:
            _check_reads(service, catalog)
            assert owner.post(f"{_org(world)}/grants/{grant}/revoke").status_code == 204
            _check_all_denied(service, catalog, 403, None)
            revoked = owner.post(
                f"{_org(world)}/service-principals/{principal}/credentials/{credential}/revoke"
            )
            assert revoked.status_code == 204, revoked.text
            _check_all_denied(service, catalog, 401, "invalid service credential")


def test_human_csrf_all_mutations_and_bearer_edit_control(migrated_database: None) -> None:
    world = seed_access_world()
    root = _root(world)
    with _client(world.owner_user_id) as owner, _client(world.owner_user_id) as human:
        catalog = _catalog(owner, world, "reference_points_5899")
        human.headers.pop("X-OpenVietGIS-CSRF")
        _check_reads(human, catalog)
        before = _snapshot(catalog)
        for call in _calls(catalog):
            if call.method != "GET":
                _denied(call, human, root, 403, "CSRF validation failed")
        human.headers["X-OpenVietGIS-CSRF"] = "invalid"
        for call in _calls(catalog):
            if call.method != "GET":
                _denied(call, human, root, 403, "CSRF validation failed")
        assert _snapshot(catalog) == before

        principal = _principal(owner, world)
        _grant(owner, world, "service_principal", principal, "manager")
        _, secret = _credential(owner, world, principal, ["project.edit"])
        with _service_client(secret) as service:
            _denied(_calls(catalog)[4], service, root, 403, None)
            for call in _calls(catalog):
                if call.permission == "project.edit":
                    response = call.send(service, root)
                    assert response.status_code == call.success_status, (call, response.text)


def _substitutions(target: Catalog, foreign: Catalog) -> list[tuple[Call, Call]]:
    absent = replace(
        foreign,
        source_id=str(uuid4()),
        retire_source_id=str(uuid4()),
        layer_id=str(uuid4()),
        feature_id=f"missing-{uuid4().hex}",
    )
    pairs = [
        (wrong, missing)
        for wrong, missing in zip(_calls(foreign), _calls(absent), strict=True)
        if wrong.path != missing.path or wrong.kwargs != missing.kwargs
    ]
    own_feature = f"/layers/{target.layer_id}/features"
    pairs.append(
        (
            Call(
                "GET",
                f"{own_feature}/{foreign.feature_id}",
                "project.read",
                {"params": target.pins},
            ),
            Call(
                "GET", f"{own_feature}/{absent.feature_id}", "project.read", {"params": target.pins}
            ),
        )
    )
    return pairs


@pytest.mark.parametrize("actor_kind", ["human", "service"])
def test_scope_substitution_and_dual_authorized_cross_project_creation(
    migrated_database: None, actor_kind: str
) -> None:
    world, other_org = seed_access_world(), seed_access_world()
    with _client(world.owner_user_id) as owner, _client(other_org.owner_user_id) as other_owner:
        sibling = _sibling(owner, world)
        own = _catalog(owner, world, "reference_points_5899")
        sibling_catalog = _catalog(owner, sibling, "reference_points_3857")
        other = _catalog(other_owner, other_org, "reference_points_3857")
        assert own.feature_id != sibling_catalog.feature_id
        if actor_kind == "human":
            for scope in (world, sibling):
                _grant(owner, scope, "membership", str(world.member_membership_id), "manager")
            actor = _client(world.member_user_id)
        else:
            principal = _principal(owner, world)
            for scope in (world, sibling):
                _grant(owner, scope, "service_principal", principal, "manager")
            _, secret = _credential(
                owner, world, principal, ["project.read", "project.edit", "project.manage"]
            )
            actor = _service_client(secret)
        with actor:
            _check_reads(actor, own)
            _check_reads(actor, sibling_catalog)
            before = _snapshot(own, sibling_catalog, other)
            absent_project = f"{_org(world)}/projects/{uuid4()}"
            wrong_project = f"{_org(world)}/projects/{other_org.project_id}"
            absent_tenant = f"/api/v1/organizations/{uuid4()}/projects/{uuid4()}"
            for call in _calls(other):
                _concealed(call, actor, wrong_project, call, absent_project)
                if actor_kind == "service":
                    _denied(call, actor, _root(other_org), 401, "invalid service credential")
                    _denied(call, actor, absent_tenant, 401, "invalid service credential")
                else:
                    _concealed(call, actor, _root(other_org), call, absent_tenant)
            # A broad grant in BOTH projects is no authority to combine their
            # resources. In particular POST /layers may never bind foreign source_id.
            for target, foreign in ((own, sibling_catalog), (sibling_catalog, own), (own, other)):
                for wrong, missing in _substitutions(target, foreign):
                    _concealed(wrong, actor, _root(target.world), missing, _root(target.world))
            assert _snapshot(own, sibling_catalog, other) == before


@pytest.mark.parametrize("actor_kind", ["human", "service"])
def test_change_history_rechecks_current_read_and_scope(
    migrated_database: None, actor_kind: str
) -> None:
    world, other_org = seed_access_world(), seed_access_world()
    call = _history()
    with _client(world.owner_user_id) as owner, _client(other_org.owner_user_id) as other_owner:
        sibling = _sibling(owner, world)
        catalog = _catalog(owner, world, "reference_points_5899")
        sibling_catalog = _catalog(owner, sibling, "reference_points_3857")
        other = _catalog(other_owner, other_org, "reference_points_3857")
        root = _root(world)
        if actor_kind == "human":
            actor = _client(world.member_user_id)
            with actor:
                _denied(call, actor, root, 403, None)
            actor = _client(world.member_user_id)
            grant = _grant(owner, world, "membership", str(world.member_membership_id), "viewer")
            _grant(owner, sibling, "membership", str(world.member_membership_id), "viewer")
        else:
            principal = _principal(owner, world)
            grant = _grant(owner, world, "service_principal", principal, "manager")
            _grant(owner, sibling, "service_principal", principal, "manager")
            _, edit_secret = _credential(owner, world, principal, ["project.edit"])
            with _service_client(edit_secret) as editor:
                _denied(call, editor, root, 403, None)
            credential_id, secret = _credential(owner, world, principal, ["project.read"])
            actor = _service_client(secret)
        with actor:
            before = _snapshot(catalog, sibling_catalog, other)
            for expected in (catalog, sibling_catalog):
                response = call.send(actor, _root(expected.world))
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["organization_id"] == str(world.organization_id)
                assert body["project_id"] == str(expected.world.project_id)
                assert len(body["items"]) == 3
                assert {item["resource_id"] for item in body["items"]} == {
                    expected.source_id,
                    expected.retire_source_id,
                    expected.layer_id,
                }
            absent_tenant = f"/api/v1/organizations/{uuid4()}/projects/{uuid4()}"
            if actor_kind == "service":
                _denied(call, actor, _root(other_org), 401, "invalid service credential")
            else:
                _concealed(call, actor, _root(other_org), call, absent_tenant)
            _concealed(
                call,
                actor,
                f"{_org(world)}/projects/{other_org.project_id}",
                call,
                f"{_org(world)}/projects/{uuid4()}",
            )
            assert owner.post(f"{_org(world)}/grants/{grant}/revoke").status_code == 204
            _denied(call, actor, root, 403, None)
            if actor_kind == "human":
                response = owner.patch(
                    f"{_org(world)}/members/{world.member_membership_id}",
                    json={"status": "suspended"},
                )
                assert response.status_code == 200, response.text
                _concealed(call, actor, root, call, absent_tenant)
            else:
                response = owner.post(
                    f"{_org(world)}/service-principals/{principal}/credentials/"
                    f"{credential_id}/revoke"
                )
                assert response.status_code == 204, response.text
                _denied(call, actor, root, 401, "invalid service credential")
            assert _snapshot(catalog, sibling_catalog, other) == before
