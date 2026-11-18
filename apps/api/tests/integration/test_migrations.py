from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from tools.test_database import assert_safe_test_target

from openvietgis_api.adapters.persistence.db import get_engine
from openvietgis_api.config import get_settings

ROOT = Path(__file__).resolve().parents[4]


def test_migrations_apply_from_zero_to_head() -> None:
    assert_safe_test_target(get_settings().database_url)
    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    inspector = inspect(get_engine())
    assert "sample_records" not in inspector.get_table_names(schema="foundation")
    assert {"service_principals", "service_credentials"} <= set(
        inspector.get_table_names(schema="org")
    )
    assert {"workspaces", "projects"} <= set(inspector.get_table_names(schema="workspace"))
