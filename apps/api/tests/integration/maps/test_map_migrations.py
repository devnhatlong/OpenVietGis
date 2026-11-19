"""Real map schema, restricted role, composite evidence and migration-cycle checks."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from openvietgis_api.adapters.persistence.db import get_engine
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.maps.test_saves import _intent, _root
from tests.integration.spatial.test_sources import _client

pytestmark = pytest.mark.usefixtures("migrated_database")
TABLES = ("project_maps", "map_operations", "map_revisions")
ROOT = Path(__file__).resolve().parents[5]


def _bind(connection, world):
    connection.execute(
        text("""
        SELECT set_config('openvietgis.organization_id',:org,true),
               set_config('openvietgis.project_id',:project,true)
    """),
        {"org": str(world.organization_id), "project": str(world.project_id)},
    )


def _saved_world():
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        saved = client.put(_root(world) + "/map", json=_intent())
        assert saved.status_code == 200, saved.text
    return world


def test_map_runtime_nonowner_forced_rls_and_append_only_evidence_privileges():
    with get_engine().connect() as connection:
        assert connection.execute(
            text("""
            SELECT current_user='openvietgis_runtime' AND NOT rolsuper AND NOT rolbypassrls
            FROM pg_roles WHERE rolname=current_user
        """)
        ).scalar_one()
        rows = (
            connection.execute(
                text("""
            SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
                pg_get_userbyid(c.relowner)<>current_user AS not_owner,
                has_table_privilege(c.oid,'DELETE') AS deletable,
                has_table_privilege(c.oid,'TRUNCATE') AS truncatable
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='maps' AND c.relkind='r'
        """)
            )
            .mappings()
            .all()
        )
        assert {row["relname"] for row in rows} == set(TABLES)
        for row in rows:
            assert row["relrowsecurity"] and row["relforcerowsecurity"] and row["not_owner"]
            assert not row["deletable"] and not row["truncatable"]
        for table in ("map_operations", "map_revisions"):
            assert not connection.execute(
                text(f"SELECT has_table_privilege('maps.{table}','UPDATE')")
            ).scalar_one()
        definitions = (
            connection.execute(
                text("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conname='fk_map_revision_operation'
        """)
            )
            .scalars()
            .all()
        )
        assert len(definitions) == 1
        for field in ("map_id", "configuration_revision", "actor_type", "actor_id"):
            assert field in definitions[0]
        revision_type = connection.execute(
            text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema='maps' AND table_name='project_maps'
                AND column_name='configuration_revision'
        """)
        ).scalar_one()
        assert revision_type == "bigint"


def test_map_rls_no_scope_foreign_scope_and_reused_connection_are_isolated():
    a, b = _saved_world(), _saved_world()
    with get_engine().begin() as connection:
        for table in TABLES:
            assert connection.execute(text(f"SELECT count(*) FROM maps.{table}")).scalar_one() == 0
        for world in (a, b, a):
            _bind(connection, world)
            for table in TABLES:
                projects = set(
                    connection.execute(text(f"SELECT project_id FROM maps.{table}")).scalars()
                )
                assert projects == {world.project_id}
        connection.execute(
            text("SELECT set_config('openvietgis.project_id',:other,true)"),
            {"other": str(b.project_id)},
        )
        assert connection.execute(text("SELECT count(*) FROM maps.project_maps")).scalar_one() == 0
    with get_engine().begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM maps.project_maps")).scalar_one() == 0


@pytest.mark.parametrize("table", ["map_operations", "map_revisions"])
def test_runtime_cannot_mutate_or_delete_existing_receipt_and_history(table):
    world = _saved_world()
    with get_engine().begin() as connection:
        _bind(connection, world)
        for statement in (
            f"UPDATE maps.{table} SET actor_id=:actor",
            f"DELETE FROM maps.{table}",
            f"TRUNCATE maps.{table}",
        ):
            with pytest.raises(DBAPIError) as failure, connection.begin_nested():
                connection.execute(text(statement), {"actor": uuid4()})
            assert failure.value.orig.sqlstate == "42501"


def test_direct_configuration_write_without_matching_next_evidence_cannot_commit():
    world = _saved_world()
    with get_engine().begin() as connection:
        _bind(connection, world)
        with pytest.raises(DBAPIError) as failure, connection.begin_nested():
            connection.execute(
                text("""
                UPDATE maps.project_maps SET configuration=jsonb_set(
                    configuration,'{default_viewpoint}',CAST(:viewpoint AS jsonb))
                WHERE project_id=:project
            """),
                {
                    "project": world.project_id,
                    "viewpoint": (
                        '{"longitude":106,"latitude":11,"zoom":8,'
                        '"bearing":0,"pitch":0,"crs":4326}'
                    ),
                },
            )
            connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        assert failure.value.orig.sqlstate == "23514"
        assert (
            connection.execute(
                text("SELECT configuration_revision FROM maps.project_maps")
            ).scalar_one()
            == 1
        )
        with pytest.raises(DBAPIError) as failure, connection.begin_nested():
            connection.execute(
                text("""
                UPDATE maps.project_maps SET configuration_revision=2
                WHERE project_id=:project
            """),
                {"project": world.project_id},
            )
            connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        assert failure.value.orig.sqlstate in ("23503", "23514")


@pytest.mark.parametrize(
    "bad",
    [
        {"layers": [], "basemap": None, "default_viewpoint": None},
        {"layers": [], "basemap": "grid", "default_viewpoint": {"crs": 4326}},
        {
            "layers": [{"layer_id": "bad", "visible": True, "style": {}}],
            "basemap": "grid",
            "default_viewpoint": None,
        },
        {"layers": [], "basemap": "grid", "default_viewpoint": None, "secret": "must reject"},
        {
            "layers": [
                {
                    "layer_id": str(uuid4()),
                    "visible": True,
                    "style": {"color": "#112233", "opacity": True, "width": 2, "radius": 5},
                }
            ],
            "basemap": "grid",
            "default_viewpoint": None,
        },
    ],
)
def test_database_configuration_validator_rejects_closed_shape_and_type_violations(bad):
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT maps.valid_configuration(CAST(:value AS jsonb))"),
                {"value": json.dumps(bad)},
            ).scalar_one()
            is False
        )


def test_map_schema_downgrade_upgrade_preserves_identity_catalog_and_reopens_cleanly():
    world = _saved_world()
    with get_admin_engine().connect() as connection:
        existing = connection.execute(
            text("SELECT id FROM workspace.projects WHERE id=:project"),
            {"project": world.project_id},
        ).scalar_one()
    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    try:
        command.downgrade(config, "0006_spatial_catalog")
        assert "maps" not in inspect(get_admin_engine()).get_schema_names()
        assert "spatial" in inspect(get_admin_engine()).get_schema_names()
        with get_admin_engine().connect() as connection:
            assert (
                connection.execute(
                    text("SELECT id FROM workspace.projects WHERE id=:project"),
                    {"project": world.project_id},
                ).scalar_one()
                == existing
            )
    finally:
        command.upgrade(config, "head")
    assert set(inspect(get_admin_engine()).get_table_names(schema="maps")) == set(TABLES)
    with _client(world.owner_user_id) as client:
        reopened = client.get(_root(world) + "/map")
        assert reopened.status_code == 200 and reopened.json()["configuration_revision"] == 0
        saved = client.put(_root(world) + "/map", json=_intent())
        assert saved.status_code == 200 and saved.json()["configuration_revision"] == 1
