"""Independent submitted print revision and artifact integrity controls."""

from __future__ import annotations

import hashlib
import io
import json
from uuid import uuid4

from PIL import Image
from sqlalchemy import text

from openvietgis_api.adapters.persistence import cartography_repository
from openvietgis_api.adapters.storage.local_object_store import LocalObjectStore
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_processing_integrity import _base, _point
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_sources import _client


def test_print_revision_confirmation_rejects_stale_source_style_layout_before_publication(
    migrated_database,
    monkeypatch,
):
    world = seed_access_world()
    base = _base(world)
    settings = {"output_format": "png", "dpi": 150}
    with _client(world.owner_user_id) as client:
        first = _import_geojson(
            client, world, "one.geojson", [_point("p1", 105.8, 21)], "One", "one"
        )
        second = _import_geojson(
            client, world, "two.geojson", [_point("p2", 105.82, 21.02)], "Two", "two"
        )
        layers = sorted([first["target_layer_id"], second["target_layer_id"]], reverse=True)
        built = client.post(
            f"{base}/cartography/layouts",
            json={
                "name": "Independent pinned print",
                "title": "Original title",
                "layer_ids": layers,
                "paper_size": "A4",
                "orientation": "landscape",
            },
        )
        assert built.status_code == 201, built.text
        layout_id = built.json()["id"]
        path = f"{base}/cartography/layouts/{layout_id}/exports"

        def preview():
            response = client.post(path + "/preview", json=settings)
            assert response.status_code == 200, response.text
            return response.json()

        def confirm(pin, settings_override=None):
            return client.post(
                path, json={**(settings_override or settings), "expected_revision_fingerprint": pin}
            )

        def reject_if_called(*_args, **_kwargs):
            raise AssertionError("stale or unconfirmed input reached rendering/object publication")

        def assert_stale(pin, settings_override=None):
            with monkeypatch.context() as patch:
                patch.setattr(cartography_repository, "render_print_map", reject_if_called)
                patch.setattr(LocalObjectStore, "put_bytes", reject_if_called)
                result = confirm(pin, settings_override)
            assert result.status_code == 409, result.text
            assert result.json()["code"] == "STALE_PRINT_REVISION"
            assert client.get(f"{base}/cartography/exports").json()["items"] == []

        # Missing digest fails even before preparing data; preview does not render or write files.
        with monkeypatch.context() as patch:
            patch.setattr(cartography_repository, "render_print_map", reject_if_called)
            patch.setattr(LocalObjectStore, "put_bytes", reject_if_called)
            assert client.post(path, json=settings).status_code == 422
            initial = preview()
            assert preview() == initial
        manifest = initial["revision_manifest"]
        pin = initial["revision_fingerprint"]
        independent_pin = hashlib.sha256(
            json.dumps(
                manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            ).encode()
        ).hexdigest()
        assert pin == independent_pin
        assert [entry["layer_id"] for entry in manifest["layers"]] == layers
        assert all(
            entry["style_revision"] == 0 and entry["style_id"] is None
            for entry in manifest["layers"]
        )
        assert manifest["pixel_width"] == 1754 and manifest["pixel_height"] == 1240
        assert manifest["effective_extent"]["min_x"] < manifest["extent"]["min_x"]
        assert manifest["effective_extent"]["max_y"] > manifest["extent"]["max_y"]
        assert_stale(pin, {"output_format": "pdf", "dpi": 300})
        assert_stale("0" * 64)

        # Creating a style when no style existed invalidates the exact submitted digest.
        style_path = f"{base}/cartography/layers/{first['target_layer_id']}/style"
        style = client.put(
            style_path, json={"mode": "single", "style_spec": {"fill_color": "#dc2626"}}
        )
        assert style.status_code == 200, style.text
        assert_stale(pin)
        with_style = preview()
        assert with_style["revision_fingerprint"] != pin
        style = client.put(
            style_path, json={"mode": "single", "style_spec": {"fill_color": "#16a34a"}}
        )
        assert style.status_code == 200, style.text
        assert_stale(with_style["revision_fingerprint"])

        before_edit = preview()
        entry = next(
            x
            for x in before_edit["revision_manifest"]["layers"]
            if x["layer_id"] == first["target_layer_id"]
        )
        edit = client.post(
            f"{base}/sources/{first['target_source_id']}/changesets",
            json={
                "base_content_revision": entry["content_revision"],
                "operation_id": str(uuid4()),
                "summary": "Change after print preview",
                "operations": [
                    {"op_type": "update", "feature_id": "p1", "properties": {"zone": "south"}}
                ],
            },
        )
        assert edit.status_code == 201, edit.text
        assert_stale(before_edit["revision_fingerprint"])

        # No exposed layout-update route in this slice; simulate restored/changed
        # persisted layout using the dedicated synthetic test database owner.
        before_layout = preview()
        with get_admin_engine().begin() as conn:
            conn.execute(
                text(
                    "UPDATE cartography.print_layouts SET title='Changed title',updated_at=now() "
                    "WHERE organization_id=:org AND project_id=:proj AND id=:id"
                ),
                {"org": world.organization_id, "proj": world.project_id, "id": layout_id},
            )
        assert_stale(before_layout["revision_fingerprint"])

        latest = preview()
        assert latest["revision_fingerprint"] != before_layout["revision_fingerprint"]
        assert (
            latest["revision_manifest"]["layout_revision"]
            != before_layout["revision_manifest"]["layout_revision"]
        )
        done = confirm(latest["revision_fingerprint"])
        assert done.status_code == 201, done.text
        exported = done.json()
        published = exported["revision_manifest"]
        assert published["revision_fingerprint"] == latest["revision_fingerprint"]
        assert {
            k: v for k, v in published.items() if k not in ("revision_fingerprint", "exported_at")
        } == latest["revision_manifest"]
        assert exported["scale_denominator"] == latest["revision_manifest"]["scale_denominator"]
        downloaded = client.get(f"{base}/cartography/exports/{exported['id']}/download")
        assert downloaded.status_code == 200
        assert (
            hashlib.sha256(downloaded.content).hexdigest()
            == exported["sha256"]
            == downloaded.headers["X-Content-SHA256"]
        )
        assert len(downloaded.content) == exported["byte_size"]
        with Image.open(io.BytesIO(downloaded.content)) as png:
            assert png.format == "PNG" and png.size == (1754, 1240)
        assert len(client.get(f"{base}/cartography/exports").json()["items"]) == 1

    with _client(world.wrong_user_id) as stranger:
        assert stranger.post(path + "/preview", json=settings).status_code in (403, 404)
        assert stranger.post(
            path, json={**settings, "expected_revision_fingerprint": latest["revision_fingerprint"]}
        ).status_code in (403, 404)
        assert stranger.get(
            f"{base}/cartography/exports/{exported['id']}/download"
        ).status_code in (403, 404)
