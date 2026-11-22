"""R011 real scoped immutable edit/review projection, stable cutoff, replay."""

from __future__ import annotations

import base64
import json
from uuid import uuid4

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_authorization import _grant
from tests.integration.spatial.test_sources import _client


def test_fifty_commits_two_actor_activity_cutoff_and_comment_replay(migrated_database):
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    base = f"{org}/projects/{world.project_id}"
    endpoint = f"{base}/collaboration/activities"
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as member:
        grant = _grant(owner, world, "membership", str(world.member_membership_id), "editor")
        imported = _import_geojson(
            owner,
            world,
            "activities.geojson",
            [
                {
                    "type": "Feature",
                    "id": "p1",
                    "properties": {"status": "initial"},
                    "geometry": {"type": "Point", "coordinates": [105.8, 21]},
                }
            ],
            "Activity points",
            "activity-import",
        )
        source = imported["target_source_id"]
        edit_url = f"{base}/sources/{source}/changesets"
        rev = imported["source_content_revision"]
        expected = {}

        def commit(index, client, actor):
            nonlocal rev
            body = {
                "base_content_revision": rev,
                "operation_id": f"activity-{index}",
                "summary": f"Actual edit {index}",
                "operations": [
                    {
                        "op_type": "update",
                        "feature_id": "p1",
                        "properties": {"status": f"edited-{index}"},
                    }
                ],
            }
            response = client.post(edit_url, json=body)
            assert response.status_code == 201, response.text
            item = response.json()
            rev = item["resulting_content_revision"]
            expected[item["id"]] = (
                str(actor),
                rev,
                body["base_content_revision"],
                body["summary"],
            )
            # Exact replay is not a duplicate committed edit event.
            if index == 0:
                repeated = client.post(edit_url, json=body)
                assert repeated.status_code == 201
                assert repeated.json()["id"] == item["id"]
            return item["id"]

        for i in range(50):
            commit(
                i,
                owner if i % 2 == 0 else member,
                world.owner_user_id if i % 2 == 0 else world.member_user_id,
            )
        # Stale edit never appears in the committed projection.
        denied = owner.post(
            edit_url,
            json={
                "base_content_revision": imported["source_content_revision"],
                "operation_id": "abandoned",
                "summary": "Abandoned stale draft",
                "operations": [{"op_type": "delete", "feature_id": "p1"}],
            },
        )
        assert denied.status_code == 409
        first_change = next(iter(expected))
        review = owner.post(
            f"{base}/collaboration/reviews",
            json={
                "changeset_id": first_change,
                "assignee_user_id": str(world.member_user_id),
            },
        )
        assert review.status_code == 201, review.text
        rid = review.json()["id"]
        comment_path = f"{base}/collaboration/reviews/{rid}/comments"
        original = {"body": "Exact comment", "feature_id": "p1", "operation_id": str(uuid4())}
        commented = member.post(comment_path, json=original)
        assert commented.status_code == 201, commented.text
        repeated = member.post(comment_path, json={**original, "body": " Exact comment "})
        assert repeated.status_code == 201 and repeated.json() == commented.json()
        mismatch = member.post(comment_path, json={**original, "body": "Different intent"})
        assert mismatch.status_code == 409
        assert mismatch.json()["code"] == "COMMENT_OPERATION_CONFLICT"
        # Same client operation ID elsewhere belongs to a different actor.
        other_comment = owner.post(comment_path, json=original)
        assert other_comment.status_code == 201
        assert other_comment.json()["id"] != commented.json()["id"]
        listed = member.get(comment_path)
        assert listed.status_code == 200
        assert {r["id"] for r in listed.json()["items"]} == {
            commented.json()["id"],
            other_comment.json()["id"],
        }
        decided = member.post(
            f"{base}/collaboration/reviews/{rid}/decide", json={"status": "approved"}
        )
        assert decided.status_code == 200

        first = member.get(endpoint, params={"limit": 7})
        assert first.status_code == 200, first.text
        assert first.headers["cache-control"] == "no-store"
        page = first.json()
        cutoff = page["cutoff"]
        token = page["next_cursor"]
        assert token
        seen = page["items"]
        assert owner.get(endpoint, params={"cursor": token}).status_code == 422
        assert member.get(endpoint, params={"cursor": "not-a-cursor"}).status_code == 422
        # Even a canonical cursor with this actor's scope and a forged row
        # boundary must not be used.
        value = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        value[-1] = str(uuid4())
        forged = (
            base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode("ascii"))
            .decode("ascii")
            .rstrip("=")
        )
        assert member.get(endpoint, params={"cursor": forged}).status_code == 422

        late_change = commit(50, owner, world.owner_user_id)
        while token:
            response = member.get(endpoint, params={"cursor": token, "limit": 7})
            assert response.status_code == 200, response.text
            page = response.json()
            assert page["cutoff"] == cutoff
            assert len(page["items"]) <= 7
            seen.extend(page["items"])
            token = page["next_cursor"]
        assert len(seen) == 54  # 50 edits + request + two comments + disposition
        assert len({(r["event_kind"], r["id"]) for r in seen}) == len(seen)
        edits = [r for r in seen if r["event_kind"] == "changeset.committed"]
        assert {r["id"] for r in edits} == set(expected) - {late_change}
        for event in edits:
            actor, rev, base_rev, summary = expected[event["id"]]
            assert event["actor_id"] == actor
            assert event["revision_ref"] == rev
            assert event["summary"] == summary
            assert event["resource_id"] == event["id"]
            assert event["metadata"]["source_id"] == source
            assert event["metadata"]["base_content_revision"] == base_rev
        comments = [r for r in seen if r["event_kind"] == "review.commented"]
        assert {r["metadata"]["comment_id"] for r in comments} == {
            commented.json()["id"],
            other_comment.json()["id"],
        }
        assert all(
            r["revision_ref"] == expected[first_change][1]
            for r in seen
            if r["event_kind"].startswith("review.")
        )
        refreshed = member.get(endpoint, params={"limit": 7})
        assert refreshed.status_code == 200
        assert refreshed.json()["items"][0]["id"] == late_change
        stale_token = refreshed.json()["next_cursor"]
        assert stale_token
        assert owner.post(f"{org}/grants/{grant}/revoke").status_code == 204
        assert member.get(endpoint, params={"cursor": stale_token}).status_code in (403, 404)
        assert member.post(comment_path, json=original).status_code in (403, 404)
