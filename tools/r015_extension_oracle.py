"""R015 head drill: independent extension oracle, only disposable fixture DBs."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

TABLES = (
    "extensions.manifests",
    "extensions.project_activations",
    "extensions.records",
    "extensions.record_revisions",
    "extensions.activation_events",
    "extensions.import_receipts",
    "org.organizations",
    "workspace.workspaces",
    "workspace.projects",
)
HISTORY_TABLES = TABLES[3:6]
REVISION = "0019_extension_history"
KEY = "recovery_notes"


def _stable(rows):
    payload = json.dumps(
        rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return {"rows": len(rows), "sha256": hashlib.sha256(payload.encode()).hexdigest()}


def fingerprint(engine, expected):
    """Independent SQL oracle: every row, not just counts/current payload."""
    with engine.begin() as conn:
        assert (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == REVISION
        )
        conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        result = {}
        for table in TABLES:
            rows = (
                conn.execute(
                    text(
                        f"SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text"
                    )
                )
                .scalars()
                .all()
            )
            result[table] = _stable(rows)
        for table in HISTORY_TABLES:
            privileges = conn.execute(
                text("""
                SELECT has_table_privilege('openvietgis_runtime', :table, 'SELECT'),
                       has_table_privilege('openvietgis_runtime', :table, 'INSERT'),
                       has_table_privilege('openvietgis_runtime', :table, 'UPDATE'),
                       has_table_privilege('openvietgis_runtime', :table, 'DELETE')
            """),
                {"table": table},
            ).one()
            assert tuple(privileges) == (True, True, False, False)
            assert conn.execute(
                text("""
                SELECT relrowsecurity AND relforcerowsecurity FROM pg_class
                WHERE oid=CAST(:table AS regclass)
            """),
                {"table": table},
            ).scalar_one()
        assert (
            conn.execute(
                text("""
            SELECT count(*) FROM extensions.record_revisions
            WHERE event='legacy_baseline'
        """)
            ).scalar_one()
            >= 1
        )
        assert (
            conn.execute(
                text("""
            SELECT count(*) FROM extensions.activation_events
            WHERE event='legacy_baseline'
        """)
            ).scalar_one()
            >= 1
        )
        # Verify sampled original and copy point at same correctly scoped active
        # Core source+feature, revisions and actual attribute/geometry bytes.
        links = (
            conn.execute(
                text("""
            SELECT to_jsonb(r) AS record,
                   to_jsonb(l) AS layer, to_jsonb(s) AS source,
                   f.attributes AS attributes, encode(ST_AsEWKB(f.geometry),'hex') AS geometry
            FROM extensions.records r
            JOIN workspace.projects p ON p.id=r.project_id AND p.organization_id=r.organization_id
            JOIN extensions.manifests m ON m.id=r.manifest_id AND m.organization_id=r.organization_id
            JOIN spatial.layers l ON l.id=r.linked_layer_id AND l.project_id=r.project_id AND l.organization_id=r.organization_id
            JOIN spatial.data_sources s ON s.id=l.source_id AND s.project_id=r.project_id AND s.organization_id=r.organization_id
            JOIN spatial.reference_features f ON f.source_id=s.id AND f.feature_id=r.linked_feature_id AND f.organization_id=r.organization_id AND f.project_id=r.project_id
            WHERE r.extension_key=:key AND r.project_id=:project AND r.organization_id=:org
              AND r.link_context->>'source_id'=s.id::text
              AND r.link_context->>'content_revision'=s.content_revision
              AND r.link_context->>'schema_revision'=s.schema_revision
              AND (r.link_context->>'stored_crs')::integer=s.stored_crs
              AND f.content_revision=s.content_revision AND f.schema_revision=s.schema_revision
              AND l.lifecycle='active' AND s.lifecycle='active' AND s.validation_state='ready'
            ORDER BY r.id
        """),
                expected,
            )
            .mappings()
            .all()
        )
        assert len(links) == 2 and {row["record"]["id"] for row in links} == set(
            expected["records"]
        )
        assert all(row["geometry"] for row in links)
        result["scoped_core_links"] = _stable([dict(row) for row in links])
        # The receipt is a persisted independent mapping with original import
        # provenance, scoped both to project and its exact manifest.
        receipt = (
            conn.execute(
                text("""
            SELECT i.id::text AS id, i.bundle_sha256, i.mappings, i.actor_id::text AS actor,
                   i.manifest_id::text AS manifest
            FROM extensions.import_receipts i
            JOIN workspace.projects p ON p.id=i.project_id AND p.organization_id=i.organization_id
            JOIN extensions.manifests m ON m.id=i.manifest_id AND m.organization_id=i.organization_id
            WHERE i.id=:receipt AND i.organization_id=:org AND i.project_id=:project
        """),
                expected,
            )
            .mappings()
            .one()
        )
        assert dict(receipt) == expected["sql_receipt"]
        return result


@contextmanager
def _client(admin_url, token):
    from fastapi.testclient import TestClient
    from openvietgis_api.adapters.http.security import get_db_session
    from openvietgis_api.main import create_app

    runtime = create_engine(admin_url)

    @event.listens_for(runtime, "connect")
    def role(connection, _):
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE openvietgis_runtime")
            cursor.execute("SELECT current_user")
            assert cursor.fetchone()[0] == "openvietgis_runtime"
        connection.commit()

    def isolated_db():
        with Session(runtime, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = isolated_db
    try:
        with TestClient(app) as client:
            client.cookies.set("ovg_session", token)
            response = client.get("/api/v1/auth/csrf")
            assert response.status_code == 200
            client.headers["X-OpenVietGIS-CSRF"] = response.json()["token"]
            assert client.get("/api/v1/me").status_code == 200
            yield client
    finally:
        runtime.dispose()


def _response(response, status):
    assert response.status_code == status, (response.status_code, response.text[:500])
    return response.json()


def seed(engine, admin_url, org, project, owner, member, owner_token, member_token):
    from openvietgis_api.domains.extensions.domain import bundle_digest

    with engine.begin() as conn:
        layer = (
            conn.execute(
                text("""
            SELECT l.id AS layer, s.id AS source, f.feature_id, s.content_revision, s.schema_revision, s.stored_crs
            FROM spatial.layers l
            JOIN spatial.data_sources s ON s.id=l.source_id AND s.project_id=l.project_id AND s.organization_id=l.organization_id
            JOIN spatial.reference_features f ON f.source_id=s.id AND f.project_id=s.project_id AND f.organization_id=s.organization_id
            WHERE l.organization_id=:org AND l.project_id=:project AND l.lifecycle='active'
              AND s.lifecycle='active' AND s.validation_state='ready'
              AND s.stored_crs IS NOT NULL AND f.content_revision=s.content_revision
              AND f.schema_revision=s.schema_revision AND f.geometry_state='present'
            ORDER BY l.id, f.feature_id LIMIT 1
        """),
                {"org": org, "project": project},
            )
            .mappings()
            .one()
        )
        outsider = conn.execute(
            text("""
            SELECT m.user_id FROM org.organization_memberships m
            JOIN identity.identity_links i ON i.user_id=m.user_id
            WHERE m.organization_id<>:org AND m.role='owner' AND m.status='active'
              AND NOT EXISTS (SELECT 1 FROM org.organization_memberships mine
                 WHERE mine.organization_id=:org AND mine.user_id=m.user_id AND mine.status='active')
            ORDER BY m.user_id LIMIT 1
        """),
            {"org": org},
        ).scalar_one()

    o = f"/api/v1/organizations/{org}"
    p = f"{o}/projects/{project}"
    records = f"{p}/extensions/{KEY}/records"
    export = f"{p}/extensions/{KEY}/portable-export"
    import_route = f"{p}/extensions/{KEY}/portable-import"
    manifest = {
        "extension_key": KEY,
        "version": "1.0.0",
        "api_compatibility": "1.x",
        "display_name": "Synthetic Recovery Notes",
        "permissions": [f"ext.{KEY}.read", f"ext.{KEY}.write"],
        "entity_schemas": {
            "note": {
                "fields": {
                    "label": {"type": "text", "required": True},
                    "amount": {"type": "number", "required": False},
                    "flag": {"type": "boolean", "required": False},
                }
            }
        },
    }
    pin = {
        "status": "pinned",
        "source_id": str(layer["source"]),
        "content_revision": layer["content_revision"],
        "schema_revision": layer["schema_revision"],
        "stored_crs": layer["stored_crs"],
    }
    before = {"label": "Synthetic initial", "amount": 12.5, "flag": False}
    after = {"label": "Synthetic revised", "amount": 24.75, "flag": True}
    with (
        _client(admin_url, owner_token) as own,
        _client(admin_url, member_token) as editor,
    ):
        mid = _response(own.post(f"{o}/extensions/manifests", json=manifest), 201)["id"]
        aid = _response(
            own.post(f"{p}/extensions/activations", json={"manifest_id": mid}), 201
        )["id"]
        initial = {
            "entity_name": "note",
            "payload": before,
            "linked_layer_id": str(layer["layer"]),
            "linked_feature_id": layer["feature_id"],
            "expected_link_context": pin,
        }
        made = _response(own.post(records, json=initial), 201)
        rid = made["id"]
        assert made["link_context"] == pin and made["revision"] == 1
        update = {
            "expected_revision": 1,
            "expected_manifest_id": mid,
            "payload": after,
            "expected_link_context": pin,
        }
        revised = _response(editor.put(f"{records}/{rid}", json=update), 200)
        assert revised["revision"] == 2 and revised["payload"] == after
        history = _response(own.get(f"{records}/{rid}/history"), 200)["items"]
        assert [h["event"] for h in history] == ["create", "update"]
        assert [h["actor_id"] for h in history] == [str(owner), str(member)]
        assert [h["payload"] for h in history] == [before, after]
        assert [h["link_context"] for h in history] == [pin, pin]
        portable = _response(own.get(export), 200)
        assert bundle_digest(portable["bundle"]) == portable["sha256"]
        request = {**portable, "expected_manifest_id": mid}
        receipt = _response(own.post(import_route, json=request), 200)
        assert not receipt["replayed"] and len(receipt["mappings"]) == 1
        copied = receipt["mappings"][0]["record_id"]
        assert copied != rid and receipt["mappings"][0]["source_record_id"] == rid
        assert _response(own.post(import_route, json=request), 200) == {
            **receipt,
            "replayed": True,
        }
        copied_history = _response(own.get(f"{records}/{copied}/history"), 200)["items"]
        assert len(copied_history) == 1 and copied_history[0]["event"] == "import"
        assert copied_history[0]["import_origin"]["bundle_sha256"] == portable["sha256"]
        assert copied_history[0]["import_origin"]["verified_origin"] is False
        assert copied_history[0]["link_context"] == pin
        _response(own.post(f"{p}/extensions/activations/{aid}/deactivate"), 200)
        assert (
            _response(own.get(export), 200)["bundle"]["activation_status"] == "disabled"
        )
        assert (
            _response(
                own.post(f"{p}/extensions/activations", json={"manifest_id": mid}), 201
            )["id"]
            == aid
        )
        nextid = _response(
            own.post(
                f"{o}/extensions/manifests", json={**manifest, "version": "1.1.0"}
            ),
            201,
        )["id"]
        _response(
            own.post(
                f"{p}/extensions/activations/{aid}/transition",
                json={"expected_manifest_id": mid, "target_manifest_id": nextid},
            ),
            200,
        )
        events = _response(own.get(f"{p}/extensions/activations/{aid}/history"), 200)[
            "items"
        ]
        assert [e["event"] for e in events] == [
            "activate",
            "deactivate",
            "activate",
            "transition",
        ]
        assert (
            events[-1]["previous_manifest_id"] == mid
            and events[-1]["manifest_id"] == nextid
        )
        final = _response(own.get(export), 200)
        assert bundle_digest(final["bundle"]) == final["sha256"]
        assert final["bundle"]["origin"] == {
            "organization_id": str(org),
            "project_id": str(project),
        }
        assert final["bundle"]["active_manifest_id"] == nextid
        assert len(final["bundle"]["records"]) == 2

    return {
        "org": org,
        "project": project,
        "key": KEY,
        "records": [rid, copied],
        "receipt": receipt["id"],
        "sql_receipt": {
            "id": receipt["id"],
            "bundle_sha256": portable["sha256"],
            "mappings": receipt["mappings"],
            "actor": str(owner),
            "manifest": mid,
        },
        "history": history,
        "copy_history": copied_history,
        "events": events,
        "export_path": export,
        "record_path": records,
        "activation_path": f"{p}/extensions/activations/{aid}/history",
        "export": final,
        "import_path": import_route,
        "import_request": {**portable, "expected_manifest_id": nextid},
        "receipt_response": receipt,
        "outsider": outsider,
    }


def verify_http(client, proof):
    """Owner sees exact bundle/history; post-restore duplicate import is a replay."""
    assert _response(client.get(proof["export_path"]), 200) == proof["export"]
    for rid, history in zip(
        proof["records"], (proof["history"], proof["copy_history"]), strict=True
    ):
        assert (
            _response(client.get(f"{proof['record_path']}/{rid}/history"), 200)["items"]
            == history
        )
    assert (
        _response(client.get(proof["activation_path"]), 200)["items"] == proof["events"]
    )
    replay = _response(
        client.post(proof["import_path"], json=proof["import_request"]), 200
    )
    assert replay == {**proof["receipt_response"], "replayed": True}


def verify_denied(client, proof):
    for path in (
        proof["export_path"],
        proof["activation_path"],
        f"{proof['record_path']}/{proof['records'][0]}/history",
    ):
        assert client.get(path).status_code in (403, 404)
