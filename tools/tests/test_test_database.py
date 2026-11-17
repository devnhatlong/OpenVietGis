from unittest.mock import Mock

import pytest

from tools import run_with_test_database
from tools.test_database import DEFAULT_TEST_DATABASE_URL, build_test_environment


def test_test_database_does_not_inherit_application_database() -> None:
    environment = build_test_environment(
        {
            "OPENVIETGIS_ENVIRONMENT": "production",
            "OPENVIETGIS_DATABASE_URL": "postgresql+psycopg://u:p@live.example.com/customer",
        }
    )
    assert environment["OPENVIETGIS_ENVIRONMENT"] == "test"
    assert environment["OPENVIETGIS_DATABASE_URL"] == DEFAULT_TEST_DATABASE_URL


def test_explicit_dedicated_test_database_takes_precedence() -> None:
    target = "postgresql+psycopg://u:p@127.0.0.1:5432/openvietgis_test"
    environment = build_test_environment({"OPENVIETGIS_TEST_DATABASE_URL": target})
    assert environment["OPENVIETGIS_DATABASE_URL"] == target


@pytest.mark.parametrize(
    "target",
    [
        "postgresql+psycopg://u:p@live.example.com/openvietgis_test",
        "postgresql+psycopg://u:p@localhost/openvietgis",
        "postgresql+psycopg://u:p@localhost/openvietgis_test?dbname=customer_prod",
        "postgresql+psycopg://u:p@localhost/openvietgis_test?host=live.example.com",
        "postgresql+psycopg://u:p@localhost/openvietgis_test?hostaddr=192.0.2.1",
        "postgresql+psycopg://u:p@localhost/openvietgis_test?service=live",
        "mysql://u:p@localhost/openvietgis_test",
        "postgresql+psycopg://u:p@localhost/openvietgis_prod",
        "postgresql+psycopg://u:p@localhost/openvietgis_customer_live",
    ],
)
def test_unsafe_test_target_stops_before_migration_or_child_process(monkeypatch, target) -> None:
    monkeypatch.setenv("OPENVIETGIS_TEST_DATABASE_URL", target)
    monkeypatch.setattr(run_with_test_database.sys, "argv", ["test-runner", "pytest"])
    migrate = Mock()
    child = Mock()
    monkeypatch.setattr(run_with_test_database.command, "upgrade", migrate)
    monkeypatch.setattr(run_with_test_database.subprocess, "run", child)
    with pytest.raises(RuntimeError, match="Refusing"):
        run_with_test_database.main()
    migrate.assert_not_called()
    child.assert_not_called()
