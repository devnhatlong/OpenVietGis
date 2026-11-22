"""Identified offline intent receives scoped Core feature identity and exact receipts."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_sources import _client


def test_identified_group_receipt_replay_and_scope(migrated_database: None, monkeypatch) -> None:
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    base = f"{org}/projects/{world.project_id}"
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as member:
        imported = _import_geojson(
            owner,
            world,
            "r013-identified.geojson",
            [
                {
                    "type": "Feature",
                    "id": "base_point",
                    "properties": {"name": "old"},
                    "geometry": {"type": "Point", "coordinates": [105.5, 20.5]},
                }
            ],
            "R013 identified",
            str(uuid4()),
        )
        layer = imported["target_layer_id"]
        source = imported["target_source_id"]
        granted = owner.post(
            f"{org}/grants",
            json={
                "subject_kind": "membership",
                "subject_id": str(world.member_membership_id),
                "scope_kind": "project",
                "project_id": str(world.project_id),
                "role": "editor",
            },
        )
        assert granted.status_code == 201, granted.text

        def issue(client):
            response = client.post(
                f"{base}/field/packages",
                json={
                    "name": "Identified pack",
                    "layer_id": layer,
                    "aoi_bbox": {"min_x": 105, "min_y": 20, "max_x": 106, "max_y": 21},
                    "local_storage_confirmed": True,
                },
            )
            assert response.status_code == 201, response.text
            return response.json()["id"]

        def sync(client, package, body):
            return client.post(f"{base}/field/packages/{package}/sync", json=body)

        def read_features():
            pins = owner.get(f"{base}/layers/{layer}").json()["source"]
            response = owner.get(
                f"{base}/layers/{layer}/features",
                params={key: pins[key] for key in ("content_revision", "schema_revision")},
            )
            assert response.status_code == 200, response.text
            return pins["content_revision"], {
                f["feature_id"]: f["attributes"] for f in response.json()["items"]
            }

        package_a = issue(owner)
        update = {
            "op_type": "update",
            "feature_id": "base_point",
            "properties": {"name": "offline update"},
            "client_operation_id": str(uuid4()),
        }
        create = {
            "op_type": "create",
            "feature_id": "draft-feature",
            "properties": {"name": "offline capture"},
            "geometry": {"type": "Point", "coordinates": [105.6, 20.6]},
            "client_operation_id": str(uuid4()),
        }
        group = {"operation_id": str(uuid4()), "operations": [update, create]}
        duplicate = sync(
            owner,
            package_a,
            {
                **group,
                "operations": [
                    update,
                    {**create, "client_operation_id": update["client_operation_id"]},
                ],
            },
        )
        assert duplicate.status_code == 422, duplicate.text
        assert duplicate.json()["code"] == "INVALID_OFFLINE_OPERATION_ID"

        denied = sync(member, package_a, group)
        assert denied.status_code == 404, denied.text
        # Precisely interrupt after Core commits but before the field receipt is
        # inserted. A retry must discover the original Core commit, reconstruct
        # mapping and persist one field receipt without another mutation.
        original = Session.execute
        receipt_attempts = []

        def fail_field_receipt(session, statement, *args, **kwargs):
            if "INSERT INTO field.sync_batches" in str(statement):
                receipt_attempts.append(True)
                raise RuntimeError("synthetic receipt interruption")
            return original(session, statement, *args, **kwargs)

        with _client(world.owner_user_id, raise_server_exceptions=False) as interrupted:
            with monkeypatch.context() as scoped:
                scoped.setattr(Session, "execute", fail_field_receipt)
                failed = sync(interrupted, package_a, group)
        assert failed.status_code == 500, failed.text
        assert receipt_attempts == [True]
        committed_before_receipt = read_features()
        assert len(committed_before_receipt[1]) == 2
        applied = sync(owner, package_a, group)
        assert applied.status_code == 201, applied.text
        payload = applied.json()
        assert payload["status"] == "applied"
        (cs_id,) = payload["applied_changeset_ids"]
        updated, captured = payload["operation_receipts"]
        core_id = captured["core_feature_id"]
        assert core_id.startswith("field-core-") and core_id != create["feature_id"]
        assert updated == {
            "client_operation_id": update["client_operation_id"],
            "local_feature_id": update["feature_id"],
            "core_feature_id": update["feature_id"],
            "status": "applied",
            "changeset_id": cs_id,
        }
        assert captured == {
            "client_operation_id": create["client_operation_id"],
            "local_feature_id": create["feature_id"],
            "core_feature_id": core_id,
            "status": "applied",
            "changeset_id": cs_id,
        }
        first = read_features()
        assert first == committed_before_receipt
        assert first[1] == {
            "base_point": {"name": "offline update"},
            core_id: {"name": "offline capture"},
        }
        changeset = owner.get(f"{base}/changesets/{cs_id}")
        assert changeset.status_code == 200, changeset.text
        assert {op["feature_id"] for op in changeset.json()["operations"]} == {
            "base_point",
            core_id,
        }

        exact = sync(owner, package_a, group)
        assert exact.status_code == 201, exact.text
        assert exact.json() == payload
        assert read_features() == first
        for changed in (
            {**create, "client_operation_id": str(uuid4())},
            {**create, "feature_id": "changed-local-label"},
        ):
            replay = sync(owner, package_a, {**group, "operations": [update, changed]})
            assert replay.status_code == 409, replay.text
            assert read_features() == first

        stale = sync(owner, package_a, {"operation_id": str(uuid4()), "operations": [create]})
        assert stale.status_code == 201, stale.text
        assert stale.json()["status"] == "conflict"
        assert stale.json()["operation_receipts"] == [
            {
                **captured,
                "core_feature_id": None,
                "status": "not_applied",
                "changeset_id": None,
            }
        ]
        assert read_features() == first

        # The same local label/operation UUID on a fresh package is a different
        # scoped capture, not a way to overwrite the original Core feature.
        package_b = issue(owner)
        scoped = sync(owner, package_b, {**group, "operations": [create]})
        assert scoped.status_code == 201, scoped.text
        assert scoped.json()["status"] == "applied"
        second_id = scoped.json()["operation_receipts"][0]["core_feature_id"]
        assert second_id != core_id
        package_c = issue(member)
        member_sync = sync(member, package_c, {**group, "operations": [create]})
        assert member_sync.status_code == 201, member_sync.text
        assert member_sync.json()["status"] == "applied"
        third_id = member_sync.json()["operation_receipts"][0]["core_feature_id"]
        assert third_id not in (core_id, second_id)
        final = read_features()
        assert set(final[1]) == {"base_point", core_id, second_id, third_id}
        assert source  # the same Core source was read throughout

        revoked = owner.post(f"{base}/field/packages/{package_a}/revoke")
        assert revoked.status_code == 200, revoked.text
        assert sync(owner, package_a, group).status_code == 403
        assert read_features() == final
