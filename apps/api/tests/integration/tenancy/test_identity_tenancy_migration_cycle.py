"""R002/P1 migration and logical-backup evidence in a disposable PostGIS container."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from testcontainers.community.postgres import PostgresContainer
from tools.test_database import assert_safe_test_target, build_test_environment

from openvietgis_api.config import get_settings
from tests.fixtures.db_admin import clear_admin_caches, get_admin_engine
from tests.fixtures.identity_tenancy import AccessWorld, seed_access_world

ROOT = Path(__file__).resolve().parents[5]
P1_SCHEMA = "0002_identity_tenant_core"
P1_RLS = "0003_tenant_rls"
P1_HEAD = "0003a_identity_unlink_security"
FOUNDATION = "0001_foundation_sample"
SCHEMAS = ("foundation", "identity", "org", "workspace", "audit", "platform")
TABLE_GRANTS = {
    "foundation.sample_records": "SELECT INSERT UPDATE",
    "identity.users": "SELECT INSERT UPDATE",
    "identity.identity_links": "SELECT INSERT UPDATE",
    "identity.web_sessions": "SELECT INSERT UPDATE",
    "org.organizations": "SELECT INSERT UPDATE",
    "org.organization_memberships": "SELECT INSERT UPDATE",
    "org.resource_grants": "SELECT INSERT UPDATE",
    "org.invitations": "SELECT INSERT UPDATE",
    "workspace.workspaces": "SELECT INSERT UPDATE",
    "workspace.projects": "SELECT INSERT UPDATE",
    "audit.audit_events": "SELECT INSERT",
    "platform.installation_state": "SELECT UPDATE",
}
RLS_TABLES = {
    "org.organization_memberships",
    "org.resource_grants",
    "org.invitations",
    "workspace.workspaces",
    "workspace.projects",
    "audit.audit_events",
}
PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
    "MAINTAIN",
)
BACKUP_PATH = "/tmp/openvietgis-p1-migration-test.dump"
DB_ARGS = [
    "--host=127.0.0.1",
    "--port=5432",
    "--username=openvietgis",
    "--dbname=openvietgis_test",
]


def _assert_revision(connection: Connection, revision: str) -> None:
    assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
        revision
    )


def _assert_schema_absent(connection: Connection, schemas: tuple[str, ...]) -> None:
    for schema in schemas:
        assert connection.execute(
            text("SELECT to_regnamespace(:schema) IS NULL"), {"schema": schema}
        ).scalar_one()


def _assert_runtime_security(connection: Connection, *, enabled: bool, unlink: bool) -> None:
    role = connection.execute(
        text(
            """
            SELECT rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolinherit, rolbypassrls
            FROM pg_roles WHERE rolname = 'openvietgis_runtime'
            """
        )
    ).one()
    assert tuple(role) == (True, False, False, False, False, False)
    for schema in SCHEMAS:
        for privilege in ("USAGE", "CREATE"):
            actual = connection.execute(
                text("SELECT has_schema_privilege('openvietgis_runtime', :schema, :privilege)"),
                {"schema": schema, "privilege": privilege},
            ).scalar_one()
            assert actual is (enabled and privilege == "USAGE"), (schema, privilege)
    for table, expected in TABLE_GRANTS.items():
        for privilege in PRIVILEGES:
            actual = connection.execute(
                text("SELECT has_table_privilege('openvietgis_runtime', :table, :privilege)"),
                {"table": table, "privilege": privilege},
            ).scalar_one()
            assert actual is (enabled and privilege in expected.split()), (table, privilege)
        flags = connection.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = "
                "CAST(:table AS regclass)"
            ),
            {"table": table},
        ).one()
        use_rls = enabled and table in RLS_TABLES
        assert tuple(flags) == (use_rls, use_rls), table
    function = connection.execute(
        text(
            """
            SELECT p.oid, p.prosecdef,
                has_function_privilege('openvietgis_runtime', p.oid, 'EXECUTE'),
                EXISTS (
                    SELECT 1
                    FROM aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a
                    WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE'
                )
            FROM pg_proc p
            WHERE p.oid = to_regprocedure('identity.unlink_identity(uuid,uuid)')
            """
        )
    ).one_or_none()
    if unlink:
        assert function is not None
        assert tuple(function[1:]) == (True, True, False)
    else:
        assert function is None


def _snapshot(connection: Connection) -> dict[str, list[str]]:
    # Fixed table names only; JSON text retains IDs, values, timestamps and NULLs.
    return {
        table: list(
            connection.execute(
                text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY 1")
            ).scalars()
        )
        for table in TABLE_GRANTS
    }


def _assert_runtime_visibility(connection: Connection, world: AccessWorld) -> None:
    connection.execute(text("SET LOCAL ROLE openvietgis_runtime"))
    assert connection.execute(text("SELECT current_user")).scalar_one() == "openvietgis_runtime"
    assert not list(connection.execute(text("SELECT id FROM workspace.workspaces")).scalars())
    connection.execute(
        text("SELECT set_config('openvietgis.organization_id', :org, true)"),
        {"org": str(world.organization_id)},
    )
    assert set(connection.execute(text("SELECT id FROM workspace.workspaces")).scalars()) == {
        world.workspace_a_id,
        world.workspace_b_id,
    }


def _container_command(container: PostgresContainer, command_args: list[str]) -> None:
    result = container.exec(["env", "PGPASSWORD=openvietgis", *command_args])
    assert result.exit_code == 0, result.output.decode(errors="replace")


def test_p1_migration_cycle_and_logical_backup(
    postgis_container_factory: Callable[[], PostgresContainer],
) -> None:
    """Never downgrade/restore the configured test DB or any persistent installation."""
    existing = make_url(get_settings().migration_db_url)
    with postgis_container_factory() as container:
        docker_container = container.get_wrapped_container()
        docker_container.reload()
        published = docker_container.attrs["NetworkSettings"]["Ports"]["5432/tcp"]
        assert len(published) == 1
        assert published[0]["HostIp"] == "127.0.0.1"
        isolated_url = make_url(container.get_connection_url())
        database_url = isolated_url.render_as_string(hide_password=False)
        assert_safe_test_target(database_url)
        # Both names are loopback; reject the same bound port regardless of hostname.
        assert isolated_url.port is not None
        assert isolated_url.port != (existing.port or 5432)
        assert isolated_url.port == int(container.get_exposed_port(5432))
        assert isolated_url.username == "openvietgis"

        env = build_test_environment({**os.environ, "OPENVIETGIS_TEST_DATABASE_URL": database_url})
        with pytest.MonkeyPatch.context() as settings_override:
            for key, value in env.items():
                if key.startswith("OPENVIETGIS_"):
                    settings_override.setenv(key, value)
            clear_admin_caches()
            get_settings.cache_clear()
            try:
                assert get_settings().migration_db_url == database_url
                engine = get_admin_engine()
                config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
                with engine.connect() as connection:
                    assert connection.execute(
                        text("SELECT current_database(), session_user")
                    ).one() == ("openvietgis_test", "openvietgis")
                    _assert_schema_absent(connection, SCHEMAS)

                command.upgrade(config, P1_HEAD)
                world = seed_access_world()
                seed_access_world()  # A separate tenant to challenge restored RLS.
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            """
                            INSERT INTO foundation.sample_records (
                                id, label, created_at, updated_at
                            )
                            VALUES (gen_random_uuid(), 'Synthetic record', now(), now())
                            """
                        )
                    )
                    connection.execute(
                        text(
                            """
                            INSERT INTO identity.web_sessions (
                                id, user_id, identity_link_id, secret_hash, issued_at, expires_at
                            )
                            SELECT gen_random_uuid(), user_id, id, decode('5a', 'hex'),
                                now(), now() + interval '1 day'
                            FROM identity.identity_links WHERE user_id = :actor
                            """
                        ),
                        {"actor": world.owner_user_id},
                    )
                    connection.execute(
                        text(
                            """
                            INSERT INTO org.resource_grants (
                                id, organization_id, subject_kind, membership_id,
                                scope_kind, workspace_id, role, created_at,
                                created_by_actor_type, created_by_actor_id
                            )
                            VALUES (
                                gen_random_uuid(), :org, 'membership', :member,
                                'workspace', :workspace, 'editor', now(), 'human', :actor
                            )
                            """
                        ),
                        {
                            "org": world.organization_id,
                            "member": world.member_membership_id,
                            "workspace": world.workspace_a_id,
                            "actor": world.owner_user_id,
                        },
                    )
                    connection.execute(
                        text(
                            """
                            INSERT INTO org.invitations (
                                id, organization_id, status, target_kind, target_email_normalized,
                                organization_role, token_hash, token_prefix,
                                expires_at, created_at, created_by_actor_type, created_by_actor_id
                            )
                            VALUES (
                                gen_random_uuid(), :org, 'pending', 'email', 'invite@example.test',
                                'member', decode('6b', 'hex'), 'synthetic',
                                now() + interval '1 day', now(), 'human', :actor
                            )
                            """
                        ),
                        {"org": world.organization_id, "actor": world.owner_user_id},
                    )
                    connection.execute(
                        text(
                            """
                            UPDATE platform.installation_state SET initialized_at = now(),
                                initial_organization_id = :org, initialized_by_user_id = :actor,
                                updated_at = now()
                            WHERE singleton_key = 'installation'
                            """
                        ),
                        {"org": world.organization_id, "actor": world.owner_user_id},
                    )
                    connection.execute(
                        text(
                            """
                            INSERT INTO audit.audit_events (
                                id, organization_id, actor_type, actor_id,
                                actor_display_snapshot, action, outcome, created_at
                            )
                            VALUES (
                                gen_random_uuid(), :org, 'human', :actor,
                                'Synthetic Owner', 'test.migration', 'success', now()
                            )
                            """
                        ),
                        {"org": world.organization_id, "actor": world.owner_user_id},
                    )
                with engine.connect() as connection:
                    expected = _snapshot(connection)
                    assert all(expected.values()), "Every application table must contain data"
                    assert len(expected["org.organizations"]) == 2
                    assert len(expected["audit.audit_events"]) == 1
                    _assert_revision(connection, P1_HEAD)
                    _assert_runtime_security(connection, enabled=True, unlink=True)

                command.downgrade(config, P1_RLS)
                with engine.connect() as connection:
                    _assert_revision(connection, P1_RLS)
                    assert _snapshot(connection) == expected
                    _assert_runtime_security(connection, enabled=True, unlink=False)

                command.downgrade(config, P1_SCHEMA)
                with engine.connect() as connection:
                    _assert_revision(connection, P1_SCHEMA)
                    assert _snapshot(connection) == expected
                    _assert_runtime_security(connection, enabled=False, unlink=False)

                command.upgrade(config, P1_HEAD)
                with engine.connect() as connection:
                    assert _snapshot(connection) == expected
                    _assert_runtime_security(connection, enabled=True, unlink=True)
                    _assert_runtime_visibility(connection, world)

                # Logical backup of the six application schemas including ACLs/policies.
                # The cluster-global runtime role is deliberately retained by 0003 downgrade.
                # This is not a full-cluster backup or a cross-cluster recovery test.
                _container_command(
                    container,
                    [
                        "pg_dump",
                        *DB_ARGS,
                        "--format=custom",
                        f"--file={BACKUP_PATH}",
                        *(f"--schema={schema}" for schema in SCHEMAS),
                    ],
                )
                command.downgrade(config, FOUNDATION)
                with engine.connect() as connection:
                    _assert_revision(connection, FOUNDATION)
                    _assert_schema_absent(connection, SCHEMAS[1:])
                command.upgrade(config, P1_HEAD)
                with engine.connect() as connection:
                    # 0002 is a destructive downgrade, not an in-place data rollback.
                    assert _snapshot(connection)["org.organizations"] == []
                    _assert_runtime_security(connection, enabled=True, unlink=True)

                command.downgrade(config, "base")
                with engine.connect() as connection:
                    _assert_schema_absent(connection, SCHEMAS)
                _container_command(
                    container,
                    [
                        "pg_restore",
                        *DB_ARGS,
                        "--single-transaction",
                        "--exit-on-error",
                        BACKUP_PATH,
                    ],
                )
                with engine.connect() as connection:
                    assert _snapshot(connection) == expected
                    _assert_runtime_security(connection, enabled=True, unlink=True)
                    _assert_runtime_visibility(connection, world)

                # Alembic's version table is outside the six-schema archive. Stamp
                # only after the restored P1 schemas, data, ACLs and RLS are verified.
                command.stamp(config, P1_HEAD)
                with engine.connect() as connection:
                    _assert_revision(connection, P1_HEAD)
            finally:
                clear_admin_caches()
                get_settings.cache_clear()
