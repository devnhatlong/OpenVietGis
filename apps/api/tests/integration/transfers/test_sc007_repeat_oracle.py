"""R005 SC007 proposed profile, five warmups and 30 measured serial trials."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url
from tools.test_database import assert_safe_test_target

from openvietgis_api.adapters.formats.geopackage import write_geopackage
from openvietgis_api.domains.spatial.domain import FieldType, NativeGeometry
from openvietgis_api.domains.transfers.domain import (
    MAX_TRANSFER_FEATURES,
    MAX_TRANSFER_FIELDS,
    MAX_UPLOAD_BYTES,
    ExportFieldMapping,
)
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client
from tests.integration.transfers.test_transfers_real import _ogrinfo_summary

# This proposed performance oracle is opt-in, never implicitly uses the suite
# default DB. Requiring a second explicit dedicated DSN prevents accidental use
# of an inherited/default service. Normal suites skip before migration fixtures.
RUN_BENCHMARK = os.environ.get("R005_RUN_BENCHMARK") == "1"
if RUN_BENCHMARK:
    target = os.environ.get("R005_BENCHMARK_TEST_DSN")
    if target is None or target != os.environ.get("OPENVIETGIS_TEST_DATABASE_URL"):
        raise RuntimeError("R005 benchmark requires explicit matching dedicated test DSNs")
    assert_safe_test_target(target)
    if make_url(target).port in (None, 5432, 54330):
        raise RuntimeError("R005 benchmark requires a separately isolated non-default test server")
    output = os.environ.get("R005_BENCHMARK_OUTPUT")
    if output is None or not Path(output).is_absolute() or Path(output).exists():
        raise RuntimeError("R005 benchmark requires a unique absolute evidence path")
    store_root = os.environ.get("OPENVIETGIS_ARTIFACT_STORE_DIR")
    if store_root is None or not Path(store_root).is_absolute():
        raise RuntimeError("R005 benchmark requires a dedicated artifact directory")


@pytest.mark.skipif(not RUN_BENCHMARK, reason="opt-in proposed R005 reference workload")
def test_r005_sc007_repeated_proposed_gpkg_point_profile(migrated_database: None) -> None:
    evidence = Path(os.environ["R005_BENCHMARK_OUTPUT"])
    assert evidence.is_absolute() and not evidence.exists()
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
    payload, _, _ = write_geopackage(
        layer_name="bench_10k",
        crs_code=4326,
        geometry_family="Point",
        field_mappings=mappings,
        features=features,
    )
    summary = _ogrinfo_summary(payload, ".gpkg")
    assert "Feature Count: 10000" in summary and "4326" in summary
    world = seed_access_world()
    client = _client(world.owner_user_id)
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "runtime_git": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "host": platform.platform(),
        "cpu_count": os.cpu_count(),
        "gdal": subprocess.check_output(["ogrinfo", "--version"], text=True).strip(),
        "profile": {
            "geometry": "2D Point, 1 position per feature",
            "feature_count": 10000,
            "attributes": ["text", "integer"],
            "source_crs": 4326,
            "target_crs": 4326,
            "format": "GeoPackage",
            "input_bytes": len(payload),
            "input_sha256": hashlib.sha256(payload).hexdigest(),
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "max_features": MAX_TRANSFER_FEATURES,
            "max_fields": MAX_TRANSFER_FIELDS,
            "warmups": 5,
            "measured": 30,
            "concurrency": 1,
            "p95_method": "nearest rank",
            "confirmed_import_budget_seconds": 60,
            "confirmed_export_budget_seconds": 30,
            "time_boundary": (
                "HTTP confirm POST in-process only; excludes upload, "
                "inspection, export preview, download, independent GDAL verification; "
                "synchronous endpoints no queue wait"
            ),
        },
        "observations": [],
    }
    ids: set[str] = set()

    def save() -> None:
        evidence.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    save()
    for i in range(35):
        up = client.post(
            f"{base}/imports/upload",
            files={"file": ("bench_10k.gpkg", payload, "application/geopackage+sqlite3")},
        )
        assert up.status_code == 201, up.text
        insp = up.json()["inspection"]
        assert insp["feature_count"] == 10_000 and insp["confirmable"]
        confirm = {
            "operation_id": str(uuid4()),
            "source_asset_id": up.json()["asset"]["id"],
            "selected_member": "bench_10k",
            "source_name": f"Bench 10k {i}",
            "layer_name": f"Bench 10k Layer {i}",
            "declared_source_crs": 4326,
            "target_crs": 4326,
            "declared_encoding": "utf-8",
            "approved_conversions": [],
            "inspection_fingerprint": insp["inspection_fingerprint"],
        }
        start = time.perf_counter()
        imp = client.post(f"{base}/imports/confirm", json=confirm)
        import_s = time.perf_counter() - start
        assert imp.status_code == 200, imp.text
        job = imp.json()
        assert job["status"] == "succeeded" and job["target_source_id"] not in ids
        ids.add(job["target_source_id"])
        layer_id = job["target_layer_id"]
        layer = client.get(f"{base}/layers/{layer_id}")
        assert layer.status_code == 200, layer.text
        source = layer.json()["source"]
        assert source["feature_count"] == 10000
        selection = {
            "layer_id": layer_id,
            "content_revision": source["content_revision"],
            "schema_revision": source["schema_revision"],
            "output_format": "geopackage",
            "output_crs": 4326,
        }
        prev = client.post(f"{base}/exports/preview", json=selection)
        assert prev.status_code == 200, prev.text
        assert prev.json()["disclosures"] == []
        start = time.perf_counter()
        exp = client.post(
            f"{base}/exports/confirm",
            json={
                **selection,
                "operation_id": str(uuid4()),
                "approved_disclosures": [],
                "preview_fingerprint": prev.json()["preview_fingerprint"],
            },
        )
        export_s = time.perf_counter() - start
        assert exp.status_code == 200, exp.text
        assert exp.json()["status"] == "succeeded"
        art = exp.json()["artifact"]
        assert (
            art["source_content_revision"] == selection["content_revision"]
            and art["source_schema_revision"] == selection["schema_revision"]
        )
        dl = client.get(f"{base}/artifacts/{art['id']}/download")
        assert (
            dl.status_code == 200
            and hashlib.sha256(dl.content).hexdigest()
            == art["sha256"]
            == dl.headers["x-content-sha256"]
        )
        assert art["byte_size"] == len(dl.content)
        gdal_summary = _ogrinfo_summary(dl.content, ".gpkg")
        assert "Feature Count: 10000" in gdal_summary and "4326" in gdal_summary
        data["observations"].append(
            {
                "index": i,
                "warmup": i < 5,
                "import_s": import_s,
                "export_s": export_s,
                "output_bytes": len(dl.content),
                "output_sha256": art["sha256"],
                "gdal_verified_count": 10000,
            }
        )
        save()
        print(
            f"R005_SC007 trial={i} warmup={i < 5} import_s={import_s:.3f} export_s={export_s:.3f}",
            flush=True,
        )
    measured = [o for o in data["observations"] if not o["warmup"]]
    assert len(measured) == 30

    def stats(key: str) -> dict[str, float]:
        vals = sorted(o[key] for o in measured)
        return {
            "p50": vals[math.ceil(0.5 * len(vals)) - 1],
            "p95": vals[math.ceil(0.95 * len(vals)) - 1],
            "max": vals[-1],
        }

    data["result"] = {"import": stats("import_s"), "export": stats("export_s")}
    save()
    assert data["result"]["import"]["p95"] <= 60
    assert data["result"]["export"]["p95"] <= 30
