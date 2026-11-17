from __future__ import annotations

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
        raise RuntimeError("Refusing reset for unsupported driver or database URL query parameters")
    if url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Refusing reset for non-local database host")

    database = url.database or ""
    if database not in {"openvietgis", "openvietgis_dev", "openvietgis_test"}:
        raise RuntimeError("Refusing reset for unexpected database name")


def main() -> int:
    from openvietgis_api.config import get_settings

    settings = get_settings()
    assert_safe_target(settings.environment, settings.database_url)

    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    print("Development foundation data reset and migrations reapplied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
