from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from tools.test_database import assert_safe_test_target, build_test_environment

os.environ.update(build_test_environment(os.environ))

from openvietgis_api.adapters.persistence.db import (  # noqa: E402
    get_engine,
    get_session_factory,
)
from openvietgis_api.config import get_settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def clear_runtime_caches() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_runtime_caches() -> None:
    clear_runtime_caches()
    yield
    clear_runtime_caches()


@pytest.fixture(scope="session")
def migrated_database() -> None:
    assert_safe_test_target(get_settings().database_url)
    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    command.upgrade(config, "head")
