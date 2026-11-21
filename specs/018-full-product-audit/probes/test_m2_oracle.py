"""Audit-only synthetic oracle; no changes to frozen application code."""
from __future__ import annotations

import hashlib
import io
import math
import re
from pathlib import Path

from PIL import Image

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_sources import _client

POINTS = ((105.80, 21.02), (105.85, 21.05), (106.70, 10.77))
SCORES = (90, 40, 85)
BBOX = (105.70, 20.95, 105.95, 21.15)
ARTIFACTS = Path("/opt/openvietgis-audit-018/dist/audit018/oracle")


def json_ok(response, statuses=(200, 201)):
    assert response.status_code in statuses, response.text
    return response.json()


def fixture(client, world):
    features = [
        {
            "type": "Feature",
            "id": f"s{i+1}",
            "properties": {"score": score, "zone": "north" if i < 2 else "south"},
            "geometry": {"type": "Point", "coordinates": list(p)},
        }
        for i, (p, score) in enumerate(zip(POINTS, SCORES, strict=True))
    ]
    points = _import_geojson(client, world, "oracle-points.geojson", features, "Oracle points", "oracle-pts")
    x0, y0, x1, y1 = BBOX
    mask = _import_geojson(client, world, "oracle-mask.geojson", [{
        "type": "Feature", "id": "mask", "properties": {"name": "mask"},
        "geometry": {"type": "Polygon", "coordinates": [[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]]},
    }], "Oracle mask", "oracle-mask")
    return points["target_layer_id"], mask["target_layer_id"]


def read_layer(client, base, layer):
    source = json_ok(client.get(f"{base}/layers/{layer}"))["source"]
    pins = {k: source[k] for k in ("content_revision", "schema_revision")}
    page = json_ok(client.get(f"{base}/layers/{layer}/features", params=pins))
    assert page["next_after_feature_id"] is None
    return pins, page["items"]


def mercator(lon, lat):
    # Independent elementary EPSG:3857 equations, no PostGIS/PROJ oracle.
    radius = 6378137.0
    return radius * math.radians(lon), radius * math.asinh(math.tan(math.radians(lat)))


def polygon_area(geometry):
    assert geometry["type"] == "Polygon"
    rings = geometry["coordinates"]
    assert len(rings) == 1
    raw = [mercator(*p) for p in rings[0]]
    assert raw[0] == raw[-1]
    x0, y0 = raw[0]
    local = [(x-x0, y-y0) for x,y in raw]
    return abs(sum(x1*y2 - x2*y1 for (x1,y1),(x2,y2) in zip(local, local[1:]))) / 2


def test_query_and_processing_oracle(migrated_database):
    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    with _client(world.owner_user_id) as client:
        points, mask = fixture(client, world)
        pins, original = read_layer(client, base, points)
        assert {item["feature_id"] for item in original} == {"s1", "s2", "s3"}
        f = {"field": "score", "op": "gte", "value": 50}
        s = {"predicate": "within", "reference_layer_id": mask}
        x0,y0,x1,y1 = BBOX
        expected = {f"s{i+1}" for i, ((x,y), n) in enumerate(zip(POINTS,SCORES,strict=True)) if n >= 50 and x0<x<x1 and y0<y<y1}
        query = json_ok(client.post(f"{base}/layers/{points}/query", json={"attribute_filter": f, "spatial_filter": s}))
        assert set(query["selection_feature_ids"]) == expected == {"s1"}
        saved = json_ok(client.post(f"{base}/saved-queries", json={"layer_id": points, "name": "Oracle query", "attribute_filter": f, "spatial_filter": s}))
        listing = json_ok(client.get(f"{base}/saved-queries", params={"layer_id": points}))
        reopened = next(item for item in listing["items"] if item["id"] == saved["id"])
        replay = json_ok(client.post(f"{base}/layers/{points}/query", json={k: reopened[k] for k in ("attribute_filter", "spatial_filter")}))
        assert set(replay["selection_feature_ids"]) == expected
        # Independent oracle for a 32-sided regular polygon, in projected units.
        # This verifies candidate's declared/observed Web Mercator computation,
        # NOT a claim of geodesic/ground distance accuracy or approved CRS scope.
        expected_area = 32/2 * 1000**2 * math.sin(2*math.pi/32)

        def run(algorithm, input_layer, params, overlay=None):
            payload = {"algorithm_id": algorithm, "input_layer_id": input_layer, "parameters": params, "output_name": f"Oracle {algorithm}", "operation_id": f"a018-oracle-{algorithm}"}
            if overlay:
                payload["overlay_layer_id"] = overlay
            job = json_ok(client.post(f"{base}/processing/jobs", json=payload))
            assert job["status"] == "succeeded", job
            layer = job["output_layer_id"]
            _, rows = read_layer(client, base, layer)
            return layer, rows

        buf, buffered = run("buffer", points, {"distance_meters": 1000, "quad_segs": 8})
        assert len(buffered) == 3
        areas = [polygon_area(item["geometry"]) for item in buffered]
        assert all(math.isclose(area, expected_area, rel_tol=0.001) for area in areas), areas
        clip, clipped = run("clip", buf, {}, mask)
        assert len(clipped) == 2
        clipped_areas = [polygon_area(item["geometry"]) for item in clipped]
        assert all(math.isclose(area, expected_area, rel_tol=0.001) for area in clipped_areas), clipped_areas
        _, dissolved = run("dissolve", clip, {})
        dissolved_area = sum(polygon_area(item["geometry"]) for item in dissolved)
        assert math.isclose(dissolved_area, 2*expected_area, rel_tol=0.001), dissolved_area
        assert read_layer(client, base, points) == (pins, original)
        print("AUDIT018_M2_GEOMETRY", {"expected_projected_area_m2": expected_area, "buffer_m2": areas, "clip_m2": clipped_areas, "dissolve_m2": dissolved_area, "selection": sorted(expected)})


def test_cartography_artifact_oracle(migrated_database):
    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    ARTIFACTS.mkdir(mode=0o700, exist_ok=True)
    with _client(world.owner_user_id) as client:
        points, _ = fixture(client, world)
        json_ok(client.put(f"{base}/cartography/layers/{points}/style", json={
            "mode": "categorical", "style_spec": {"field": "zone", "categories": [
                {"value": "north", "color": "#dc2626", "label": "North"},
                {"value": "south", "color": "#16a34a", "label": "South"}]},
        }))
        layout = json_ok(client.post(f"{base}/cartography/layouts", json={
            "name": "Oracle A4", "title": "Audit synthetic map", "paper_size": "A4",
            "orientation": "landscape", "crs_code": 4326, "attribution": "Synthetic audit fixture",
            "layer_ids": [points],
        }))
        for ext,dpi in (("png",150),("pdf",300)):
            meta = json_ok(client.post(f"{base}/cartography/layouts/{layout['id']}/exports", json={"output_format": ext, "dpi": dpi}))
            response = client.get(f"{base}/cartography/exports/{meta['id']}/download")
            assert response.status_code == 200
            raw = response.content
            (ARTIFACTS / f"synthetic-a4-{dpi}.{ext}").write_bytes(raw)
            assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
            if ext == "png":
                image = Image.open(io.BytesIO(raw)).convert("RGB")
                assert image.size == (round(297/25.4*dpi), round(210/25.4*dpi))
                # Check colored symbols in map area, not just legend swatches.
                map_pixels = image.crop((0, 0, int(image.width*0.65), image.height)).getdata()
                red = sum(1 for r,g,b in map_pixels if r>g+40 and r>b+40)
                green = sum(1 for r,g,b in map_pixels if g>r+40 and g>b+25)
                assert red > 10 and green > 10, (red, green)
                print("AUDIT018_M2_PNG", image.size, {"red_map_pixels": red, "green_map_pixels": green})
            else:
                assert raw.startswith(b"%PDF-")
                box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", raw)
                assert box, "missing readable PDF page bounds"
                w,h = map(float,box.groups())
                assert abs(w-297/25.4*72)<1 and abs(h-210/25.4*72)<1, (w,h)
                print("AUDIT018_M2_PDF", {"page_points": [w,h]})
