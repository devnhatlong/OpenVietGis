"""Independent synthetic M3 lifecycle and cross-actor regression gates."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_authorization import _grant
from tests.integration.spatial.test_sources import _client


def test_extension_lifecycle_scope_and_retained_records(migrated_database):
    world = seed_access_world()
    other = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    base = f"{org}/projects/{world.project_id}"
    payload = {
        "extension_key": "audit_notes",
        "version": "1.0.0",
        "display_name": "Audit notes",
        "permissions": ["ext.audit_notes.read", "ext.audit_notes.write"],
        "entity_schemas": {"note": {"fields": {"text": {"type": "text", "required": True}}}},
    }
    record = {"entity_name": "note", "payload": {"text": "retained data"}}
    with (
        _client(world.owner_user_id) as owner,
        _client(world.member_user_id) as member,
        _client(other.owner_user_id) as outsider,
    ):
        _grant(owner, world, "membership", str(world.member_membership_id), "editor")
        forbidden = member.post(f"{org}/extensions/manifests", json=payload)
        assert forbidden.status_code == 403, forbidden.text
        manifest = owner.post(f"{org}/extensions/manifests", json=payload)
        assert manifest.status_code == 201, manifest.text
        mid = manifest.json()["id"]
        activation = {"manifest_id": mid}
        denied = member.post(f"{base}/extensions/activations", json=activation)
        assert denied.status_code == 403, denied.text
        act = owner.post(f"{base}/extensions/activations", json=activation)
        assert act.status_code == 201, act.text
        aid = act.json()["id"]
        records = f"{base}/extensions/audit_notes/records"
        outside = outsider.get(records)
        assert outside.status_code in (403, 404), outside.text
        bad_link = owner.post(records, json={**record, "linked_layer_id": str(uuid4())})
        assert bad_link.status_code == 404, bad_link.text
        dangling = owner.post(records, json={**record, "linked_feature_id": "unbound"})
        assert dangling.status_code == 422, dangling.text
        made = owner.post(records, json=record)
        assert made.status_code == 201, made.text
        replacement = owner.post(
            f"{org}/extensions/manifests", json={**payload, "version": "2.0.0"}
        )
        assert replacement.status_code == 201, replacement.text
        swap = owner.post(
            f"{base}/extensions/activations", json={"manifest_id": replacement.json()["id"]}
        )
        assert swap.status_code == 409, swap.text
        disable = f"{base}/extensions/activations/{aid}/deactivate"
        assert member.post(disable).status_code == 403
        disabled = owner.post(disable)
        assert disabled.status_code == 200 and disabled.json()["status"] == "disabled", (
            disabled.text
        )
        assert owner.post(records, json=record).status_code == 404
        # Retained records use Core-authorized data access, not module execution.
        retained = owner.get(records)
        assert retained.status_code == 200
        assert [r["id"] for r in retained.json()["items"]] == [made.json()["id"]]
        assert owner.get(f"{org}/projects/{world.project_id}").status_code == 200
        reactivate = owner.post(f"{base}/extensions/activations", json=activation)
        assert reactivate.status_code == 201 and reactivate.json()["id"] == aid


def test_legacy_manifest_mutation_block_preserves_authorized_retained_data(migrated_database):
    world = seed_access_world()
    other = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    base = f"{org}/projects/{world.project_id}/extensions"
    payload = {
        "extension_key": "retained_notes",
        "version": "1.0.0",
        "display_name": "Retained notes",
        "permissions": ["ext.retained_notes.read"],
        "commands": [
            {"id": "read", "label": "Read", "required_permission": "ext.retained_notes.read"}
        ],
        "entity_schemas": {"note": {"fields": {"text": {"type": "text", "required": True}}}},
    }
    record = {"entity_name": "note", "payload": {"text": "retained"}}
    with _client(world.owner_user_id) as owner, _client(other.owner_user_id) as outsider:
        registered = owner.post(f"{org}/extensions/manifests", json=payload)
        assert registered.status_code == 201, registered.text
        mid = registered.json()["id"]
        act = owner.post(f"{base}/activations", json={"manifest_id": mid})
        assert act.status_code == 201, act.text
        aid = act.json()["id"]
        records = f"{base}/retained_notes/records"
        made = owner.post(records, json=record)
        assert made.status_code == 201, made.text
        rid = made.json()["id"]
        successor = owner.post(f"{org}/extensions/manifests", json={**payload, "version": "1.1.0"})
        assert successor.status_code == 201, successor.text

        # Synthetic legacy registration: pre-strict-contract versions could
        # persist command metadata without required_permission. No execution.
        with get_admin_engine().begin() as conn:
            conn.execute(
                text(
                    "UPDATE extensions.manifests SET commands=CAST(:commands AS jsonb) "
                    "WHERE organization_id=:org AND id=:id"
                ),
                {
                    "commands": '[{"id":"read","label":"Read"}]',
                    "org": world.organization_id,
                    "id": mid,
                },
            )
        before = owner.get(f"{records}/{rid}/history")
        assert before.status_code == 200, before.text
        export = owner.get(f"{base}/retained_notes/portable-export")
        assert export.status_code == 200, export.text
        for denied in (
            owner.post(records, json=record),
            owner.put(
                f"{records}/{rid}",
                json={
                    "expected_revision": 1,
                    "expected_manifest_id": mid,
                    "payload": {"text": "changed"},
                },
            ),
            owner.post(
                f"{base}/retained_notes/portable-import",
                json={**export.json(), "expected_manifest_id": mid},
            ),
            owner.post(
                f"{base}/activations/{aid}/transition",
                json={"expected_manifest_id": mid, "target_manifest_id": successor.json()["id"]},
            ),
        ):
            assert denied.status_code == 409, denied.text
            assert denied.json()["code"] == "EXTENSION_MANIFEST_REVALIDATION_REQUIRED"

        # Command declarations are not an execution surface.
        assert owner.post(f"{base}/retained_notes/commands/read").status_code in (404, 405)
        assert owner.get(f"{records}/{rid}/history").json() == before.json()
        assert owner.get(records).json()["items"] == [made.json()]
        assert outsider.get(records).status_code in (403, 404)
        assert owner.post(f"{base}/activations/{aid}/deactivate").status_code == 200
        rejected = owner.post(f"{base}/activations", json={"manifest_id": mid})
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["code"] == "EXTENSION_MANIFEST_REVALIDATION_REQUIRED"
        retained = owner.get(f"{base}/retained_notes/portable-export")
        assert retained.status_code == 200, retained.text
        assert retained.json()["bundle"]["activation_status"] == "disabled"
        assert len(retained.json()["bundle"]["records"]) == 1
        assert retained.json()["bundle"]["records"][0]["payload"] == record["payload"]


def test_review_assignee_current_permission_and_immutable_decision(migrated_database):
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    base = f"{org}/projects/{world.project_id}"
    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as reviewer:
        imp = _import_geojson(
            owner,
            world,
            "review.geojson",
            [
                {
                    "type": "Feature",
                    "id": "p1",
                    "properties": {"status": "old"},
                    "geometry": {"type": "Point", "coordinates": [105.8, 21.0]},
                }
            ],
            "Review points",
            "review-import",
        )
        source = imp["target_source_id"]
        changes = owner.post(
            f"{base}/sources/{source}/changesets",
            json={
                "base_content_revision": imp["source_content_revision"],
                "operation_id": "review-edit",
                "summary": "Independent change",
                "operations": [
                    {"op_type": "update", "feature_id": "p1", "properties": {"status": "new"}}
                ],
            },
        )
        assert changes.status_code == 201, changes.text
        req = {"changeset_id": changes.json()["id"], "assignee_user_id": str(world.member_user_id)}
        reviews = f"{base}/collaboration/reviews"
        assert owner.post(reviews, json=req).status_code == 422
        reader_grant = _grant(owner, world, "membership", str(world.member_membership_id), "viewer")
        self_review = owner.post(
            reviews,
            json={**req, "assignee_user_id": str(world.owner_user_id)},
        )
        assert self_review.status_code == 201
        reader_review = f"{reviews}/{self_review.json()['id']}"
        assert reviewer.get(reviews).status_code == 200
        assert (
            reviewer.post(
                f"{reader_review}/comments",
                json={"body": "Viewer cannot mutate"},
            ).status_code
            == 403
        )
        assert owner.post(f"{org}/grants/{reader_grant}/revoke").status_code == 204
        grant = _grant(owner, world, "membership", str(world.member_membership_id), "editor")
        with get_admin_engine().begin() as conn:
            conn.execute(
                text("UPDATE identity.users SET status='disabled' WHERE id=:id"),
                {"id": world.member_user_id},
            )
        assert owner.post(reviews, json=req).status_code == 422
        with get_admin_engine().begin() as conn:
            conn.execute(
                text("UPDATE identity.users SET status='active' WHERE id=:id"),
                {"id": world.member_user_id},
            )
        created = owner.post(reviews, json=req)
        assert created.status_code == 201, created.text
        rid = created.json()["id"]
        decide = f"{reviews}/{rid}/decide"
        assert owner.post(decide, json={"status": "approved"}).status_code == 403
        comment = reviewer.post(f"{reviews}/{rid}/comments", json={"body": "Reviewed point"})
        assert comment.status_code == 201, comment.text
        assert comment.json()["author_actor_id"] == str(world.member_user_id)
        approved = reviewer.post(decide, json={"status": "approved", "decision_note": "Verified"})
        assert approved.status_code == 200, approved.text
        assert approved.json()["decided_by_actor_id"] == str(world.member_user_id)
        assert reviewer.post(decide, json={"status": "changes_requested"}).status_code == 409
        # Revocation removes current access despite a historical assignment.
        revoked = owner.post(f"{org}/grants/{grant}/revoke")
        assert revoked.status_code == 204, revoked.text
        assert reviewer.get(reviews).status_code in (403, 404)
        assert reviewer.post(f"{reviews}/{rid}/comments", json={"body": "Denied"}).status_code in (
            403,
            404,
        )
        assert reviewer.post(decide, json={"status": "approved"}).status_code in (403, 404)
