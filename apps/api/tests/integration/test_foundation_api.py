from fastapi.testclient import TestClient

from openvietgis_api.main import create_app


def test_create_read_not_found_and_validation(migrated_database: None) -> None:
    with TestClient(create_app()) as client:
        create = client.post(
            "/api/v1/foundation-records",
            json={"label": "  api-check  "},
        )
        assert create.status_code == 201
        created = create.json()
        assert created["label"] == "api-check"

        loaded = client.get(f"/api/v1/foundation-records/{created['id']}")
        assert loaded.status_code == 200
        assert loaded.json() == created

        missing = client.get("/api/v1/foundation-records/00000000-0000-0000-0000-000000000000")
        assert missing.status_code == 404

        blank = client.post("/api/v1/foundation-records", json={"label": "   "})
        assert blank.status_code == 422

        too_long = client.post("/api/v1/foundation-records", json={"label": "x" * 121})
        assert too_long.status_code == 422
