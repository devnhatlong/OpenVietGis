"""Regression: an optimized viewport read must not reuse stale or unauthorized data."""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_authorization import _grant, _org, _root
from tests.integration.spatial.test_sources import _client


def test_warmed_viewport_and_extent_recheck_live_pins_and_actor(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    base = _root(world)
    bbox = {"west": 105.0, "south": 20.0, "east": 106.0, "north": 22.0}

    with _client(world.owner_user_id) as owner, _client(world.member_user_id) as member:
        imported = _import_geojson(
            owner,
            world,
            "warm-pins.geojson",
            [
                {
                    "type": "Feature",
                    "id": "warm-point",
                    "properties": {"name": "Current feature"},
                    "geometry": {"type": "Point", "coordinates": [105.81, 21.01]},
                }
            ],
            "Warm revision regression",
            str(uuid4()),
        )
        layer = imported["target_layer_id"]
        source_id = imported["target_source_id"]
        endpoint = base + f"/layers/{layer}"
        source = owner.get(endpoint).json()["source"]
        original = {key: source[key] for key in ("content_revision", "schema_revision")}
        grant = _grant(owner, world, "membership", str(world.member_membership_id), "viewer")

        def reads(pins):
            return (
                (endpoint + "/viewport", {**pins, **bbox}),
                (endpoint + "/display-extent", pins),
            )

        # Warm the identical URL/pins in both actors' authenticated sessions.
        for actor in (owner, member, owner, member):
            viewport, extent = [actor.get(url, params=params) for url, params in reads(original)]
            for response in (viewport, extent):
                assert response.status_code == 200, response.text
                assert response.headers["cache-control"] == "no-store"
            wire = viewport.json()
            assert wire["complete"] is True
            assert wire["context"]["content_revision"] == original["content_revision"]
            assert wire["items"][0]["geometry"]["coordinates"] == pytest.approx([105.81, 21.01])
            assert extent.json()["bounds"] == pytest.approx([105.81, 21.01, 105.81, 21.01])

        # A real Core geometry update changes the content pin but not the schema pin.
        committed = owner.post(
            base + f"/sources/{source_id}/changesets",
            json={
                "base_content_revision": original["content_revision"],
                "operation_id": str(uuid4()),
                "operations": [
                    {
                        "op_type": "update",
                        "feature_id": "warm-point",
                        "geometry": {"type": "Point", "coordinates": [105.91, 21.11]},
                        "properties": {"name": "Current feature"},
                    }
                ],
            },
        )
        assert committed.status_code == 201, committed.text
        updated = owner.get(endpoint).json()["source"]
        current = {key: updated[key] for key in original}
        assert current["content_revision"] != original["content_revision"]
        assert current["schema_revision"] == original["schema_revision"]

        # Every previously successful exact request now fails closed, for both actors.
        for actor in (owner, member):
            for url, params in reads(original):
                stale = actor.get(url, params=params)
                assert stale.status_code == 409, stale.text
                assert stale.json()["code"] == "STALE_READ_PIN"
                assert "items" not in stale.json() and "bounds" not in stale.json()
            viewport, extent = [actor.get(url, params=params) for url, params in reads(current)]
            assert viewport.status_code == extent.status_code == 200
            assert viewport.json()["context"]["content_revision"] == current["content_revision"]
            assert viewport.json()["items"][0]["geometry"]["coordinates"] == pytest.approx(
                [105.91, 21.11]
            )
            assert extent.json()["bounds"] == pytest.approx([105.91, 21.11, 105.91, 21.11])

        # Same member session, same warmed URLs, now denied before any pin result or data.
        assert owner.post(f"{_org(world)}/grants/{grant}/revoke").status_code == 204
        for pins in (current, original):
            for url, params in reads(pins):
                denied = member.get(url, params=params)
                assert denied.status_code == 403, denied.text
                assert "items" not in denied.json() and "bounds" not in denied.json()

        # Revoked member lookups must not poison another still-authorized actor's reads.
        viewport, extent = [owner.get(url, params=params) for url, params in reads(current)]
        assert viewport.status_code == extent.status_code == 200
        assert viewport.json()["items"][0]["feature_id"] == "warm-point"
