"""Audit-only negative readiness test: a deliberately unavailable provider is not a working GIS adapter."""
from __future__ import annotations

import pytest
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client


@pytest.mark.parametrize("protocol", ["wms", "wfs_ogc_features", "wmts_xyz", "cog_geotiff"])
def test_unvalidated_external_provider_not_advertised(migrated_database, protocol):
    world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    base = f"{org}/projects/{world.project_id}"
    # Reserved, deliberately non-resolvable .invalid TLD: no valid external
    # provider or actual customer endpoint, no credentials, no production data.
    host = "audit018-provider.invalid"
    with _client(world.owner_user_id) as client:
        allow = client.post(f"{org}/external-sources/allowlist", json={"hostname":host})
        if allow.status_code in (403, 422):
            # Denied unsupported destination is a safe negative outcome.
            return
        assert allow.status_code == 201, allow.text
        result = client.post(f"{base}/external-sources", json={
            "allowlist_id":allow.json()["id"], "name":f"Audit unvalidated {protocol}",
            "protocol":protocol, "endpoint_url":f"https://{host}/not-a-provider",
            "layer_identifier":"absent", "attribution":"Audit synthetic",
            "license_text":"No actual provider or assets", "crs_codes":[4326],
        })
        if result.status_code in (403, 422, 502, 503, 504):
            return
        assert result.status_code == 201, result.text
        record = result.json()
        active = {key for key, value in record["capabilities"].items() if value}
        print("AUDIT018_R010_UNVALIDATED",protocol,record["lifecycle"],sorted(active))
        # Registration as disabled/unverified metadata is allowed, but not
        # truthful active use capability before independent validation.
        assert not (record["lifecycle"] == "active" and active & {"render","feature_read","query","style"}), (
            "unavailable provider marked active with working capability", protocol, sorted(active)
        )
