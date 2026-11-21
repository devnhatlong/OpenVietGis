"""R010 protected provider transactions: real DB/RLS, synthetic provider bytes."""

from __future__ import annotations

import base64
import io
import json
from dataclasses import asdict, replace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from PIL import Image

from openvietgis_api.adapters.http import external_sources
from openvietgis_api.domains.external_sources.provider import PROFILE_ENV, ProviderUnavailable
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client
from tests.unit.test_external_provider import (
    FEATURES,
    HOST,
    PROFILE,
    WFS,
    WFS_XML,
    WMS_XML,
    png,
)


def test_r010_provider_preview_real_auth_live_bytes_and_reopen(migrated_database, monkeypatch):
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    project = f"{org}/projects/{world.project_id}"
    calls: list[str] = []
    fail = False

    def controlled_fetch(url: str, kind: str, limit: int) -> bytes:
        calls.append(url)
        if fail:
            raise ProviderUnavailable()
        p = urlsplit(url)
        assert p.hostname == HOST
        params = parse_qs(p.query)
        operation = params["REQUEST"][0]
        if operation == "GetCapabilities":
            assert kind == "xml"
            return WMS_XML if p.path == "/wms" else WFS_XML
        if operation == "GetMap":
            assert kind == "png"
            assert params["BBOX"] == [",".join(map(str, PROFILE.bbox))]
            return png()
        if operation == "GetFeature":
            assert kind == "json" and params["MAXFEATURES"] == ["100"]
            return json.dumps(FEATURES).encode()
        raise AssertionError("unexpected request")

    monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(PROFILE), asdict(WFS)]))
    monkeypatch.setattr(external_sources, "fetch_provider_bytes", controlled_fetch)
    with _client(world.owner_user_id) as client:
        allow = client.post(f"{org}/external-sources/allowlist", json={"hostname": HOST})
        assert allow.status_code == 201, allow.text
        for profile in (PROFILE, WFS):
            body = {
                "allowlist_id": allow.json()["id"],
                "name": "Synthetic provider",
                "protocol": profile.protocol.value,
                "endpoint_url": profile.endpoint,
                "layer_identifier": profile.layer,
                "attribution": profile.attribution,
                "license_text": profile.license_text,
                "crs_codes": [4326],
            }
            created = client.post(f"{project}/external-sources", json=body)
            assert created.status_code == 201, created.text
            conn = created.json()
            assert conn["availability"] == "unverified"
            assert not conn["capabilities"]["render"]
            assert not conn["capabilities"]["query"]
            endpoint = f"{project}/external-sources/{conn['id']}"
            count = len(calls)

            with _client(world.wrong_user_id) as wrong:
                denied = wrong.post(f"{endpoint}/preview")
                assert denied.status_code in (403, 404), denied.text
            with _client(world.member_user_id) as member:
                denied = member.post(f"{endpoint}/preview")
                assert denied.status_code in (403, 404), denied.text
                register = member.post(
                    f"{org}/external-sources/allowlist", json={"hostname": "denied.example.org"}
                )
                assert register.status_code == 403, register.text
            other = client.post(f"{project}/external-sources/{uuid4()}/preview")
            assert other.status_code == 404, other.text
            assert len(calls) == count

            # Fresh HTTP response verifies provider capabilities and real parsed bytes.
            verified = client.post(f"{endpoint}/preview")
            assert verified.status_code == 200, verified.text
            assert verified.headers["cache-control"] == "no-store"
            result = verified.json()
            assert result["availability"] == "available"
            assert result["scope"] == "operator_approved_sample"
            assert result["bbox"] == list(profile.bbox)
            assert result["crs"] == 4326
            assert result["connection_id"] == conn["id"]
            assert result["cache_generation"] == 1
            if profile == PROFILE:
                assert result["capabilities"]["render"]
                assert not result["capabilities"]["query"]
                with Image.open(io.BytesIO(base64.b64decode(result["image_png_base64"]))) as img:
                    assert img.getpixel((12, 34)) == (99, 89, 79, 255)
            else:
                assert result["capabilities"]["query"] and result["capabilities"]["feature_read"]
                assert not result["capabilities"]["render"]
                assert result["feature_collection"]["features"] == FEATURES["features"]
            assert not result["capabilities"]["edit"]
            assert not result["capabilities"]["offline"]
            assert len(calls) == count + 2

            # Reopen is a new request; no stale persisted success after failure.
            with _client(world.owner_user_id) as reopened:
                again = reopened.post(f"{endpoint}/preview")
                assert again.status_code == 200, again.text
                assert len(calls) == count + 4
                fail = True
                unavailable = reopened.post(f"{endpoint}/preview")
                assert unavailable.status_code == 502, unavailable.text
                fail = False
                records = reopened.get(f"{project}/external-sources").json()["items"]
                current = next(r for r in records if r["id"] == conn["id"])
                assert current["availability"] == "unverified"
                assert not current["capabilities"]["render"]
                assert not current["capabilities"]["query"]

            invalidated = client.post(f"{endpoint}/invalidate-cache")
            assert invalidated.json()["cache_generation"] == 2
            repeat = client.post(f"{endpoint}/preview")
            assert repeat.json()["cache_generation"] == 2
            revoked = client.post(f"{endpoint}/revoke")
            assert revoked.json()["availability"] == "revoked"
            before = len(calls)
            denied = client.post(f"{endpoint}/preview")
            assert denied.status_code == 403, denied.text
            assert len(calls) == before

        # Wrong rights, unsupported protocol, and embedded URL query cannot egress.
        wrong_rights = replace(PROFILE, license_text="Wrong License")
        for profile in (wrong_rights, replace(PROFILE, protocol="wmts_xyz")):
            c = client.post(
                f"{project}/external-sources",
                json={
                    "allowlist_id": allow.json()["id"],
                    "name": "Disabled provider",
                    "protocol": profile.protocol,
                    "endpoint_url": profile.endpoint,
                    "layer_identifier": profile.layer,
                    "attribution": profile.attribution,
                    "license_text": profile.license_text,
                    "crs_codes": [4326],
                },
            )
            assert c.status_code == 201, c.text
            before = len(calls)
            disabled = client.post(f"{project}/external-sources/{c.json()['id']}/preview")
            assert disabled.status_code == 403, disabled.text
            assert len(calls) == before
        sensitive = client.post(
            f"{project}/external-sources",
            json={
                "allowlist_id": allow.json()["id"],
                "name": "Embedded credential",
                "protocol": "wms",
                "endpoint_url": PROFILE.endpoint + "?token=fixture-secret",
            },
        )
        assert sensitive.status_code == 403, sensitive.text
        assert "fixture-secret" not in sensitive.text
