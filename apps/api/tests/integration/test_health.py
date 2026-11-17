from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from openvietgis_api.adapters.http import health
from openvietgis_api.main import create_app


def test_liveness_and_readiness_use_real_database(migrated_database: None) -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health/live").json() == {"status": "ok"}
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ready"}


def test_readiness_reports_database_unavailable(monkeypatch) -> None:
    class BrokenEngine:
        def connect(self):
            raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(health, "get_engine", lambda: BrokenEngine())

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}
