"""Real runtime roles and exact revision-chain collaboration evidence."""

from __future__ import annotations

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_authorization import _grant
from tests.integration.spatial.test_sources import _client


def test_replay_actor_and_rebase_exact_history(migrated_database):
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    base = f"{org}/projects/{world.project_id}"
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as member:
        imported = _import_geojson(
            owner,
            world,
            "rebase.geojson",
            [
                {
                    "type": "Feature",
                    "id": fid,
                    "properties": {"status": "old"},
                    "geometry": {"type": "Point", "coordinates": [105.8 + idx * 0.01, 21]},
                }
                for idx, fid in enumerate(["p1", "p2", "p3"])
            ],
            "Revision points",
            "rebase-import",
        )
        rev0 = imported["source_content_revision"]
        path = f"{base}/sources/{imported['target_source_id']}"
        edit1 = {
            "base_content_revision": rev0,
            "operation_id": "first",
            "summary": "First",
            "operations": [
                {"op_type": "update", "feature_id": "p1", "properties": {"status": "first"}},
            ],
        }
        one = owner.post(f"{path}/changesets", json=edit1)
        assert one.status_code == 201, one.text
        rev1 = one.json()["resulting_content_revision"]
        pending = {
            "base_content_revision": rev1,
            "draft_operations": [
                {"op_type": "update", "feature_id": "p1"},
                {"op_type": "update", "feature_id": "p2"},
                {"op_type": "create", "feature_id": "p3"},
                {"op_type": "update", "feature_id": "missing"},
                {"op_type": "create", "feature_id": "new"},
            ],
        }
        assert member.post(f"{path}/conflict-rebase", json=pending).status_code in (403, 404)
        _grant(owner, world, "membership", str(world.member_membership_id), "editor")
        stolen = member.post(f"{path}/changesets", json=edit1)
        assert stolen.status_code == 409, stolen.text
        assert stolen.json()["code"] == "OPERATION_ID_CONFLICT"
        assert owner.post(f"{path}/changesets", json=edit1).json()["id"] == one.json()["id"]
        edit2 = {
            "base_content_revision": rev1,
            "operation_id": "second",
            "summary": "Second",
            "operations": [
                {"op_type": "update", "feature_id": "p2", "properties": {"status": "second"}},
            ],
        }
        two = member.post(f"{path}/changesets", json=edit2)
        assert two.status_code == 201, two.text
        rev2 = two.json()["resulting_content_revision"]
        report = owner.post(f"{path}/conflict-rebase", json=pending)
        assert report.status_code == 200, report.text
        data = report.json()
        assert data["current_content_revision"] == rev2
        assert [op["feature_id"] for op in data["reapplicable_operations"]] == ["p1", "new"]
        assert {op["feature_id"] for op in data["conflicts"]} == {"p2", "p3", "missing"}
        current = owner.post(
            f"{path}/conflict-rebase",
            json={**pending, "base_content_revision": rev2},
        )
        assert current.status_code == 200, current.text
        assert [op["feature_id"] for op in current.json()["reapplicable_operations"]] == [
            "p1",
            "p2",
            "new",
        ]
        oldest = owner.post(
            f"{path}/conflict-rebase",
            json={**pending, "base_content_revision": rev0},
        )
        assert oldest.status_code == 200, oldest.text
        assert {op["feature_id"] for op in oldest.json()["conflicts"]} == {
            "p1",
            "p2",
            "p3",
            "missing",
        }
        unknown = owner.post(
            f"{path}/conflict-rebase",
            json={**pending, "base_content_revision": "f" * 64},
        )
        assert unknown.status_code == 409, unknown.text
        assert unknown.json()["code"] == "REBASE_HISTORY_UNAVAILABLE"
        assert (
            owner.post(
                f"{path}/conflict-rebase",
                json={
                    **pending,
                    "draft_operations": [
                        {"op_type": "create", "feature_id": "new"},
                        {"op_type": "update", "feature_id": "new"},
                    ],
                },
            ).status_code
            == 422
        )
        review = owner.post(
            f"{base}/collaboration/reviews",
            json={
                "changeset_id": one.json()["id"],
                "assignee_user_id": str(world.member_user_id),
            },
        )
        assert review.status_code == 201, review.text
        comments = f"{base}/collaboration/reviews/{review.json()['id']}/comments"
        invalid = member.post(comments, json={"feature_id": "p2", "body": "wrong anchor"})
        assert invalid.status_code == 422, invalid.text
        valid = member.post(comments, json={"feature_id": "p1", "body": "old revision anchor"})
        assert valid.status_code == 201, valid.text
        assert valid.json()["content_revision"] == rev1
        assert len(owner.get(comments).json()["items"]) == 1
