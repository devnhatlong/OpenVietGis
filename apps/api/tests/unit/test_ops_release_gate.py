"""Fail-closed release truth and safe operational readiness probes."""

from pathlib import Path
from unittest.mock import MagicMock

from fastapi import Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http import ops
from openvietgis_api.adapters.persistence.ops_repository import SqlOpsRepository
from openvietgis_api.domains.ops.domain import (
    MANDATORY_TEAM_RELEASE,
    RELEASE_IDS,
    release_inventory,
)


def _healthy_session() -> MagicMock:
    session = MagicMock(spec=Session)
    session.execute.return_value.scalar_one.side_effect = ["PostgreSQL 18", "3.7"]
    return session


def test_release_inventory_is_not_production_certification() -> None:
    report = release_inventory()
    assert report["total_releases"] == len(RELEASE_IDS) == 15
    assert report["profile_status"] == "unverified"
    assert report["production_ready"] is False
    assert report["accepted_release_count"] == 0
    assert report["enabled_semantics"] == "release_certification"
    assert {item["id"] for item in report["items"]} == RELEASE_IDS
    assert {
        item["id"] for item in report["items"] if item["required_for_team"]
    } == MANDATORY_TEAM_RELEASE
    assert all(
        item["enabled"] is False and item["status"] == "unverified" and item["reason"]
        for item in report["items"]
    )
    # A caller cannot mutate future requests' catalog.
    report["items"][0]["enabled"] = True
    assert release_inventory()["items"][0]["enabled"] is False
    assert ops.ops_release_capabilities() == release_inventory()


def test_readiness_safe_probe_and_metric_certification_counts(tmp_path: Path) -> None:
    original_probe = tmp_path / ".ready_probe"
    original_probe.write_bytes(b"must not change")
    report = SqlOpsRepository(_healthy_session()).check_readiness(tmp_path)
    assert report["status"] == "ready"
    assert report["database"] == report["postgis"] == report["artifact_store"] == "ok"
    assert report["scope"] == "dependency_probe_only"
    assert report["production_ready"] is False
    assert original_probe.read_bytes() == b"must not change"
    assert list(tmp_path.iterdir()) == [original_probe]

    metrics = SqlOpsRepository(_healthy_session()).render_prometheus_metrics()
    assert "openvietgis_release_capabilities_enabled 0\n" in metrics
    assert "openvietgis_release_inventory_count 15\n" in metrics
    assert "openvietgis_release_gate_ready 0\n" in metrics
    assert "openvietgis_database_ready 1\n" in metrics
    assert "openvietgis_postgis_ready 1\n" in metrics


def test_missing_storage_is_not_created(tmp_path: Path) -> None:
    target = tmp_path / "missing"
    report = SqlOpsRepository(_healthy_session()).check_readiness(target)
    assert report["status"] == "not_ready"
    assert report["artifact_store"] == "unavailable"
    assert not target.exists()


def test_symlink_storage_is_not_probed(tmp_path: Path) -> None:
    real = tmp_path / "store"
    real.mkdir()
    target = tmp_path / "link"
    target.symlink_to(real, target_is_directory=True)
    report = SqlOpsRepository(_healthy_session()).check_readiness(target)
    assert report["status"] == "not_ready"
    assert list(real.iterdir()) == []


def test_database_failure_is_sanitized_and_does_not_imply_readiness(tmp_path: Path) -> None:
    session = MagicMock(spec=Session)
    session.execute.side_effect = SQLAlchemyError("private-connection-configuration")
    report = SqlOpsRepository(session).check_readiness(tmp_path)
    assert report["status"] == "not_ready"
    assert report["database"] == report["postgis"] == "unavailable"
    assert report["artifact_store"] == "ok"
    assert "private-connection-configuration" not in str(report)
    session.rollback.assert_called_once()


def test_postgis_failure_not_reported_as_database_loss(tmp_path: Path) -> None:
    session = MagicMock(spec=Session)
    session.execute.side_effect = [
        _healthy_session().execute.return_value,
        SQLAlchemyError("function unavailable"),
    ]
    report = SqlOpsRepository(session).check_readiness(tmp_path)
    assert report["status"] == "not_ready"
    assert report["database"] == "ok"
    assert report["postgis"] == "unavailable"
    session.rollback.assert_called_once()


def test_readiness_http_failure_returns_503(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        ops, "get_settings", lambda: MagicMock(artifact_store_dir=str(tmp_path / "absent"))
    )
    response = Response()
    report = ops.ops_health_ready(response, _healthy_session())
    assert response.status_code == 503
    assert report["status"] == "not_ready"
