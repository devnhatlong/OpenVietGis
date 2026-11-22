"""Protected COG window route, with real fixture pixel/range proof and no outside network."""

import json
from dataclasses import asdict

from openvietgis_api.adapters.http import external_sources
from openvietgis_api.domains.external_sources.provider import PROFILE_ENV, RangeResponse
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client
from tests.unit.test_external_cog_provider import CROP, PROFILE, _gray, manual_cog
from tests.unit.test_external_provider import HOST


def test_r010_cog_viewport_authorization_pixels_and_generation(migrated_database, monkeypatch):
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    project = f"{org}/projects/{world.project_id}"
    raw, planes = manual_cog()
    calls: list[tuple[int, int]] = []
    monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(PROFILE)]))

    def fetch(url, first, last, etag, total, timeout):
        assert url == PROFILE.endpoint
        assert (etag, total) == ((None, None) if first == 0 else ('"fixture-v1"', len(raw)))
        assert 0 < timeout <= 5
        calls.append((first, last))
        return RangeResponse(raw[first : last + 1], len(raw), '"fixture-v1"')

    def deny_full(*args):
        raise AssertionError("unexpected full object fetch")

    monkeypatch.setattr(external_sources, "fetch_provider_range", fetch)
    monkeypatch.setattr(external_sources, "fetch_provider_bytes", deny_full)
    with _client(world.owner_user_id) as client:
        allow = client.post(f"{org}/external-sources/allowlist", json={"hostname": HOST})
        assert allow.status_code == 201, allow.text
        reg = client.post(
            f"{project}/external-sources",
            json={
                "allowlist_id": allow.json()["id"],
                "name": "Controlled COG",
                "endpoint_url": PROFILE.endpoint,
                "protocol": PROFILE.protocol.value,
                "layer_identifier": PROFILE.layer,
                "crs_codes": [PROFILE.crs],
                "attribution": PROFILE.attribution,
                "license_text": PROFILE.license_text,
            },
        )
        assert reg.status_code == 201, reg.text
        registration = reg.json()
        assert registration["availability"] == "unverified"
        assert not registration["capabilities"]["render"]
        endpoint = f"{project}/external-sources/{registration['id']}"
        window = {"crs": 4326, "bbox": CROP, "width": 128, "height": 128}
        with _client(world.wrong_user_id) as wrong:
            assert wrong.post(f"{endpoint}/viewport", json=window).status_code in (403, 404)
        assert (
            client.post(
                f"{endpoint}/viewport", json={**window, "bbox": (104, 20, 106, 21)}
            ).status_code
            == 403
        )
        for invalid in (
            {**window, "crs": 3857},
            {**window, "width": 513},
            {**window, "endpoint": "https://not-approved.invalid"},
            {**window, "bbox": ["105", 20, 106, 21]},
        ):
            assert client.post(f"{endpoint}/viewport", json=invalid).status_code == 422
        assert not calls

        preview = client.post(f"{endpoint}/preview")
        assert preview.status_code == 200, preview.text
        sample = preview.json()
        assert sample["scope"] == "operator_approved_sample"
        assert sample["sample"]["overview_index"] == 2
        assert sample["sample"]["allow_viewport"]
        assert _gray(sample) == ((256, 256), planes[2])
        assert preview.headers["cache-control"] == "no-store"

        calls.clear()
        viewport = client.post(f"{endpoint}/viewport", json=window)
        assert viewport.status_code == 200, viewport.text
        sample = viewport.json()
        oracle = b"".join(planes[0][y * 1024 : y * 1024 + 128] for y in range(128))
        assert _gray(sample) == ((128, 128), oracle)
        assert sample["scope"] == "operator_approved_viewport"
        assert sample["sample"]["overview_index"] == 0
        assert sample["sample"]["source_pixel_window"] == [0, 0, 128, 128]
        assert sample["sample"]["range_requests"] == len(calls) == 2
        assert sample["cache_generation"] == registration["cache_generation"]
        assert sample["connection_id"] == registration["id"]
        assert sample["capabilities"]["render"]
        assert not sample["capabilities"]["query"]
        assert not sample["capabilities"]["offline"]
        assert viewport.headers["cache-control"] == "no-store"

        invalidated = client.post(f"{endpoint}/invalidate-cache")
        assert invalidated.status_code == 200
        fresh = client.post(f"{endpoint}/viewport", json=window)
        assert fresh.status_code == 200
        assert fresh.json()["cache_generation"] == registration["cache_generation"] + 1
        listed = client.get(f"{project}/external-sources")
        assert listed.status_code == 200
        row = next(x for x in listed.json()["items"] if x["id"] == registration["id"])
        assert row["availability"] == "unverified" and not row["capabilities"]["render"]

        assert client.post(f"{endpoint}/revoke").status_code == 200
        before = len(calls)
        assert client.post(f"{endpoint}/viewport", json=window).status_code == 403
        assert len(calls) == before
