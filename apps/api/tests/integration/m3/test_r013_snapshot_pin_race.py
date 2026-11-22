"""A real concurrent edit cannot be labeled with older offline snapshot pins."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m2.test_r006_r009_real import _import_geojson
from tests.integration.spatial.test_sources import _client


def test_package_snapshot_serializes_against_core_content_edit(migrated_database, monkeypatch):
    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    package_reading_fields, release_package, writer_started = Event(), Event(), Event()
    package_pid: list[int] = []
    writer_pids: list[int] = []

    with _client(world.owner_user_id) as reader, _client(world.owner_user_id) as writer:
        result = _import_geojson(
            reader,
            world,
            "r013-race.geojson",
            [
                {
                    "type": "Feature",
                    "id": "snapshot-point",
                    "properties": {"name": "old"},
                    "geometry": {"type": "Point", "coordinates": [105.5, 20.5]},
                }
            ],
            "R013 snapshot race",
            str(uuid4()),
        )
        source_id, layer_id = result["target_source_id"], result["target_layer_id"]
        detail = reader.get(f"{base}/layers/{layer_id}").json()["source"]
        base_revision = detail["content_revision"]

        original = Session.execute

        def execute(session, statement, *args, **kwargs):
            sql = str(statement)
            if (
                "SELECT field_id, name, type, nullable" in sql
                and "FROM spatial.source_fields" in sql
            ):
                # The issue request already read metadata/pins. Pause before reading rows.
                package_pid.append(
                    session.connection().exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
                )
                package_reading_fields.set()
                if not release_package.wait(15):
                    raise RuntimeError("package race test gate timed out")
            elif package_reading_fields.is_set() and not release_package.is_set():
                # Only the concurrent writer is doing Session SQL while the issue
                # request is paused. Capture before auth/scope locks, which can
                # serialize the writer earlier than the explicit source lock.
                pid = session.connection().exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
                if pid not in writer_pids:
                    writer_pids.append(pid)
                writer_started.set()
            return original(session, statement, *args, **kwargs)

        with monkeypatch.context() as scoped:
            scoped.setattr(Session, "execute", execute)
            with ThreadPoolExecutor(max_workers=2) as pool:
                issued = pool.submit(
                    reader.post,
                    f"{base}/field/packages",
                    json={
                        "name": "Atomic snapshot",
                        "layer_id": layer_id,
                        "aoi_bbox": {"min_x": 105, "min_y": 20, "max_x": 106, "max_y": 21},
                        "local_storage_confirmed": True,
                    },
                )
                try:
                    assert package_reading_fields.wait(10), "package never reached row read"
                    edited = pool.submit(
                        writer.post,
                        f"{base}/sources/{source_id}/changesets",
                        json={
                            "operation_id": str(uuid4()),
                            "base_content_revision": base_revision,
                            "operations": [
                                {
                                    "op_type": "update",
                                    "feature_id": "snapshot-point",
                                    "properties": {"name": "new"},
                                }
                            ],
                        },
                    )
                    assert writer_started.wait(5), "Core writer never entered database request"
                    # Independent lock oracle: the actual writer is blocked by
                    # this issue transaction, whether at org/project or source.
                    waiting = False
                    deadline = monotonic() + 5
                    with get_admin_engine().connect() as observer:
                        while monotonic() < deadline and not edited.done():
                            for pid in list(writer_pids):
                                blockers = observer.execute(
                                    text("SELECT pg_blocking_pids(:pid)"), {"pid": pid}
                                ).scalar_one()
                                if package_pid[0] in blockers:
                                    waiting = True
                                    break
                            if waiting:
                                break
                            sleep(0.01)
                    assert waiting, "Core writer was not blocked by the package issue transaction"
                finally:
                    release_package.set()
                package_response = issued.result(timeout=15)
                edit_response = edited.result(timeout=15)

        assert package_response.status_code == 201, package_response.text
        assert edit_response.status_code == 201, edit_response.text
        package = package_response.json()
        assert package["layer_pins"][0]["content_revision"] == base_revision
        snapshot_response = reader.get(f"{base}/field/packages/{package['id']}/snapshot")
        assert snapshot_response.status_code == 200, snapshot_response.text
        snapshot = snapshot_response.json()
        assert snapshot["content_revision"] == base_revision
        assert snapshot["features"][0]["properties"] == {"name": "old"}
        current = reader.get(f"{base}/layers/{layer_id}").json()["source"]
        assert current["content_revision"] != base_revision
        reread = reader.get(
            f"{base}/layers/{layer_id}/features",
            params={
                "content_revision": current["content_revision"],
                "schema_revision": current["schema_revision"],
            },
        )
        assert reread.status_code == 200, reread.text
        assert reread.json()["items"][0]["attributes"] == {"name": "new"}


@pytest.mark.parametrize("pin", ["content_revision", "schema_revision"])
def test_package_rejects_inconsistent_selected_row_pin(migrated_database, monkeypatch, pin):
    world = seed_access_world()
    base = f"/api/v1/organizations/{world.organization_id}/projects/{world.project_id}"
    with _client(world.owner_user_id) as client:
        result = _import_geojson(
            client,
            world,
            "r013-mixed-pin.geojson",
            [
                {
                    "type": "Feature",
                    "id": "pin-point",
                    "properties": {"name": "expected"},
                    "geometry": {"type": "Point", "coordinates": [105.5, 20.5]},
                }
            ],
            "R013 mixed pin",
            str(uuid4()),
        )
        original = Session.execute

        class MixedRows:
            def __init__(self, rows):
                self.rows = rows

            def mappings(self):
                return self

            def all(self):
                return self.rows

        def execute(session, statement, *args, **kwargs):
            sql = str(statement)
            response = original(session, statement, *args, **kwargs)
            # Simulate inconsistent stored pin at exactly the selected row
            # boundary, without corrupting shared fixtures or bypassing auth.
            matches = (
                "ST_CoveredBy" in sql and "FROM spatial.reference_features" in sql
                if pin == "content_revision"
                else "SELECT field_id, name, type, nullable" in sql
                and "FROM spatial.source_fields" in sql
            )
            if matches:
                rows = [dict(row) for row in response.mappings().all()]
                assert rows and rows[0][pin] != "0" * 64
                rows[0][pin] = "0" * 64
                return MixedRows(rows)
            return response

        with monkeypatch.context() as scoped:
            scoped.setattr(Session, "execute", execute)
            refused = client.post(
                f"{base}/field/packages",
                json={
                    "name": "Mixed pin must fail",
                    "layer_id": result["target_layer_id"],
                    "aoi_bbox": {"min_x": 105, "min_y": 20, "max_x": 106, "max_y": 21},
                    "local_storage_confirmed": True,
                },
            )
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "STALE_READ_PIN"
        listed = client.get(f"{base}/field/packages")
        assert listed.status_code == 200 and listed.json()["items"] == []
