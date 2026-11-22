"""Opt-in isolated R015 schema 0019 recovery drill from the pinned synthetic v2 checkpoint.

Run only on the new disposable, explicitly labeled loopback Docker container.
Creates four new synthetic databases and private directories; never changes the
original fixture, pre-existing databases, or production. Leaves synthetic targets
for inspection. No runtime CONNECT privilege is granted.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from tools.backup_restore import (
    _copy_verified,
    _digest,
    _inventory,
    _sql,
    backup_docker_postgres_and_artifacts,
    verify_isolated_restore_docker,
)
from tools.r015_extension_oracle import (
    REVISION,
    fingerprint,
    seed,
    verify_denied,
    verify_http,
)

CONTAINER = "ovg-r015-head-postgres"
DB_USER = "openvietgis"
# Explicitly disposable credentials and loopback for the dedicated drill only.
ADMIN_URL = "postgresql+psycopg://openvietgis:openvietgis@127.0.0.1:54341/"
FIXTURE = Path("/opt/openvietgis-remediation-018/dist/remediation018/backup-v2-run1")


def _new_database(name: str, dump: Path) -> None:
    assert name.startswith("openvietgis_r015_")
    subprocess.run(
        [
            "docker",
            "exec",
            CONTAINER,
            "createdb",
            "-U",
            DB_USER,
            "--template=template0",
            name,
        ],
        capture_output=True,
        check=True,
    )
    _sql(
        CONTAINER,
        DB_USER,
        "postgres",
        f'REVOKE CONNECT ON DATABASE "{name}" FROM PUBLIC, openvietgis_runtime;',
    )
    with dump.open("rb") as raw:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                CONTAINER,
                "psql",
                "-X",
                "-U",
                DB_USER,
                "-d",
                name,
                "-v",
                "ON_ERROR_STOP=1",
            ],
            stdin=raw,
            capture_output=True,
            check=True,
        )


def _session(engine, user, issue_session_token):
    session_id = uuid4()
    token, digest = issue_session_token(session_id)
    with engine.begin() as conn:
        conn.execute(
            text("""
          INSERT INTO identity.web_sessions
            (id,user_id,identity_link_id,secret_hash,issued_at,expires_at)
          SELECT :id, user_id, id, :digest, now(), now()+interval '1 hour'
          FROM identity.identity_links WHERE user_id=:who ORDER BY id LIMIT 1
        """),
            {"id": session_id, "digest": digest, "who": user},
        )
    return token


def main() -> None:
    if os.environ.get("OPENVIETGIS_R015_SYNTHETIC_DRILL") != "confirmed":
        raise RuntimeError("Confirm dedicated synthetic R015 drill explicitly")
    # Explicit identity/port gate: reject even a same-name accidental target.
    binding = subprocess.check_output(
        [
            "docker",
            "inspect",
            "--format",
            '{{index .Config.Labels "org.openvietgis.purpose"}} {{json .HostConfig.PortBindings}}',
            CONTAINER,
        ],
        text=True,
    ).strip()
    label, port_json = binding.split(" ", 1)
    assert label == "r015-head-synthetic"
    assert json.loads(port_json) == {
        "5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "54341"}]
    }
    # Only the exact parent checkpoint's independently hashed synthetic input.
    fixture_manifest = FIXTURE / "backup-manifest.json"
    assert _digest(fixture_manifest)["sha256"] == (
        "aa415676b92db959c6844d12d6b60da83cab608b5907896344a48b818edd6a07"
    )
    baseline = json.loads(fixture_manifest.read_text())
    assert baseline["manifest_version"] == 2
    assert _digest(FIXTURE / "database.sql") == {
        "sha256": baseline["dump_sha256"],
        "byte_size": baseline["dump_bytes"],
    }
    suffix = uuid4().hex[:8]
    root = Path("dist/r015") / suffix
    root.mkdir(mode=0o700, parents=True)
    source = f"openvietgis_r015_src_{suffix}"
    current = f"openvietgis_r015_current_{suffix}"
    reconciled = f"openvietgis_r015_reconciled_{suffix}"
    quarantine = f"openvietgis_r015_quarantine_{suffix}"
    source_files = root / "source-artifacts"
    _copy_verified(FIXTURE / "artifacts", source_files, baseline["artifacts"])
    _new_database(source, FIXTURE / "database.sql")

    os.environ.update(
        {
            "OPENVIETGIS_ENVIRONMENT": "test",
            "OPENVIETGIS_DATABASE_URL": ADMIN_URL + reconciled,
            "OPENVIETGIS_RUNTIME_DATABASE_URL": "postgresql+psycopg://openvietgis_runtime:synthetic@127.0.0.1:54341/"
            + reconciled,
            "OPENVIETGIS_ARTIFACT_STORE_DIR": str(
                (root / "reconciled-artifacts").resolve()
            ),
            "OPENVIETGIS_APPLICATION_SESSION_SECRET": "synthetic-r015-session",
            "OPENVIETGIS_CSRF_SECRET": "synthetic-r015-csrf",
            "OPENVIETGIS_BOOTSTRAP_SECRET": "synthetic-r015-bootstrap",
        }
    )
    # Migrate the exact pinned 0018 fixture, before any 0019 data is written.
    migration_env = os.environ.copy() | {
        "OPENVIETGIS_DATABASE_URL": ADMIN_URL + source,
        "OPENVIETGIS_MIGRATION_DATABASE_URL": ADMIN_URL + source,
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "apps/api/alembic.ini",
            "upgrade",
            "head",
        ],
        env=migration_env,
        check=True,
    )
    assert (
        _sql(CONTAINER, DB_USER, source, "SELECT version_num FROM alembic_version")
        == REVISION
    )
    from fastapi.testclient import TestClient
    from openvietgis_api.adapters.http.security import get_db_session
    from openvietgis_api.adapters.storage.local_object_store import LocalObjectStore
    from openvietgis_api.main import create_app
    from openvietgis_api.security.secrets import (
        digest_secret,
        generate_service_credential_secret,
    )
    from openvietgis_api.security.sessions import issue_session_token

    source_engine = create_engine(ADMIN_URL + source)
    with source_engine.begin() as conn:
        row = (
            conn.execute(
                text("""
            SELECT e.id AS export_id,e.sha256,e.byte_size,e.output_format,
                   e.organization_id AS org,e.project_id AS project,
                   ow.user_id AS owner, m.user_id AS member, m.id AS membership
              FROM cartography.print_exports e
              JOIN org.organization_memberships ow ON ow.organization_id=e.organization_id
                    AND ow.role='owner' AND ow.status='active'
              JOIN org.organization_memberships m ON m.organization_id=e.organization_id
                    AND m.role='member' AND m.status='active'
              WHERE EXISTS (SELECT 1 FROM processing.jobs j
                WHERE j.organization_id=e.organization_id AND j.project_id=e.project_id)
              ORDER BY e.id LIMIT 1
        """)
            )
            .mappings()
            .one()
        )
        info = dict(row)
        org, project, owner, member = (
            info[k] for k in ("org", "project", "owner", "member")
        )
        grant_id, principal_id, credential_id, processing_id, transfer_id = [
            uuid4() for _ in range(5)
        ]
        common = {
            "org": org,
            "project": project,
            "owner": owner,
            "member": member,
            "membership": info["membership"],
        }
        conn.execute(
            text("""
          INSERT INTO org.resource_grants(
            id,organization_id,subject_kind,membership_id,scope_kind,project_id,
            role,created_at,created_by_actor_type,created_by_actor_id)
          VALUES(:id,:org,'membership',:membership,'project',:project,'editor',now(),'human',:owner)
          ON CONFLICT DO NOTHING
        """),
            common | {"id": grant_id},
        )
        grant_id = conn.execute(
            text("""
          SELECT id FROM org.resource_grants WHERE membership_id=:membership
           AND organization_id=:org AND project_id=:project AND role='editor'
           AND revoked_at IS NULL
        """),
            common,
        ).scalar_one()
        conn.execute(
            text("""
          INSERT INTO org.service_principals(
            id,organization_id,name,status,created_at,created_by_actor_type,created_by_actor_id)
          VALUES(:id,:org,'Synthetic R015 machine','active',now(),'human',:owner)
        """),
            common | {"id": principal_id},
        )
        service_token = generate_service_credential_secret(credential_id)
        conn.execute(
            text("""
          INSERT INTO org.service_credentials(
            id,organization_id,service_principal_id,name,prefix,secret_hash,created_at)
          VALUES(:id,:org,:pid,'Synthetic R015 credential',:prefix,:digest,now())
        """),
            common
            | {
                "id": credential_id,
                "pid": principal_id,
                "prefix": service_token[:12],
                "digest": digest_secret(service_token),
            },
        )
        conn.execute(
            text("""
          INSERT INTO org.resource_grants(
            id,organization_id,subject_kind,service_principal_id,scope_kind,project_id,
            role,created_at,created_by_actor_type,created_by_actor_id)
          VALUES(:id,:org,'service_principal',:pid,'project',:project,'editor',now(),'human',:owner)
        """),
            common | {"id": uuid4(), "pid": principal_id},
        )
        conn.execute(
            text("""
          INSERT INTO org.invitations(
            id,organization_id,status,target_kind,target_user_id,organization_role,
            token_hash,token_prefix,expires_at,created_at,created_by_actor_type,created_by_actor_id)
          VALUES(:id,:org,'pending','user',:member,'member',:digest,'synthetic-r015',
            now()+interval '1 hour',now(),'human',:owner)
        """),
            common | {"id": uuid4(), "digest": digest_secret("synthetic-invite-only")},
        )
        conn.execute(
            text("""
          INSERT INTO processing.jobs(id,organization_id,project_id,algorithm_id,operation_id,
            status,actor_type,actor_id,input_refs,parameters,output_name,output_crs,engine_version,
            attempt_count,created_at,updated_at)
          SELECT :id,organization_id,project_id,algorithm_id,:operation,'running','human',:owner,
            input_refs,parameters,'Synthetic interrupted',output_crs,engine_version,1,now(),now()
          FROM processing.jobs WHERE organization_id=:org AND project_id=:project
          ORDER BY id LIMIT 1
        """),
            common | {"id": processing_id, "operation": f"recovery-{suffix}"},
        )
        conn.execute(
            text("""
          INSERT INTO transfers.jobs(id,organization_id,project_id,operation_id,kind,
            request_fingerprint,status,actor_type,actor_id,actor_display_snapshot,
            source_asset_id,attempt_count,created_at,updated_at)
          SELECT :id,organization_id,project_id,:operation,'import',repeat('a',64),
            'active','human',:owner,'Synthetic owner',id,1,now(),now()
          FROM transfers.source_assets WHERE organization_id=:org AND project_id=:project
          ORDER BY id LIMIT 1
        """),
            common | {"id": transfer_id, "operation": uuid4()},
        )
        conn.execute(
            text("""
          INSERT INTO transfers.job_attempts(id,organization_id,project_id,job_id,
            attempt_number,status,actor_type,actor_id,started_at)
          VALUES(:id,:org,:project,:job,1,'active','human',:owner,now())
        """),
            common | {"id": uuid4(), "job": transfer_id},
        )
    old_owner_session = _session(source_engine, owner, issue_session_token)
    old_member_session = _session(source_engine, member, issue_session_token)
    extension_proof = seed(
        source_engine,
        ADMIN_URL + source,
        org,
        project,
        owner,
        member,
        old_owner_session,
        old_member_session,
    )
    extension_before = fingerprint(source_engine, extension_proof)
    source_engine.dispose()

    # A test-only key independent of the snapshot and both restored artifact roots.
    # It is never printed, copied into backup, or committed.
    signing_key = root / "synthetic-manifest.key"
    with os.fdopen(
        os.open(signing_key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
    ) as out:
        out.write(secrets.token_bytes(32))
    provenance = "synthetic-r015-head-0019-drill"
    snapshot = backup_docker_postgres_and_artifacts(
        container_name=CONTAINER,
        db_user=DB_USER,
        db_name=source,
        artifact_dir=source_files,
        backup_dir=root / "snapshot",
        manifest_key_file=signing_key,
        provenance=provenance,
        quiesced=True,
    )
    _new_database(current, root / "snapshot" / "database.sql")
    authority_engine = create_engine(ADMIN_URL + current)
    with authority_engine.begin() as conn:
        # Real post-snapshot changes, never applied to original/production DB.
        conn.execute(
            text("UPDATE org.resource_grants SET revoked_at=now() WHERE id=:id"),
            {"id": grant_id},
        )
        conn.execute(
            text("UPDATE org.service_credentials SET revoked_at=now() WHERE id=:id"),
            {"id": credential_id},
        )
        conn.execute(
            text("UPDATE identity.web_sessions SET revoked_at=now() WHERE user_id=:id"),
            {"id": member},
        )
    authority_engine.dispose()

    # The recovery function cannot access source artifact root: input is backup only.
    # Keep source files for inspection under a different name while restoring.
    source_files.rename(root / "original-files-offline")
    base_args = {
        "container_name": CONTAINER,
        "db_user": DB_USER,
        "backup_dir": root / "snapshot",
        "manifest_key_file": signing_key,
        "expected_provenance": provenance,
        "isolated_target_confirmed": True,
    }
    # On a separate test copy only, replace BOTH dump and unsigned checksum
    # fields; the external authentication key is not available to an attacker.
    tampered_dir = root / "tampered-copy"
    shutil.copytree(root / "snapshot", tampered_dir)
    tampered_sql = tampered_dir / "database.sql"
    tampered_sql.write_bytes(b"SELECT 42;")
    tampered_manifest = tampered_dir / "backup-manifest.json"
    changed = json.loads(tampered_manifest.read_text())
    changed["dump_sha256"] = _digest(tampered_sql)["sha256"]
    changed["dump_bytes"] = tampered_sql.stat().st_size
    tampered_manifest.write_text(json.dumps(changed))
    tampered_db = f"openvietgis_r015_tampered_{suffix}"
    try:
        verify_isolated_restore_docker(
            **(base_args | {"backup_dir": tampered_dir}),
            restore_db_name=tampered_db,
            restore_artifact_dir=root / "tampered-artifacts",
        )
    except RuntimeError as error:
        assert "manifest authentication failed" in str(error)
    else:
        raise AssertionError("Tampered snapshot was accepted")
    assert (
        _sql(
            CONTAINER,
            DB_USER,
            "postgres",
            f"SELECT NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='{tampered_db}')",
        )
        == "t"
    )
    assert not (root / "tampered-artifacts").exists()

    closed = verify_isolated_restore_docker(
        **base_args,
        restore_db_name=quarantine,
        restore_artifact_dir=root / "quarantine-artifacts",
    )
    assert (
        closed["manifest_authenticated"] and closed["backup_provenance"] == provenance
    )
    assert not closed["authorization_reconciled"] and closed["authority_quarantined"]
    assert closed["quarantine_report"]["active_users"] == 0
    assert closed["quarantine_report"]["active_memberships"] == 0
    assert closed["quarantine_report"]["active_grants"] == 0

    report = verify_isolated_restore_docker(
        **base_args,
        restore_db_name=reconciled,
        restore_artifact_dir=root / "reconciled-artifacts",
        current_authority=(CONTAINER, DB_USER, current),
        current_authority_confirmed=True,
    )
    assert (
        report["manifest_authenticated"]
        and report["manifest_key_id"] == snapshot["key_id"]
    )
    assert report["authorization_reconciled"] and not report["production_ready"]
    for key in (
        "unrevoked_sessions",
        "unrevoked_service_credentials",
        "active_service_principals",
        "pending_invitations",
        "unrevoked_offline_packages",
    ):
        assert report["quarantine_report"][key] == 0
    assert report["quarantine_report"]["processing_jobs_quarantined"] >= 1
    assert report["quarantine_report"]["transfer_jobs_quarantined"] >= 1
    assert report["quarantine_report"]["transfer_attempts_quarantined"] >= 1
    assert report["database_checks"] == snapshot["database_checks"]
    for db in [quarantine, reconciled]:
        assert (
            _sql(
                CONTAINER,
                DB_USER,
                "postgres",
                f"SELECT has_database_privilege('openvietgis_runtime','{db}','CONNECT')",
            )
            == "f"
        )

    for db in (quarantine, reconciled):
        ext_engine = create_engine(ADMIN_URL + db)
        assert fingerprint(ext_engine, extension_proof) == extension_before
        ext_engine.dispose()

    # Exercise actual application storage reader with every required restored object.
    store = LocalObjectStore(root / "reconciled-artifacts")
    for ref in snapshot["references"]:
        if ref["required"]:
            data = store.get_bytes(ref["storage_key"], expected_sha256=ref["sha256"])
            assert len(data) == ref["byte_size"]

    # The actual HTTP auth+authorization+artifact adapters run under the restricted
    # role through an explicitly isolated test-only session dependency. No runtime
    # CONNECT or application services are enabled on either recovered database.
    target_engine = create_engine(ADMIN_URL + reconciled)
    owner_token = _session(target_engine, owner, issue_session_token)
    # This fresh verified-identity test session proves a revoked project membership
    # cannot gain old grant authority even after authentication succeeds.
    member_token = _session(target_engine, member, issue_session_token)
    outsider_token = _session(
        target_engine, extension_proof["outsider"], issue_session_token
    )
    runtime_engine = create_engine(ADMIN_URL + reconciled)

    @event.listens_for(runtime_engine, "connect")
    def restricted_role(dbapi_connection, _):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET ROLE openvietgis_runtime")
            cursor.execute("SELECT current_user")
            assert cursor.fetchone()[0] == "openvietgis_runtime"
        dbapi_connection.commit()

    def isolated_db():
        with Session(runtime_engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = isolated_db
    url = f"/api/v1/organizations/{org}/projects/{project}"
    download = f"{url}/cartography/exports/{info['export_id']}/download"
    with TestClient(app) as client:
        for token in (old_owner_session, old_member_session):
            client.cookies.set("ovg_session", token)
            assert client.get(download).status_code == 401
        client.cookies.clear()
        assert (
            client.get(
                download, headers={"Authorization": "Bearer " + service_token}
            ).status_code
            == 401
        )
        client.cookies.set("ovg_session", member_token)
        assert client.get("/api/v1/me").status_code == 200
        assert client.get(download).status_code in (403, 404)
        verify_denied(client, extension_proof)
        client.cookies.set("ovg_session", outsider_token)
        assert client.get("/api/v1/me").status_code == 200
        verify_denied(client, extension_proof)
        client.cookies.set("ovg_session", owner_token)
        response = client.get(download)
        assert response.status_code == 200, response.text[:200]
        assert len(response.content) == info["byte_size"]
        assert hashlib.sha256(response.content).hexdigest() == info["sha256"]
        assert response.content.startswith(b"%PDF") or response.content.startswith(
            b"\x89PNG"
        )
        csrf = client.get("/api/v1/auth/csrf")
        assert csrf.status_code == 200
        client.headers["X-OpenVietGIS-CSRF"] = csrf.json()["token"]
        verify_http(client, extension_proof)
        p_response = client.post(f"{url}/processing/jobs/{processing_id}/retry")
        assert p_response.status_code == 409, p_response.text
        assert p_response.json()["code"] == "RECOVERY_QUARANTINED"
        t_response = client.post(f"{url}/jobs/{transfer_id}/retry")
        assert t_response.status_code == 409, t_response.text
    runtime_engine.dispose()
    assert fingerprint(target_engine, extension_proof) == extension_before
    target_engine.dispose()
    checks_after = _inventory(CONTAINER, DB_USER, reconciled)[1]
    assert checks_after == snapshot["database_checks"]

    print(
        json.dumps(
            {
                "drill_root": str(root),
                "schema_revision": REVISION,
                "extension_table_fingerprints": extension_before,
                "extension_portable_export_sha256": extension_proof["export"]["sha256"],
                "extension_replayed_receipt_id": extension_proof["receipt"],
                "extension_checks": {
                    "full_rows_original_quarantine_reconciled_and_post_replay_equal": True,
                    "scoped_ownership_core_geometry_pins_and_receipt_mapping_equal": True,
                    "forced_rls_and_append_only_privileges": True,
                    "legacy_baselines_preserved": True,
                    "owner_history_export_receipt_replay_equal": True,
                    "revoked_member_and_outsider_fresh_sessions_denied": True,
                },
                "closed_recovery": closed,
                "reconciled_recovery": report,
                "application_checks": {
                    "tampered_dump_and_manifest_denied_before_db_creation": True,
                    "old_sessions_denied": 2,
                    "old_service_credential_denied": True,
                    "revoked_grant_fresh_session_denied": True,
                    "unchanged_owner_print_download_verified": True,
                    "interrupted_processing_and_transfer_retry_denied": True,
                    "spatial_fingerprints_unchanged_after_retry": True,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
