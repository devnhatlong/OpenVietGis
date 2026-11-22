from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tools import reset_dev
from tools.reset_dev import assert_safe_target

from openvietgis_api import config


@pytest.mark.parametrize("database", ["openvietgis", "openvietgis_dev", "openvietgis_test"])
def test_accepts_only_documented_local_reset_databases(database: str) -> None:
    assert_safe_target(
        "development",
        f"postgresql+psycopg://user:pass@localhost:54329/{database}",
    )


@pytest.mark.parametrize(
    ("environment", "url"),
    [
        ("production", "postgresql+psycopg://user:pass@localhost/openvietgis"),
        ("development", "postgresql+psycopg://user:pass@db.example.com/openvietgis"),
        ("test", "postgresql+psycopg://user:pass@localhost/customer_prod"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?dbname=customer_prod"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?host=live.example.com"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?hostaddr=192.0.2.1"),
        ("test", "postgresql+psycopg://u:p@localhost/openvietgis_test?service=live"),
        ("test", "mysql://u:p@localhost/openvietgis_test"),
        ("development", "postgresql+psycopg://user:pass@localhost/openvietgis_prod"),
        ("test", "postgresql+psycopg://user:pass@localhost/openvietgis_customer_live"),
        ("development", "postgresql+psycopg://user:pass@localhost/openvietgis_dev_live"),
        ("test", "postgresql+psycopg://user:pass@localhost/openvietgis2"),
    ],
)
def test_rejects_unsafe_targets(environment: str, url: str) -> None:
    with pytest.raises(RuntimeError, match="Refusing reset"):
        assert_safe_target(environment, url)


@pytest.mark.parametrize(
    ("migration_url", "override"),
    [
        ("postgresql+psycopg://owner:dummy@example.test/openvietgis", None),
        ("postgresql+psycopg://owner:dummy@localhost:54329/customer_prod", None),
        ("postgresql+psycopg://owner:dummy@localhost:54329/openvietgis?hostaddr=192.0.2.1", None),
        ("postgresql+psycopg://owner:dummy@localhost:54330/openvietgis", None),
        ("postgresql+psycopg://owner:dummy@localhost:54329/openvietgis_test", None),
        ("postgresql+psycopg://owner:dummy@localhost:54329/openvietgis", "PGHOSTADDR"),
        ("postgresql+psycopg://owner:dummy@localhost:54329/openvietgis", "PGSERVICE"),
        ("postgresql+psycopg://owner:dummy@localhost:54329/openvietgis", "PGSERVICEFILE"),
    ],
)
def test_reset_rejects_actual_migration_destination_before_alembic(
    monkeypatch: pytest.MonkeyPatch, migration_url: str, override: str | None
) -> None:
    # This test never opens a database. The application URL looks safe in all
    # cases, but Alembic would use a different, unverified migration target.
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(
            environment="development",
            database_url="postgresql+psycopg://runtime:dummy@localhost:54329/openvietgis",
            migration_db_url=migration_url,
        ),
    )
    for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPORT"):
        monkeypatch.delenv(key, raising=False)
    if override:
        monkeypatch.setenv(override, "test-overridden")
    downgrade, upgrade = Mock(), Mock()
    monkeypatch.setattr(reset_dev.command, "downgrade", downgrade)
    monkeypatch.setattr(reset_dev.command, "upgrade", upgrade)
    with pytest.raises(RuntimeError, match="Refusing reset"):
        reset_dev.main()
    downgrade.assert_not_called()
    upgrade.assert_not_called()


def test_reset_accepts_distinct_credentials_for_same_local_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(
            environment="test",
            database_url="postgresql+psycopg://runtime:dummy@localhost:54330/openvietgis_test",
            migration_db_url="postgresql+psycopg://owner:dummy@localhost:54330/openvietgis_test",
        ),
    )
    for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPORT"):
        monkeypatch.delenv(key, raising=False)
    downgrade, upgrade = Mock(), Mock()
    monkeypatch.setattr(reset_dev.command, "downgrade", downgrade)
    monkeypatch.setattr(reset_dev.command, "upgrade", upgrade)
    assert reset_dev.main() == 0
    downgrade.assert_called_once()
    upgrade.assert_called_once()


def test_reset_refuses_implicit_port_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(
            environment="development",
            database_url="postgresql+psycopg://runtime:dummy@localhost/openvietgis",
            migration_db_url="postgresql+psycopg://owner:dummy@localhost/openvietgis",
        ),
    )
    for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PGPORT", "54399")
    downgrade, upgrade = Mock(), Mock()
    monkeypatch.setattr(reset_dev.command, "downgrade", downgrade)
    monkeypatch.setattr(reset_dev.command, "upgrade", upgrade)
    with pytest.raises(RuntimeError, match="Refusing reset"):
        reset_dev.main()
    downgrade.assert_not_called()
    upgrade.assert_not_called()
