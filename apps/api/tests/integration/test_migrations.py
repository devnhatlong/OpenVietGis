from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from openvietgis_api.adapters.persistence.db import get_engine

ROOT = Path(__file__).resolve().parents[4]


def test_migrations_apply_from_zero_to_head() -> None:
    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    inspector = inspect(get_engine())
    assert "sample_records" in inspector.get_table_names(schema="foundation")
