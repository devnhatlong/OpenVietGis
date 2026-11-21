"""Protected API path for the restricted raster adapters; no live providers."""

from __future__ import annotations

import base64
import io
import json
from dataclasses import asdict
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from openvietgis_api.adapters.http import external_sources
from openvietgis_api.domains.external_sources.provider import PROFILE_ENV
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client
from tests.unit.test_external_provider import HOST, png
from tests.unit.test_external_raster_provider import (
    TIFF,
    TILE_JSON,
    WMTS,
    WMTS_XML,
    XYZ,
    fixture_tiff,
)


def test_r010_raster_profiles_protected_api(migrated_database, monkeypatch):
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    project = f"{org}/projects/{world.project_id}"
    calls: list[str] = []
    monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(XYZ), asdict(WMTS), asdict(TIFF)]))

    def fetch(url: str, expected: str, _limit: int) -> bytes:
        calls.append(url)
        parsed = urlsplit(url)
        assert parsed.hostname == HOST
        if parsed.path == "/tilejson.json":
            assert expected == "json"
            return json.dumps(TILE_JSON).encode()
        if parsed.path == "/tiles/2/3/1.png":
            assert expected == "png"
            return png()
        if parsed.path == "/wmts":
            request = parse_qs(parsed.query)["REQUEST"][0]
            if request == "GetCapabilities":
                assert expected == "xml"
                return WMTS_XML
            assert expected == "png" and request == "GetTile"
            return png()
        if parsed.path == "/sample.tif":
            assert expected == "tiff"
            return fixture_tiff()
        raise AssertionError("unapproved endpoint")

    monkeypatch.setattr(external_sources, "fetch_provider_bytes", fetch)
    with _client(world.owner_user_id) as client:
        allow = client.post(f"{org}/external-sources/allowlist", json={"hostname": HOST})
        assert allow.status_code == 201, allow.text
        for profile, sample in ((XYZ, "xyz"), (WMTS, "wmts"), (TIFF, "geotiff_range_sample")):
            reg = client.post(
                f"{project}/external-sources",
                json={
                    "allowlist_id": allow.json()["id"],
                    "name": "Controlled raster",
                    "endpoint_url": profile.endpoint,
                    "protocol": profile.protocol.value,
                    "layer_identifier": profile.layer,
                    "crs_codes": [profile.crs],
                    "attribution": profile.attribution,
                    "license_text": profile.license_text,
                },
            )
            assert reg.status_code == 201, reg.text
            registration = reg.json()
            assert registration["availability"] == "unverified"
            assert not registration["capabilities"]["render"]
            endpoint = f"{project}/external-sources/{registration['id']}"
            before = len(calls)
            with _client(world.wrong_user_id) as wrong:
                assert wrong.post(f"{endpoint}/preview").status_code in (403, 404)
            assert len(calls) == before
            result = client.post(f"{endpoint}/preview")
            assert result.status_code == 200, result.text
            data = result.json()
            assert data["availability"] == "available"
            assert data["sample"]["kind"] == sample and data["capabilities"]["render"]
            assert data["scope"] == "operator_approved_sample"
            assert not data["capabilities"]["query"]
            assert result.headers["cache-control"] == "no-store"
            with Image.open(io.BytesIO(base64.b64decode(data["image_png_base64"]))) as image:
                if profile == TIFF:
                    assert image.getpixel((17, 17)) == (240, 240, 240, 255)
                else:
                    assert image.getpixel((12, 34)) == (99, 89, 79, 255)
            revoked = client.post(f"{endpoint}/revoke")
            assert revoked.status_code == 200
            before = len(calls)
            assert client.post(f"{endpoint}/preview").status_code == 403
            assert len(calls) == before
