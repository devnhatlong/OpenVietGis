"""Real PostgreSQL/PostGIS/ezdxf/GeoPackage integration tests for Wave B: R010–R013."""

from __future__ import annotations

import hashlib
import io
import json
import math
from uuid import uuid4

import ezdxf

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client


def _make_sample_dxf() -> bytes:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(500000, 2300000), (500100, 2300000), (500100, 2300100), (500000, 2300100)],
        close=True,
        dxfattribs={"layer": "PARCELS"},
    )
    msp.add_circle((500200, 2300200), radius=20.0, dxfattribs={"layer": "TREES"})
    # Unsupported 3DFACE should be logged explicitly in loss_report, never silently dropped
    msp.add_3dface([(0, 0, 10), (1, 0, 10), (1, 1, 10), (0, 1, 10)])
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_r010_external_sources_ssrf_and_allowlist(migrated_database: None) -> None:
    world = seed_access_world()
    org_base = f"/api/v1/organizations/{world.organization_id}"
    proj_base = f"{org_base}/projects/{world.project_id}"

    with _client(world.owner_user_id) as client:
        # 1. SSRF blocks loopback, private IPs, metadata endpoints
        for bad_host in ("127.0.0.1", "169.254.169.254", "10.0.0.5", "localhost", "db.internal"):
            r = client.post(
                f"{org_base}/external-sources/allowlist",
                json={"hostname": bad_host},
            )
            assert r.status_code == 403, f"expected 403 for {bad_host}: {r.text}"
            assert r.json()["code"] == "SSRF_BLOCKED"

        # 2. Allowlist legitimate public GIS host (with secret ref, never raw credential)
        al = client.post(
            f"{org_base}/external-sources/allowlist",
            json={
                "hostname": "tiles.example.org",
                "allowed_schemes": ["https"],
                "allowed_ports": [443],
                "secret_ref_name": "EXT_TILES_API_KEY",
            },
        )
        assert al.status_code == 201, al.text
        al_id = al.json()["id"]
        assert al.json()["has_secret_ref"] is True

        # 3. Embedded credentials in URL forbidden
        cred_err = client.post(
            f"{proj_base}/external-sources",
            json={
                "allowlist_id": al_id,
                "name": "Bad Creds",
                "protocol": "wms",
                "endpoint_url": "https://user:pass@tiles.example.org/wms",
            },
        )
        assert cred_err.status_code == 403

        # 4. Non-allowlisted host blocked
        host_err = client.post(
            f"{proj_base}/external-sources",
            json={
                "allowlist_id": al_id,
                "name": "Wrong Host",
                "protocol": "wms",
                "endpoint_url": "https://evil.example.net/wms",
            },
        )
        assert host_err.status_code == 403

        # 5. Valid WMS + COG connections are strictly read-only (edit=False, offline=False)
        conn = client.post(
            f"{proj_base}/external-sources",
            json={
                "allowlist_id": al_id,
                "name": "Satellite COG",
                "protocol": "cog_geotiff",
                "endpoint_url": "https://tiles.example.org/imagery/vn.tif",
                "attribution": "Open Imagery",
                "license_text": "CC-BY-4.0",
                "crs_codes": [3857, 4326],
            },
        )
        assert conn.status_code == 201, conn.text
        cdata = conn.json()
        assert cdata["read_only"] is True
        assert cdata["availability"] == "unverified"
        assert {key for key, enabled in cdata["capabilities"].items() if enabled} == {
            "metadata_read"
        }
        assert cdata["capabilities"]["edit"] is False
        assert cdata["capabilities"]["offline"] is False
        assert cdata["cache_generation"] == 1

        inv = client.post(f"{proj_base}/external-sources/{cdata['id']}/invalidate-cache")
        assert inv.status_code == 200 and inv.json()["cache_generation"] == 2

        rev = client.post(f"{proj_base}/external-sources/{cdata['id']}/revoke")
        assert rev.status_code == 200 and rev.json()["lifecycle"] == "revoked"
        assert rev.json()["availability"] == "revoked"


def test_r011_r012_r013_collaboration_cad_and_field_offline(migrated_database: None) -> None:
    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"

    with _client(world.owner_user_id) as client:
        # --- R012: CAD DXF import, DWG rejection, DXF export, Precision COGO ---
        dwg_res = client.post(
            f"{base}/cad/import",
            files={"file": ("site.dwg", b"AC1032-fake-dwg", "application/acad")},
            data={"layer_name": "Site DWG", "units": "meter", "crs_code": "5899"},
        )
        assert dwg_res.status_code == 422
        assert dwg_res.json()["code"] == "DWG_ADAPTER_REQUIRED"

        dxf_bytes = _make_sample_dxf()
        files = {"file": ("site.dxf", dxf_bytes, "application/dxf")}
        form = {
            "layer_name": "VN2000 CAD Parcels",
            "units": "meter",
            "crs_code": "5899",
            "curve_tolerance_m": "0.01",
        }
        inspection = client.post(f"{base}/cad/inspect", files=files, data=form)
        assert inspection.status_code == 200, inspection.text
        inspected = inspection.json()
        assert inspected["published"] is False and inspected["geometry_valid"] is True
        assert inspected["loss_report"]["requires_acknowledgement"] is True
        unacknowledged = client.post(f"{base}/cad/import", files=files, data=form)
        assert unacknowledged.status_code == 422
        assert unacknowledged.json()["code"] == "CAD_LOSS_ACK_REQUIRED"
        confirmed = form | {
            "acknowledge_loss": "true",
            "expected_sha256": inspected["sha256"],
            "expected_inspection_fingerprint": inspected["inspection_fingerprint"],
        }
        stale = client.post(
            f"{base}/cad/import", files=files, data=confirmed | {"curve_tolerance_m": "0.02"}
        )
        assert stale.status_code == 409 and stale.json()["code"] == "CAD_INSPECTION_STALE"
        dxf_res = client.post(f"{base}/cad/import", files=files, data=confirmed)
        assert dxf_res.status_code == 201, dxf_res.text
        dxf_data = dxf_res.json()
        assert dxf_data["status"] == "succeeded"
        assert dxf_data["entity_summary"]["published_feature_count"] == 2
        assert dxf_data["loss_report"]["unsupported_entities"]["3DFACE"] == 1
        assert "CIRCLE_TESSELLATED_BOUNDED" in dxf_data["loss_report"]["curve_approximations"]
        assert dxf_data["loss_report"]["curve_details"][0]["max_chord_deviation_grid_m"] <= 0.01
        assert dxf_data["loss_report"]["acknowledged"] is True

        # Export back to DXF and parse independently with ezdxf
        export_body = {
            "layer_id": dxf_data["layer_id"],
            "units": "meter",
            "expected_content_revision": dxf_data["content_revision"],
        }
        unacknowledged_export = client.post(f"{base}/cad/export", json=export_body)
        assert unacknowledged_export.status_code == 422
        assert unacknowledged_export.json()["code"] == "CAD_LOSS_ACK_REQUIRED"
        stale_export = client.post(
            f"{base}/cad/export",
            json=export_body
            | {"expected_content_revision": "0" * 64, "acknowledge_attribute_loss": True},
        )
        assert stale_export.status_code == 409
        dxf_exp = client.post(
            f"{base}/cad/export", json=export_body | {"acknowledge_attribute_loss": True}
        )
        assert dxf_exp.status_code == 200, dxf_exp.text
        exported_doc = ezdxf.read(io.StringIO(dxf_exp.content.decode("utf-8")))
        assert len(list(exported_doc.modelspace())) == 2

        # Precision COGO math endpoints
        trav = client.post(
            f"{base}/cad/precision/traverse",
            json={"origin": [500000.0, 2300000.0], "distance": 100.0, "azimuth_degrees": 90.0},
        )
        assert trav.status_code == 200
        assert math.isclose(trav.json()["endpoint"][0], 500100.0, abs_tol=1e-9)
        assert math.isclose(trav.json()["endpoint"][1], 2300000.0, abs_tol=1e-9)

        inter = client.post(
            f"{base}/cad/precision/intersection",
            json={"seg_a": [[0, 0], [10, 10]], "seg_b": [[0, 10], [10, 0]]},
        )
        assert inter.status_code == 200 and inter.json()["within_segments"] is True
        assert inter.json()["point"] == [5.0, 5.0]

        snap = client.post(
            f"{base}/cad/precision/snap",
            json={"target": [5.01, 0.01], "segments": [[[0, 0], [10, 0]]], "tolerance": 0.1},
        )
        assert snap.status_code == 200 and snap.json()["kind"] == "midpoint"

        # --- R013: Offline GeoPackage bundle, revocation, outbox sync + conflict ---
        # First import an editable Point layer in WGS84
        gj = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "pole_1",
                        "properties": {"status": "ok"},
                        "geometry": {"type": "Point", "coordinates": [105.85, 21.02]},
                    }
                ],
            }
        ).encode("utf-8")
        up = client.post(
            f"{base}/imports/upload",
            files={"file": ("poles.geojson", gj, "application/geo+json")},
        )
        assert up.status_code == 201, up.text
        ubody = up.json()
        imp = client.post(
            f"{base}/imports/confirm",
            json={
                "operation_id": str(uuid4()),
                "source_asset_id": ubody["asset"]["id"],
                "selected_member": ubody["inspection"]["selected_member"],
                "source_name": "Field Poles",
                "layer_name": "Field Poles",
                "declared_source_crs": 4326,
                "target_crs": 4326,
                "inspection_fingerprint": ubody["inspection"]["inspection_fingerprint"],
            },
        )
        assert imp.status_code in (200, 201), imp.text
        pole_layer = imp.json()["target_layer_id"]
        pole_source = imp.json()["target_source_id"]

        pkg = client.post(
            f"{base}/field/packages",
            json={
                "name": "Hanoi Field Pack",
                "layer_id": pole_layer,
                "aoi_bbox": {"min_x": 105.0, "min_y": 20.0, "max_x": 106.5, "max_y": 22.0},
                "ttl_hours": 48,
                "local_storage_confirmed": True,
            },
        )
        assert pkg.status_code == 201, pkg.text
        pkg_data = pkg.json()
        assert pkg_data["feature_count"] == 1

        dl = client.get(f"{base}/field/packages/{pkg_data['id']}/download")
        assert dl.status_code == 200
        assert dl.content[:16] == b"SQLite format 3\x00"
        assert hashlib.sha256(dl.content).hexdigest() == pkg_data["sha256"]
        snapshot = client.get(f"{base}/field/packages/{pkg_data['id']}/snapshot")
        assert snapshot.status_code == 200, snapshot.text
        assert (
            hashlib.sha256(snapshot.content).hexdigest()
            == pkg_data["layer_pins"][0]["snapshot_sha256"]
        )
        assert snapshot.json()["features"][0]["feature_id"] == "pole_1"
        assert snapshot.json()["features"][0]["properties"] == {"status": "ok"}

        for invalid in [
            {
                "op_type": "create",
                "feature_id": "outside",
                "geometry": {"type": "Point", "coordinates": [1, 1]},
                "properties": {"status": "new"},
            },
            {"op_type": "update", "feature_id": "not-packaged", "properties": {"status": "new"}},
            {"op_type": "delete", "feature_id": "pole_1", "properties": {"status": "new"}},
        ]:
            result = client.post(
                f"{base}/field/packages/{pkg_data['id']}/sync",
                json={
                    "operation_id": str(uuid4()),
                    "operations": [invalid],
                },
            )
            assert result.status_code == 422, result.text

        # Sync offline field point capture cleanly through R006 changeset
        sync1 = client.post(
            f"{base}/field/packages/{pkg_data['id']}/sync",
            json={
                "operation_id": "sync-batch-1",
                "operations": [
                    {
                        "op_type": "create",
                        "feature_id": "pole_2",
                        "geometry": {"type": "Point", "coordinates": [105.86, 21.03]},
                        "properties": {"status": "new_field"},
                    }
                ],
            },
        )
        assert sync1.status_code == 201, sync1.text
        assert sync1.json()["status"] == "applied"
        cs_id = sync1.json()["applied_changeset_ids"][0]
        replay_body = {
            "operation_id": "sync-batch-1",
            "operations": [
                {
                    "op_type": "create",
                    "feature_id": "pole_2",
                    "geometry": {"type": "Point", "coordinates": [105.86, 21.03]},
                    "properties": {"status": "new_field"},
                }
            ],
        }
        replay = client.post(f"{base}/field/packages/{pkg_data['id']}/sync", json=replay_body)
        assert replay.status_code == 201, replay.text
        assert replay.json()["id"] == sync1.json()["id"]
        replay_body["operations"][0]["properties"]["status"] = "changed intent"
        changed_replay = client.post(
            f"{base}/field/packages/{pkg_data['id']}/sync", json=replay_body
        )
        assert changed_replay.status_code == 409, changed_replay.text

        # Second sync from same stale package hits explicit conflict (never blind merge!)
        sync2 = client.post(
            f"{base}/field/packages/{pkg_data['id']}/sync",
            json={
                "operation_id": "sync-batch-2-stale",
                "operations": [
                    {
                        "op_type": "update",
                        "feature_id": "pole_1",
                        "properties": {"status": "conflict_edit"},
                    }
                ],
            },
        )
        assert sync2.status_code == 201, sync2.text
        assert sync2.json()["status"] == "conflict"
        assert len(sync2.json()["conflicts"]) == 1

        # Revoking offline package blocks future downloads
        rev_pkg = client.post(f"{base}/field/packages/{pkg_data['id']}/revoke")
        assert rev_pkg.status_code == 200 and rev_pkg.json()["revoked_at"] is not None
        dl_denied = client.get(f"{base}/field/packages/{pkg_data['id']}/download")
        assert dl_denied.status_code == 403

        # --- R011: Team Collaboration (Post-commit review, comments, activity, rebase) ---
        review = client.post(
            f"{base}/collaboration/reviews",
            json={
                "changeset_id": cs_id,
                "assignee_user_id": str(world.owner_user_id),
            },
        )
        assert review.status_code == 201, review.text
        rev_id = review.json()["id"]

        cmt = client.post(
            f"{base}/collaboration/reviews/{rev_id}/comments",
            json={"body": "Verified field pole_2 coordinates.", "feature_id": "pole_2"},
        )
        assert cmt.status_code == 201, cmt.text

        dec = client.post(
            f"{base}/collaboration/reviews/{rev_id}/decide",
            json={"status": "approved", "decision_note": "LGTM"},
        )
        assert dec.status_code == 200 and dec.json()["status"] == "approved"

        acts = client.get(f"{base}/collaboration/activities")
        assert acts.status_code == 200 and len(acts.json()["items"]) >= 3

        rebase = client.post(
            f"{base}/sources/{pole_source}/conflict-rebase",
            json={
                "base_content_revision": pkg_data["layer_pins"][0]["content_revision"],
                "draft_operations": [
                    {"op_type": "update", "feature_id": "pole_2"},
                    {"op_type": "update", "feature_id": "pole_1"},
                ],
            },
        )
        assert rebase.status_code == 200
        assert rebase.json()["has_conflicts"] is True
        assert rebase.json()["conflicts"][0]["feature_id"] == "pole_2"
        assert rebase.json()["policy"] == "explicit_refresh_and_reapply"
