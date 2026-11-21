"""Audit-only real 3 formats x 3 geometry families round-trip via independent GDAL."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client

ROOT = Path("/opt/openvietgis-audit-018/dist/audit018")
FORMATS = {"geojson": ("geojson", "application/geo+json"),
           "gpkg": ("geopackage", "application/geopackage+sqlite3"),
           "zip": ("shapefile_zip", "application/zip")}
FAMILIES = {"points": ("Point", 2), "lines": ("LineString", 1), "polygons": ("Polygon", 1)}


def ok(response, status=(200, 201)):
    assert response.status_code in status, response.text
    return response.json()


def gdal(path):
    target = f"/vsizip/{path}" if path.suffix == ".zip" else str(path)
    info = json.loads(subprocess.check_output(["ogrinfo", "-al", "-so", "-json", target]))
    layer = info["layers"][0]
    features = json.loads(subprocess.check_output(["ogr2ogr", "-f", "GeoJSON", "/vsistdout/", target]))["features"]
    return layer, features


def normalize_geometry(g):
    def pt(p):
        return tuple(round(float(x), 8) for x in p)
    typ = g["type"]
    coords = g["coordinates"]
    if typ == "Point":
        return typ, pt(coords)
    if typ == "LineString":
        p = tuple(map(pt, coords))
        return typ, min(p, p[::-1])
    assert typ == "Polygon"
    rings = []
    for ring in coords:
        p = tuple(map(pt, ring))
        assert p[0] == p[-1]
        p = p[:-1]
        choices = [seq[i:] + seq[:i] for seq in (p, p[::-1]) for i in range(len(p))]
        rings.append(min(choices))
    return typ, tuple(rings)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("suffix", FORMATS)
def test_exact_format_roundtrip(migrated_database, family, suffix):
    crs = 4326
    expected_type, expected_count = FAMILIES[family]
    fmt, media = FORMATS[suffix]
    input_path = ROOT / "fixtures" / f"{family}.{suffix}"
    input_meta, input_features = gdal(input_path)
    assert input_meta["featureCount"] == len(input_features) == expected_count
    assert input_meta["geometryFields"][0]["type"] == expected_type
    assert input_meta["geometryFields"][0]["coordinateSystem"]["projjson"]["id"]["code"] == crs
    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    with _client(world.owner_user_id) as client:
        inp = input_path.read_bytes()
        uploaded = ok(client.post(f"{base}/imports/upload", files={"file":(input_path.name,inp,media)}))
        asset = uploaded["asset"]["id"]
        inspect = uploaded["inspection"]
        # Re-inspect with explicit CRS and encoding to obtain matching confirmation fingerprint.
        inspect = ok(client.post(f"{base}/imports/inspect", json={"source_asset_id": asset, "selected_member":inspect["selected_member"], "declared_source_crs":crs,"target_crs":crs,"declared_encoding":"utf-8"}))
        assert inspect["confirmable"], inspect
        assert inspect["asset_sha256"] == hashlib.sha256(inp).hexdigest()
        assert inspect["feature_count"] == expected_count
        operation = str(uuid4())
        ip = {"operation_id":operation,"source_asset_id":asset,"selected_member":inspect["selected_member"],
              "source_name":f"Audit {family} {suffix}","layer_name":f"Audit {family} {suffix}",
              "declared_source_crs":crs,"target_crs":crs,"declared_encoding":"utf-8",
              "approved_conversions":[c["code"] for c in inspect["conversions"] if c["requires_approval"]],
              "inspection_fingerprint":inspect["inspection_fingerprint"]}
        job = ok(client.post(f"{base}/imports/confirm", json=ip))
        assert job["status"] == "succeeded", job
        assert ok(client.post(f"{base}/imports/confirm", json=ip))["id"] == job["id"]
        layer_id = job["target_layer_id"]
        source = ok(client.get(f"{base}/layers/{layer_id}"))["source"]
        assert source["feature_count"] == expected_count
        assert source["stored_crs"]["code"] == crs
        pins = {k:source[k] for k in ("content_revision","schema_revision")}
        features = ok(client.get(f"{base}/layers/{layer_id}/features",params=pins))["items"]
        assert sorted(normalize_geometry(f["geometry"]) for f in features) == sorted(normalize_geometry(f["geometry"]) for f in input_features)
        export_params = {"layer_id":layer_id, **pins, "output_format":fmt,"output_crs":crs}
        preview = ok(client.post(f"{base}/exports/preview",json=export_params))
        assert preview["confirmable"]
        loss = [c["code"] for c in preview["disclosures"] if c["requires_approval"]]
        result = ok(client.post(f"{base}/exports/confirm",json={
            **export_params,"operation_id":str(uuid4()),"approved_disclosures":loss,
            "preview_fingerprint":preview["preview_fingerprint"]}))
        artifact = result["artifact"]
        dl = client.get(f"{base}/artifacts/{artifact['id']}/download")
        assert dl.status_code == 200
        assert hashlib.sha256(dl.content).hexdigest() == artifact["sha256"]
        out = ROOT / "roundtrip"
        out.mkdir(mode=0o700, exist_ok=True)
        p = out / f"{family}.{suffix}"
        p.write_bytes(dl.content)
        output_meta, output_features = gdal(p)
        assert output_meta["featureCount"] == len(output_features) == expected_count
        assert output_meta["geometryFields"][0]["type"] == expected_type
        assert output_meta["geometryFields"][0]["coordinateSystem"]["projjson"]["id"]["code"] == crs
        assert sorted(normalize_geometry(f["geometry"]) for f in output_features) == sorted(normalize_geometry(f["geometry"]) for f in input_features)
        mappings = {x["source_name"]:x["output_name"] for x in preview["field_mappings"]}
        # Core source names may use stable field IDs, not display names; use schema map if necessary.
        fields = {f["field_id"]:f["name"] for f in source["schema"]["fields"]}
        for m in preview["field_mappings"]:
            mappings.setdefault(fields[m["field_id"]], m["output_name"])
        input_fields = {f["name"]:(f["type"],f.get("subType")) for f in input_meta["fields"]}
        output_fields = {f["name"]:(f["type"],f.get("subType")) for f in output_meta["fields"]}
        for key, val in input_fields.items():
            assert key in mappings, (key,mappings)
            assert mappings[key] in output_fields, (key,output_fields)
            if not inspect["conversions"] and not preview["disclosures"]:
                assert output_fields[mappings[key]] == val, (key,val,output_fields)
        by_geom = {normalize_geometry(f["geometry"]):f["properties"] for f in output_features}
        for f in input_features:
            actual = by_geom[normalize_geometry(f["geometry"])]
            for key,val in f["properties"].items():
                assert actual[mappings[key]] == val, (key,val,actual[mappings[key]])
        print("AUDIT018_ROUNDTRIP", family,suffix,expected_count,{"import_conversions":[x["code"] for x in inspect["conversions"]],"export_disclosures":[x["code"] for x in preview["disclosures"]],"sha256":artifact["sha256"]})
