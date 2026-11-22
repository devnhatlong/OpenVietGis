"""Protect the schema pin and exact replay of editing drafts."""

from __future__ import annotations

from sqlalchemy import text

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_sources import _client


def test_stale_schema_fails_without_publication_and_pinned_replay_is_exact(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    project = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    with _client(world.owner_user_id) as client:
        imported = _import_geojson(
            client,
            world,
            "schema-pin.geojson",
            [
                {
                    "type": "Feature",
                    "id": "p1",
                    "properties": {"label": "before"},
                    "geometry": {"type": "Point", "coordinates": [105, 21]},
                }
            ],
            "Schema pin",
            "schema-pin-import",
        )
        source_id = imported["target_source_id"]
        source_url = f"{project}/spatial/sources/{source_id}"
        url = f"{project}/sources/{source_id}/changesets"
        before = client.get(source_url).json()
        schema = before["schema_revision"]
        stale = "f" * 64 if schema != "f" * 64 else "a" * 64
        body = {
            "base_content_revision": before["content_revision"],
            "base_schema_revision": stale,
            "operation_id": "schema-pin",
            "operations": [
                {"op_type": "update", "feature_id": "p1", "properties": {"label": "after"}}
            ],
        }
        refused = client.post(url, json=body)
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "STALE_SCHEMA_REVISION"
        assert refused.json()["details"]["current_schema_revision"] == schema
        assert client.get(source_url).json() == before
        assert client.get(url).json()["items"] == []
        pinned = {**body, "base_schema_revision": schema}
        committed = client.post(url, json=pinned)
        assert committed.status_code == 201, committed.text
        receipt = committed.json()
        assert client.post(url, json=pinned).json() == receipt
        for changed in (body, {k: v for k, v in pinned.items() if k != "base_schema_revision"}):
            result = client.post(url, json=changed)
            assert result.status_code == 409
            assert result.json()["code"] == "OPERATION_ID_CONFLICT"
        assert len(client.get(url).json()["items"]) == 1
        assert client.get(source_url).json()["schema_revision"] == schema
        with get_admin_engine().connect() as connection:
            metadata = connection.execute(
                text("SELECT metadata FROM audit.audit_events WHERE id=:id"),
                {"id": receipt["audit_event_id"]},
            ).scalar_one()
        assert metadata["base_schema_revision"] == metadata["submitted_schema_revision"] == schema
