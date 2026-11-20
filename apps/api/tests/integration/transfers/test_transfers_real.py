"""Real PostGIS + GDAL (ogrinfo) integration, RLS, security, and SC-007 benchmark tests for R005."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from openvietgis_api.adapters.formats.geopackage import write_geopackage
from openvietgis_api.adapters.persistence.db import get_engine
from openvietgis_api.domains.spatial.domain import FieldType, NativeGeometry
from openvietgis_api.domains.transfers.domain import ExportFieldMapping
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client


def _make_sample_gpkg(crs_code: int = 4326) -> bytes:
    mappings = [
        ExportFieldMapping("code", "Code", "code", FieldType.TEXT),
        ExportFieldMapping(
            "long_description_field", "Long Desc", "long_description_field", FieldType.TEXT
        ),
        ExportFieldMapping("rank", "Rank", "rank", FieldType.INTEGER),
        ExportFieldMapping("measure", "Measure", "measure", FieldType.DECIMAL),
        ExportFieldMapping("active", "Active", "active", FieldType.BOOLEAN),
        ExportFieldMapping("observed_at", "Observed At", "observed_at", FieldType.TIMESTAMP),
    ]
    if crs_code == 4756:
        pts = [(107.160, 20.710), (107.165, 20.715)]
    else:
        pts = [(106.604, 10.704), (106.608, 10.708)]
    features = [
        (
            "pt-001",
            {
                "code": "P-1",
                "long_description_field": "",
                "rank": 0,
                "measure": "12.5",
                "active": False,
                "observed_at": "2026-11-20T00:00:00Z",
            },
            NativeGeometry("Point", pts[0], crs_code),
        ),
        (
            "pt-002",
            {
                "code": "P-2",
                "long_description_field": None,
                "rank": None,
                "measure": None,
                "active": None,
                "observed_at": None,
            },
            NativeGeometry("Point", pts[1], crs_code),
        ),
    ]
    data, _, _ = write_geopackage(
        layer_name="vn_points",
        crs_code=crs_code,
        geometry_family="Point",
        field_mappings=mappings,
        features=features,
    )
    return data


def _ogrinfo_summary(payload: bytes, suffix: str) -> str:
    if shutil.which("ogrinfo") is None:
        pytest.skip("ogrinfo not installed")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(payload)
        path = Path(handle.name)
    try:
        target = f"/vsizip/{path}" if suffix == ".zip" else str(path)
        proc = subprocess.run(
            ["ogrinfo", "-al", "-so", target],
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout
    finally:
        path.unlink(missing_ok=True)


def test_r005_migration_rls_and_append_only_privileges(migrated_database: None) -> None:
    with get_engine().begin() as conn:
        rows = (
            conn.execute(
                text("""
                    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                           c.relowner <> current_user::regrole AS not_owner,
                           has_table_privilege('transfers.' || c.relname, 'DELETE') AS deletable,
                           has_table_privilege('transfers.' || c.relname, 'UPDATE') AS updatable
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'transfers' AND c.relkind = 'r'
                """)
            )
            .mappings()
            .all()
        )
        by_name = {r["relname"]: r for r in rows}
        assert set(by_name) == {"source_assets", "jobs", "job_attempts", "derived_artifacts"}
        for name, row in by_name.items():
            assert row["relrowsecurity"] and row["relforcerowsecurity"] and row["not_owner"]
            assert not row["deletable"], f"{name} must not allow DELETE"
        assert not by_name["source_assets"]["updatable"]
        assert not by_name["job_attempts"]["updatable"]
        # Unscoped runtime query sees zero rows
        for name in by_name:
            assert conn.execute(text(f"SELECT count(*) FROM transfers.{name}")).scalar_one() == 0


def test_r005_import_export_round_trip_gdal_verify_and_idempotency(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    client = _client(world.owner_user_id)
    csrf: dict[str, str] = {}
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"

    # 1. Upload & inspect GeoPackage
    gpkg_bytes = _make_sample_gpkg(4326)
    up = client.post(
        f"{base}/imports/upload",
        files={"file": ("vn_points.gpkg", gpkg_bytes, "application/geopackage+sqlite3")},
        headers=csrf,
    )
    assert up.status_code == 201, up.text
    up_body = up.json()
    asset_id = up_body["asset"]["id"]
    insp = up_body["inspection"]
    assert insp["confirmable"] is True
    assert insp["feature_count"] == 2
    assert insp["resolved_source_crs"] == 4326

    # 2. Confirm import (idempotent replay + conflicting intent check)
    op_id = str(uuid4())
    confirm_body = {
        "operation_id": op_id,
        "source_asset_id": asset_id,
        "selected_member": insp["selected_member"],
        "source_name": "Imported Points",
        "layer_name": "Imported Points Layer",
        "declared_source_crs": 4326,
        "target_crs": 4326,
        "declared_encoding": "utf-8",
        "approved_conversions": [],
        "inspection_fingerprint": insp["inspection_fingerprint"],
    }
    res1 = client.post(f"{base}/imports/confirm", json=confirm_body, headers=csrf)
    assert res1.status_code == 200, res1.text
    job1 = res1.json()
    assert job1["status"] == "succeeded"
    layer_id = job1["target_layer_id"]
    source_id = job1["target_source_id"]
    assert layer_id and source_id

    # Idempotent replay returns exact same job without creating a duplicate source/layer
    res2 = client.post(f"{base}/imports/confirm", json=confirm_body, headers=csrf)
    assert res2.status_code == 200
    assert res2.json()["id"] == job1["id"]
    assert res2.json()["target_source_id"] == source_id

    # Conflicting intent on same operation_id returns 409
    bad_replay = dict(confirm_body, layer_name="Different Layer Name")
    res_conflict = client.post(f"{base}/imports/confirm", json=bad_replay, headers=csrf)
    assert res_conflict.status_code == 409
    assert res_conflict.json()["code"] == "OPERATION_INTENT_CONFLICT"

    # Verify imported source & layer are discoverable in R003 Spatial Catalog with export capability
    layer_detail = client.get(f"{base}/layers/{layer_id}")
    assert layer_detail.status_code == 200
    ldata = layer_detail.json()
    assert ldata["source"]["kind"] == "imported_file"
    assert ldata["source"]["provenance"]["source_asset_id"] == asset_id
    caps = {c["name"]: c for c in ldata["capabilities"]}
    assert caps["export"]["available"] is True and caps["export"]["actor_authorized"] is True
    content_rev = ldata["source"]["content_revision"]
    schema_rev = ldata["source"]["schema_revision"]

    # 3. Export to GeoPackage (lossless) + independent GDAL ogrinfo check
    prev_gpkg = client.post(
        f"{base}/exports/preview",
        json={
            "layer_id": layer_id,
            "content_revision": content_rev,
            "schema_revision": schema_rev,
            "output_format": "geopackage",
            "output_crs": 4326,
        },
        headers=csrf,
    )
    assert prev_gpkg.status_code == 200
    pg = prev_gpkg.json()
    assert pg["disclosures"] == []
    exp_gpkg = client.post(
        f"{base}/exports/confirm",
        json={
            "operation_id": str(uuid4()),
            "layer_id": layer_id,
            "content_revision": content_rev,
            "schema_revision": schema_rev,
            "output_format": "geopackage",
            "output_crs": 4326,
            "approved_disclosures": [],
            "preview_fingerprint": pg["preview_fingerprint"],
        },
        headers=csrf,
    )
    assert exp_gpkg.status_code == 200
    art_gpkg = exp_gpkg.json()["artifact"]
    dl_gpkg = client.get(f"{base}/artifacts/{art_gpkg['id']}/download")
    assert dl_gpkg.status_code == 200
    assert dl_gpkg.headers["x-content-sha256"] == art_gpkg["sha256"]
    ogr_gpkg = _ogrinfo_summary(dl_gpkg.content, ".gpkg")
    assert "Feature Count: 2" in ogr_gpkg
    assert "4326" in ogr_gpkg

    # 4. Export to ZIP Shapefile requires explicit loss approval, then passes GDAL ogrinfo
    prev_shp = client.post(
        f"{base}/exports/preview",
        json={
            "layer_id": layer_id,
            "content_revision": content_rev,
            "schema_revision": schema_rev,
            "output_format": "shapefile_zip",
            "output_crs": 3857,
        },
        headers=csrf,
    )
    assert prev_shp.status_code == 200
    ps = prev_shp.json()
    req_codes = [d["code"] for d in ps["disclosures"] if d["requires_approval"]]
    assert "DBF_FIELD_NAME_TRUNCATED" in req_codes

    # Unapproved loss must fail 422
    denied_loss = client.post(
        f"{base}/exports/confirm",
        json={
            "operation_id": str(uuid4()),
            "layer_id": layer_id,
            "content_revision": content_rev,
            "schema_revision": schema_rev,
            "output_format": "shapefile_zip",
            "output_crs": 3857,
            "approved_disclosures": [],
            "preview_fingerprint": ps["preview_fingerprint"],
        },
        headers=csrf,
    )
    assert denied_loss.status_code == 422
    assert denied_loss.json()["code"] == "UNAPPROVED_LOSS"

    # Approved loss succeeds and passes GDAL ogrinfo with EPSG:3857
    exp_shp = client.post(
        f"{base}/exports/confirm",
        json={
            "operation_id": str(uuid4()),
            "layer_id": layer_id,
            "content_revision": content_rev,
            "schema_revision": schema_rev,
            "output_format": "shapefile_zip",
            "output_crs": 3857,
            "approved_disclosures": req_codes,
            "preview_fingerprint": ps["preview_fingerprint"],
        },
        headers=csrf,
    )
    assert exp_shp.status_code == 200, exp_shp.text
    art_shp = exp_shp.json()["artifact"]
    dl_shp = client.get(f"{base}/artifacts/{art_shp['id']}/download")
    assert dl_shp.status_code == 200
    ogr_shp = _ogrinfo_summary(dl_shp.content, ".zip")
    assert "Feature Count: 2" in ogr_shp
    assert "3857" in ogr_shp or "Pseudo-Mercator" in ogr_shp

    # 5. Stale revision pin on export must fail with 409 STALE_READ_PIN
    stale_prev = client.post(
        f"{base}/exports/preview",
        json={
            "layer_id": layer_id,
            "content_revision": "f" * 64,
            "schema_revision": schema_rev,
            "output_format": "geopackage",
            "output_crs": 4326,
        },
        headers=csrf,
    )
    assert stale_prev.status_code == 409
    assert stale_prev.json()["code"] == "STALE_READ_PIN"


def test_r005_vn2000_transform_invalid_geometry_and_revoked_download_security(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    owner = _client(world.owner_user_id)
    owner_csrf: dict[str, str] = {}
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"

    # 1. Invalid self-intersecting polygon must block publication (zero partial source)
    bowtie = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [106.0, 10.0],
                                [106.2, 10.2],
                                [106.2, 10.0],
                                [106.0, 10.2],
                                [106.0, 10.0],
                            ]
                        ],
                    },
                    "properties": {"name": "Bowtie"},
                }
            ],
        }
    ).encode("utf-8")
    up_bad = owner.post(
        f"{base}/imports/upload",
        files={"file": ("bowtie.geojson", bowtie, "application/geo+json")},
        headers=owner_csrf,
    )
    assert up_bad.status_code == 201
    bad_insp = up_bad.json()["inspection"]
    bad_confirm = owner.post(
        f"{base}/imports/confirm",
        json={
            "operation_id": str(uuid4()),
            "source_asset_id": up_bad.json()["asset"]["id"],
            "selected_member": "features",
            "source_name": "Bad Poly",
            "layer_name": "Bad Poly Layer",
            "declared_source_crs": 4326,
            "target_crs": 4326,
            "declared_encoding": "utf-8",
            "approved_conversions": [],
            "inspection_fingerprint": bad_insp["inspection_fingerprint"],
        },
        headers=owner_csrf,
    )
    assert bad_confirm.status_code == 422
    assert bad_confirm.json()["code"] == "INVALID_GEOMETRY"
    assert owner.get(f"{base}/spatial/sources").json()["items"] == []

    # 2. VN-2000 EPSG:4756 -> EPSG:4326 transform import preserves source_crs=4756, stored_crs=4326
    vn_gpkg = _make_sample_gpkg(4756)
    up_vn = owner.post(
        f"{base}/imports/upload",
        files={"file": ("quangninh_4756.gpkg", vn_gpkg, "application/geopackage+sqlite3")},
        headers=owner_csrf,
    )
    assert up_vn.status_code == 201
    insp_vn = owner.post(
        f"{base}/imports/inspect",
        json={
            "source_asset_id": up_vn.json()["asset"]["id"],
            "selected_member": "vn_points",
            "declared_source_crs": 4756,
            "target_crs": 4326,
            "declared_encoding": "utf-8",
        },
        headers=owner_csrf,
    )
    assert insp_vn.status_code == 200
    iv = insp_vn.json()["inspection"]
    assert iv["confirmable"] is True
    job_vn = owner.post(
        f"{base}/imports/confirm",
        json={
            "operation_id": str(uuid4()),
            "source_asset_id": up_vn.json()["asset"]["id"],
            "selected_member": "vn_points",
            "source_name": "QN VN2000",
            "layer_name": "QN Layer",
            "declared_source_crs": 4756,
            "target_crs": 4326,
            "declared_encoding": "utf-8",
            "approved_conversions": [],
            "inspection_fingerprint": iv["inspection_fingerprint"],
        },
        headers=owner_csrf,
    )
    assert job_vn.status_code == 200, job_vn.text
    layer_id = job_vn.json()["target_layer_id"]
    layer_info = owner.get(f"{base}/layers/{layer_id}").json()
    assert layer_info["source"]["source_crs"]["code"] == 4756
    assert layer_info["source"]["stored_crs"]["code"] == 4326

    # 3. Grant viewer: cannot import, can export, then revoke -> download 403
    grant_res = owner.post(
        f"/api/v1/organizations/{world.organization_id}/grants",
        json={
            "subject_kind": "membership",
            "subject_id": str(world.member_membership_id),
            "scope_kind": "project",
            "project_id": str(world.project_id),
            "role": "viewer",
        },
        headers=owner_csrf,
    )
    assert grant_res.status_code == 201, grant_res.text
    grant_id = grant_res.json()["id"]

    viewer = _client(world.member_user_id)
    viewer_csrf: dict[str, str] = {}

    # Viewer cannot upload/import
    v_up = viewer.post(
        f"{base}/imports/upload",
        files={"file": ("v.gpkg", vn_gpkg, "application/geopackage+sqlite3")},
        headers=viewer_csrf,
    )
    assert v_up.status_code == 403

    # Viewer can preview + confirm export + download
    v_prev = viewer.post(
        f"{base}/exports/preview",
        json={
            "layer_id": layer_id,
            "content_revision": layer_info["source"]["content_revision"],
            "schema_revision": layer_info["source"]["schema_revision"],
            "output_format": "geopackage",
            "output_crs": 4326,
        },
        headers=viewer_csrf,
    )
    assert v_prev.status_code == 200
    v_exp = viewer.post(
        f"{base}/exports/confirm",
        json={
            "operation_id": str(uuid4()),
            "layer_id": layer_id,
            "content_revision": layer_info["source"]["content_revision"],
            "schema_revision": layer_info["source"]["schema_revision"],
            "output_format": "geopackage",
            "output_crs": 4326,
            "approved_disclosures": [],
            "preview_fingerprint": v_prev.json()["preview_fingerprint"],
        },
        headers=viewer_csrf,
    )
    assert v_exp.status_code == 200
    art_id = v_exp.json()["artifact"]["id"]
    assert viewer.get(f"{base}/artifacts/{art_id}/download").status_code == 200

    # Revoke viewer grant -> previously issued artifact_id MUST immediately return 403!
    rev = owner.post(
        f"/api/v1/organizations/{world.organization_id}/grants/{grant_id}/revoke",
        headers=owner_csrf,
    )
    assert rev.status_code == 204
    assert viewer.get(f"{base}/artifacts/{art_id}/download").status_code == 403
    assert viewer.get(f"{base}/jobs").status_code == 403


def test_r005_sc007_10000_feature_import_and_export_performance(migrated_database: None) -> None:
    world = seed_access_world()
    client = _client(world.owner_user_id)
    csrf: dict[str, str] = {}
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"

    mappings = [
        ExportFieldMapping("code", "Code", "code", FieldType.TEXT),
        ExportFieldMapping("rank", "Rank", "rank", FieldType.INTEGER),
    ]
    features = [
        (
            f"pt-{i:06d}",
            {"code": f"C-{i}", "rank": i},
            NativeGeometry("Point", (106.5 + (i % 100) * 0.001, 10.6 + (i // 100) * 0.001), 4326),
        )
        for i in range(10_000)
    ]
    gpkg_10k, _, _ = write_geopackage(
        layer_name="bench_10k",
        crs_code=4326,
        geometry_family="Point",
        field_mappings=mappings,
        features=features,
    )
    up = client.post(
        f"{base}/imports/upload",
        files={"file": ("bench_10k.gpkg", gpkg_10k, "application/geopackage+sqlite3")},
        headers=csrf,
    )
    assert up.status_code == 201
    insp = up.json()["inspection"]
    assert insp["feature_count"] == 10_000

    t0 = time.perf_counter()
    imp = client.post(
        f"{base}/imports/confirm",
        json={
            "operation_id": str(uuid4()),
            "source_asset_id": up.json()["asset"]["id"],
            "selected_member": "bench_10k",
            "source_name": "Bench 10k",
            "layer_name": "Bench 10k Layer",
            "declared_source_crs": 4326,
            "target_crs": 4326,
            "declared_encoding": "utf-8",
            "approved_conversions": [],
            "inspection_fingerprint": insp["inspection_fingerprint"],
        },
        headers=csrf,
    )
    import_s = time.perf_counter() - t0
    assert imp.status_code == 200, imp.text
    assert import_s <= 60.0, f"10k import took {import_s:.2f}s (> 60s budget)"

    layer_id = imp.json()["target_layer_id"]
    layer_info = client.get(f"{base}/layers/{layer_id}").json()
    prev = client.post(
        f"{base}/exports/preview",
        json={
            "layer_id": layer_id,
            "content_revision": layer_info["source"]["content_revision"],
            "schema_revision": layer_info["source"]["schema_revision"],
            "output_format": "geopackage",
            "output_crs": 4326,
        },
        headers=csrf,
    )
    assert prev.status_code == 200

    t1 = time.perf_counter()
    exp = client.post(
        f"{base}/exports/confirm",
        json={
            "operation_id": str(uuid4()),
            "layer_id": layer_id,
            "content_revision": layer_info["source"]["content_revision"],
            "schema_revision": layer_info["source"]["schema_revision"],
            "output_format": "geopackage",
            "output_crs": 4326,
            "approved_disclosures": [],
            "preview_fingerprint": prev.json()["preview_fingerprint"],
        },
        headers=csrf,
    )
    export_s = time.perf_counter() - t1
    assert exp.status_code == 200, exp.text
    assert export_s <= 30.0, f"10k export took {export_s:.2f}s (> 30s budget)"
    print(f"R005_SC007_10K import_s={import_s:.2f} export_s={export_s:.2f}")
