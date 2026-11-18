from uuid import uuid4

from fastapi.testclient import TestClient

from openvietgis_api.main import create_app
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.rls.test_cross_tenant_api import client_for_user


def test_real_tenant_create_read_not_found_and_validation(migrated_database: None) -> None:
    world = seed_access_world()
    root = f"/api/v1/organizations/{world.organization_id}/projects"
    with client_for_user(world.owner_user_id) as client:
        created = client.post(root, json={"name": "  api-check  ", "slug": f"api-{uuid4().hex}"})
        assert created.status_code == 201, created.text
        record = created.json()
        assert record["name"] == "api-check"
        assert record["organization_id"] == str(world.organization_id)
        loaded = client.get(f"{root}/{record['id']}")
        assert loaded.status_code == 200
        assert loaded.json() == record
        assert client.get(f"{root}/{uuid4()}").status_code == 404

        for name in ("", "  ", "đ" * 201):
            invalid = client.post(root, json={"name": name, "slug": f"invalid-{uuid4().hex}"})
            assert invalid.status_code == 422

    with TestClient(create_app()) as anonymous:
        response = anonymous.post("/api/v1/foundation-records", json={"label": "retired"})
        assert response.status_code == 404
        assert anonymous.get(f"/api/v1/foundation-records/{uuid4()}").status_code == 404
        assert anonymous.get("/api/v1/health/live").status_code == 200
        assert anonymous.get("/api/v1/health/ready").status_code == 200
