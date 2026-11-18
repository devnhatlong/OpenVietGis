from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tools.test_database import assert_safe_test_target


def assert_safe_seed_target(environment: str, migration_url: str, runtime_url: str) -> None:
    """Refuse to seed a normal installation, even on the local development host."""
    if environment != "test":
        raise RuntimeError("Refusing identity E2E seed outside test environment")
    assert_safe_test_target(migration_url)
    assert_safe_test_target(runtime_url)
    migration = make_url(migration_url)
    runtime = make_url(runtime_url)
    if (migration.host, migration.port, migration.database) != (
        runtime.host,
        runtime.port,
        runtime.database,
    ):
        raise RuntimeError("Refusing identity E2E seed for mismatched test database targets")
    if not migration.username or (
        migration.username == runtime.username or runtime.username != "openvietgis_runtime"
    ):
        raise RuntimeError("Refusing identity E2E seed without distinct runtime role")


def main() -> int:
    from openvietgis_api.config import get_settings

    settings = get_settings()
    assert_safe_seed_target(
        settings.environment, settings.migration_db_url, settings.runtime_db_url
    )

    engine = create_engine(settings.migration_db_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE platform.installation_state
                    SET initialized_at = COALESCE(initialized_at, :now),
                        updated_at = :now
                    WHERE singleton_key = 'installation'
                    """
                ),
                {"now": datetime.now(UTC)},
            )
    finally:
        engine.dispose()

    print("P1 E2E installation marker initialized (dedicated test database only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
