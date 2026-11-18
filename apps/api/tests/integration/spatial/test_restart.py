"""SC-009 recovery through fresh applications and interrupted real DB writes.

Only guarded synthetic databases are used. The interruption kills the exact
restricted connection performing registration after actual SQL writes, rather
than replacing registration with a mock or restarting the shared DB service.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import event, text

from openvietgis_api.adapters.persistence.db import get_engine, get_session_factory
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_change_evidence import _all_changes
from tests.integration.spatial.test_features import _read, _setup
from tests.integration.spatial.test_layers import _counts, _detail
from tests.integration.spatial.test_layers import _path as _layer_path
from tests.integration.spatial.test_sources import _client, _error, _get, _register, _rows
from tests.integration.spatial.test_sources import _path as _source_path


def _restart_runtime() -> None:
    """Dispose all app connections and recreate factories; leave DB running."""
    get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()


@contextmanager
def _interrupt_registration_after(table: str) -> Iterator[list[int]]:
    engine = get_engine()
    interrupted: list[int] = []

    def after_write(connection, cursor, statement, parameters, context, executemany):
        if interrupted or not " ".join(statement.lower().split()).startswith(
            f"insert into {table} "
        ):
            return
        pid, database, role = connection.execute(
            text("SELECT pg_backend_pid(),current_database(),current_user")
        ).one()
        assert database == "openvietgis_test" and role == "openvietgis_runtime"
        # Kill only the observed registration backend in the guarded test DB.
        # The outer request then fails on its next SQL/commit and cannot retain
        # an earlier ready source, fields, features or success evidence.
        with get_admin_engine().begin() as admin:
            killed = admin.execute(
                text("""
                    SELECT pg_terminate_backend(pid, 5000)
                    FROM pg_stat_activity
                    WHERE pid=:pid AND datname='openvietgis_test'
                      AND usename='openvietgis_runtime'
                """),
                {"pid": pid},
            ).scalar_one()
            assert killed is True
        interrupted.append(pid)

    event.listen(engine, "after_cursor_execute", after_write)
    try:
        yield interrupted
    finally:
        event.remove(engine, "after_cursor_execute", after_write)


def test_fresh_app_and_pool_recreation_preserve_committed_catalog_and_pins(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as first_app:
        path, source, layer_id, pins = _setup(first_app, world, "reference_points_5899")
        before_page = _read(first_app, path, {**pins, "limit": 2})
        before_detail = _read(first_app, path + "/HVS-QN1", pins)
        before_layer = _detail(first_app, _layer_path(world), layer_id)
        before_history = _all_changes(first_app, world)
    before_rows, before_counts = _rows(source["id"]), _counts(world)

    # Repeat recreation to rule out dependence on the first app or connection.
    for _ in range(2):
        _restart_runtime()
        with _client(world.owner_user_id) as fresh_app:
            assert _get(fresh_app, _source_path(world), source["id"]) == source
            assert _detail(fresh_app, _layer_path(world), layer_id) == before_layer
            assert _read(fresh_app, path, {**pins, "limit": 2}) == before_page
            assert _read(fresh_app, path + "/HVS-QN1", pins) == before_detail
            assert _all_changes(fresh_app, world) == before_history
            _error(
                fresh_app.post(
                    _source_path(world),
                    json={"reference_key": "reference_points_5899", "name": "Duplicate retry"},
                ),
                409,
                "SOURCE_ALREADY_REGISTERED",
            )
        assert _rows(source["id"]) == before_rows
        assert _counts(world) == before_counts


@pytest.mark.parametrize(
    "after_table",
    ["spatial.data_sources", "spatial.reference_features", "spatial.catalog_changes"],
)
def test_interrupted_registration_rolls_back_then_fresh_app_retry_is_complete(
    migrated_database: None,
    after_table: str,
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as committed_app:
        path, source, layer_id, pins = _setup(committed_app, world, "reference_points_5899")
        before_layer = _detail(committed_app, _layer_path(world), layer_id)
        before_page = _read(committed_app, path, pins)
        before_history = _all_changes(committed_app, world)
    before_rows, before_counts = _rows(source["id"]), _counts(world)

    with _client(world.owner_user_id, raise_server_exceptions=False) as interrupted_app:
        with _interrupt_registration_after(after_table) as interrupted:
            failed = interrupted_app.post(
                _source_path(world),
                json={"reference_key": "reference_lines_4326", "name": "Interrupted reference"},
            )
        assert len(interrupted) == 1, f"did not interrupt {after_table} write"
        assert failed.status_code == 500

    _restart_runtime()
    # No source/field/feature/layer/change/success-audit survives the lost
    # transaction; previously committed records remain byte-for-byte intact.
    assert _counts(world) == before_counts
    assert _rows(source["id"]) == before_rows
    with _client(world.owner_user_id) as recovered_app:
        assert _get(recovered_app, _source_path(world), source["id"]) == source
        assert _detail(recovered_app, _layer_path(world), layer_id) == before_layer
        assert _read(recovered_app, path, pins) == before_page
        assert _all_changes(recovered_app, world) == before_history
        listing = _read(recovered_app, _source_path(world), {})
        assert listing["items"] == [source]
        retry = _register(
            recovered_app, _source_path(world), "reference_lines_4326", "Retried reference"
        )
        retried = _get(recovered_app, _source_path(world), retry["resource_id"])
        assert retried["validation_state"] == "ready"
        assert retried["feature_count"] == 3000
        assert retried["catalog_revision"] == 1
        retried_rows = _rows(retried["id"])
        assert len(retried_rows) == 3000
        assert all(
            row["valid"]
            and row["geometry_state"] == "present"
            and row["srid"] == 4326
            and row["content_revision"] == retried["content_revision"]
            and row["schema_revision"] == retried["schema_revision"]
            for row in retried_rows
        )
        final_history = _all_changes(recovered_app, world)
        assert len(final_history) == len(before_history) + 1
        assert sum(item["resource_id"] == retried["id"] for item in final_history) == 1
        after_counts = _counts(world)
        assert after_counts == tuple(
            count + delta for count, delta in zip(before_counts, (1, 7, 3000, 0, 1, 1), strict=True)
        )
        _error(
            recovered_app.post(
                _source_path(world),
                json={"reference_key": "reference_lines_4326", "name": "Duplicate retry"},
            ),
            409,
            "SOURCE_ALREADY_REGISTERED",
        )
        assert _counts(world) == after_counts

    # The successful retry is durable after another application recreation.
    _restart_runtime()
    with _client(world.owner_user_id) as final_app:
        assert _get(final_app, _source_path(world), retried["id"]) == retried
        assert _all_changes(final_app, world) == final_history
    assert _rows(source["id"]) == before_rows
