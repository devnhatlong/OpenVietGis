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
