from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def assert_safe_target(environment: str, database_url: str) -> None:
    if environment not in {"development", "test"}:
        raise RuntimeError("Refusing reset outside development/test environment")

    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg" or url.query:
        raise RuntimeError(
            "Refusing reset for unsupported driver or database URL query parameters"
        )
    if url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Refusing reset for non-local database host")

    database = url.database or ""
    if database not in {"openvietgis", "openvietgis_dev", "openvietgis_test"}:
        raise RuntimeError("Refusing reset for unexpected database name")


def main() -> int:
    from openvietgis_api.config import get_settings

    settings = get_settings()
    # Alembic's env.py connects to migration_db_url, not necessarily database_url.
    # Validate both, and refuse a separate destination even when its name is
    # itself development-looking. Different credentials on the same DB are OK.
    assert_safe_target(settings.environment, settings.database_url)
    assert_safe_target(settings.environment, settings.migration_db_url)
    application = make_url(settings.database_url)
    migration = make_url(settings.migration_db_url)
    if (application.host, application.port or 5432, application.database) != (
        migration.host,
        migration.port or 5432,
        migration.database,
    ):
        raise RuntimeError(
            "Refusing reset when application and migration database targets differ"
        )
    # libpq may obtain a host address or service configuration independently
    # of the URL, and an omitted port from PGPORT. Never depend on these when
    # issuing destructive migration commands.
    if any(
        os.environ.get(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE")
    ) or (migration.port is None and os.environ.get("PGPORT")):
        raise RuntimeError("Refusing reset with libpq destination overrides")

    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    print("Development foundation data reset and migrations reapplied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
