"""CAD preview API must enforce the requested project, even when computation is pure."""

from __future__ import annotations

import pytest

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("traverse", {"origin": [0, 0], "distance": 10, "azimuth_degrees": 90}),
        ("intersection", {"seg_a": [[0, 0], [10, 10]], "seg_b": [[0, 10], [10, 0]]}),
        ("offset", {"segment": [[0, 0], [10, 0]], "offset_distance": 2}),
        ("snap", {"target": [5, 0.1], "segments": [[[0, 0], [10, 0]]], "tolerance": 0.2}),
    ],
)
def test_cogo_preview_requires_live_project_access(migrated_database, name, payload):
    world = seed_access_world()
    other = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    path = f"{base}/cad/precision/{name}"
    with (
        _client(world.owner_user_id) as owner,
        _client(world.member_user_id) as ungranted,
        _client(other.owner_user_id) as outsider,
    ):
        result = owner.post(path, json=payload)
        assert result.status_code == 200, result.text
        assert result.json()["coordinate_reference"] == "unreferenced_planar_input"
        assert result.json()["survey_grade"] is False
        assert result.json()["published"] is False
        assert ungranted.post(path, json=payload).status_code in (403, 404)
        assert outsider.post(path, json=payload).status_code in (403, 404)


def test_dxf_requires_explicit_units_and_crs_and_leaves_no_rejected_artifact(migrated_database):
    from pathlib import Path

    from openvietgis_api.config import get_settings

    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    root = Path(get_settings().artifact_store_dir) / "cad" / str(world.organization_id)
    with _client(world.owner_user_id) as owner:
        files = {"file": ("broken.dxf", b"not a valid DXF", "application/dxf")}
        missing = owner.post(f"{base}/cad/import", files=files)
        assert missing.status_code == 422, missing.text
        invalid = owner.post(
            f"{base}/cad/import", files=files, data={"units": "meter", "crs_code": "5899"}
        )
        assert invalid.status_code == 422, invalid.text
        assert invalid.json()["code"] == "INVALID_DXF"
        assert not root.exists() or not any(path.is_file() for path in root.rglob("*"))
        assert owner.get(f"{base}/cad/conversions").json()["items"] == []
