from fastapi.testclient import TestClient

from openvietgis_api.adapters.persistence.db import get_engine, get_session_factory
from openvietgis_api.config import get_settings
from openvietgis_api.main import create_app


def reset_runtime_state() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()


def test_create_restart_read_path_ten_consecutive_runs(migrated_database: None) -> None:
    for index in range(10):
        with TestClient(create_app()) as client:
            create = client.post(
                "/api/v1/foundation-records",
                json={"label": f"restart-check-{index}"},
            )
            assert create.status_code == 201
            created = create.json()

        reset_runtime_state()

        with TestClient(create_app()) as restarted_client:
            loaded = restarted_client.get(f"/api/v1/foundation-records/{created['id']}")
            assert loaded.status_code == 200
            assert loaded.json()["id"] == created["id"]
            assert loaded.json()["label"] == created["label"]
