from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from testcontainers.community.postgres import PostgresContainer
from tools.test_database import assert_safe_test_target, build_test_environment

pytest_plugins = ("tests.fixtures.identity_tenancy",)

os.environ.update(build_test_environment(os.environ))
os.environ.setdefault(
    "OPENVIETGIS_BOOTSTRAP_SECRET",
    "openvietgis-test-bootstrap-secret",
)
os.environ.setdefault(
    "OPENVIETGIS_CSRF_SECRET",
    "openvietgis-test-csrf-secret",
)
os.environ.setdefault(
    "OPENVIETGIS_APPLICATION_SESSION_SECRET",
    "openvietgis-test-session-secret",
)
os.environ.setdefault(
    "OPENVIETGIS_OIDC_PROVIDERS",
    (
        '{"keycloak":{"issuer":"http://127.0.0.1:18080/realms/openvietgis",'
        '"client_id":"openvietgis-web","display_name":"OpenVietGIS Development"}}'
    ),
)
TEST_DATABASE_URL = os.environ["OPENVIETGIS_TEST_DATABASE_URL"]


from openvietgis_api.adapters.persistence.db import (  # noqa: E402
    get_engine,
    get_session_factory,
)
from openvietgis_api.config import get_settings  # noqa: E402
from tests.fixtures.db_admin import clear_admin_caches, get_admin_engine  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def clear_runtime_caches() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    clear_admin_caches()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_runtime_caches() -> None:
    clear_runtime_caches()
    yield
    clear_runtime_caches()


@pytest.fixture(scope="session")
def migrated_database() -> None:
    assert_safe_test_target(TEST_DATABASE_URL)
    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture
def destructive_migration_database(
    migrated_database: None,
    postgis_container_factory: Callable[[], PostgresContainer],
) -> Iterator[None]:
    """A fresh loopback DB for tests that intentionally drop/downgrade schemas.

    Depend on migrated_database first so the shared suite schema remains at head;
    never run destructive migration cycles over other tests' retained histories.
    """
    existing_url = make_url(get_settings().migration_db_url)
    with postgis_container_factory() as container:
        docker_container = container.get_wrapped_container()
        docker_container.reload()
        published = docker_container.attrs["NetworkSettings"]["Ports"]["5432/tcp"]
        assert len(published) == 1 and published[0]["HostIp"] == "127.0.0.1"
        isolated_url = make_url(container.get_connection_url())
        assert isolated_url.port is not None and isolated_url.port != (existing_url.port or 5432)
        assert isolated_url.port == int(container.get_exposed_port(5432))
        assert isolated_url.username == "openvietgis"
        database_url = isolated_url.render_as_string(hide_password=False)
        assert_safe_test_target(database_url)
        env = build_test_environment({**os.environ, "OPENVIETGIS_TEST_DATABASE_URL": database_url})
        try:
            with pytest.MonkeyPatch.context() as override:
                for key, value in env.items():
                    if key.startswith("OPENVIETGIS_"):
                        override.setenv(key, value)
                clear_runtime_caches()
                try:
                    assert get_settings().migration_db_url == database_url
                    with get_admin_engine().begin() as connection:
                        assert connection.execute(
                            text("SELECT current_database(), session_user")
                        ).one() == ("openvietgis_test", "openvietgis")
                        assert connection.execute(
                            text("SELECT to_regclass('alembic_version') IS NULL")
                        ).scalar_one()
                        # Testcontainers does not mount the development role-init
                        # SQL. Initialize the same restricted login in this fresh,
                        # verified disposable cluster only, including its test password.
                        connection.exec_driver_sql(
                            (
                                ROOT / "infra" / "dev" / "postgres" / "001-runtime-role.sql"
                            ).read_text(encoding="utf-8")
                        )
                    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
                    command.upgrade(config, "head")
                    yield
                finally:
                    clear_runtime_caches()
        finally:
            clear_runtime_caches()
