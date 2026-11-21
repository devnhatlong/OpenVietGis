"""R009 export must not silently omit missing layers or truncated features."""

from __future__ import annotations

from uuid import uuid4

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_sources import _client


def test_print_export_rejects_incomplete_layout(migrated_database):
    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    with _client(world.owner_user_id) as client:
        layout = {"name": "Safe print", "title": "Safe print", "layer_ids": [str(uuid4())]}
        rejected = client.post(f"{base}/cartography/layouts", json=layout)
        assert rejected.status_code == 404, rejected.text
        points = [
            {
                "type": "Feature",
                "id": f"p{i:04d}",
                "properties": {"label": f"P{i}"},
                "geometry": {"type": "Point", "coordinates": [105.8 + i * 0.00001, 21.0]},
            }
            for i in range(2501)
        ]
        imported = _import_geojson(client, world, "dense.geojson", points, "Dense", "dense-print")
        layout["layer_ids"] = [imported["target_layer_id"]]
        bad_extent = client.post(
            f"{base}/cartography/layouts",
            json={**layout, "extent": {"min_x": 106, "max_x": 105, "min_y": 20, "max_y": 22}},
        )
        assert bad_extent.status_code == 422, bad_extent.text
        assert bad_extent.json()["code"] == "INVALID_PRINT_EXTENT"
        created = client.post(f"{base}/cartography/layouts", json=layout)
        assert created.status_code == 201, created.text
        export = client.post(
            f"{base}/cartography/layouts/{created.json()['id']}/exports",
            json={"output_format": "png", "dpi": 150},
        )
        assert export.status_code == 422, export.text
        assert export.json()["code"] == "PRINT_FEATURE_LIMIT"
        assert client.get(f"{base}/cartography/exports").json()["items"] == []
