"""R015 offline recovery drill: PostgreSQL dump plus verified artifact bytes.

The operator must quiesce writers/cleanup and use an isolated instance for
restore. Historical access is quarantined unless independently reconciled with
a separately attested current authority source. This tool never activates a runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.recovery_authority import (
    AUTHORITY_QUERY,
    QUARANTINE_REPORT_QUERY,
    reconciliation_sql,
    safe_human_authority,
)

_ARTIFACT_QUERY = """
SELECT COALESCE(json_agg(row_to_json(a) ORDER BY storage_key, kind), '[]'::json)
FROM (
    SELECT storage_key, sha256, byte_size, 'source' AS kind, true AS required
    FROM transfers.source_assets
    UNION ALL
    SELECT storage_key, sha256, byte_size, 'derived', state = 'ready'
    FROM transfers.derived_artifacts
    UNION ALL
    SELECT storage_key, sha256, byte_size, 'print', true
    FROM cartography.print_exports
    UNION ALL
    SELECT storage_key, sha256, byte_size, 'cad', true
    FROM cad.conversions
    UNION ALL
    SELECT storage_key, sha256, byte_size, 'offline', true
    FROM field.offline_packages
) a;
"""
_DB_CHECK = """
SELECT json_build_object(
    'revision', (SELECT version_num FROM alembic_version),
    'features', (SELECT count(*) FROM spatial.reference_features),
    'sources', (SELECT count(*) FROM spatial.data_sources),
    'layers', (SELECT count(*) FROM spatial.layers),
    'inconsistent_publications', (
      SELECT count(*) FROM (
        SELECT id FROM processing.jobs WHERE status<>'succeeded'
          AND (output_source_id IS NOT NULL OR output_layer_id IS NOT NULL)
        UNION ALL
        SELECT id FROM transfers.jobs WHERE status<>'succeeded'
          AND (artifact_id IS NOT NULL OR (kind='import' AND
            (target_source_id IS NOT NULL OR target_layer_id IS NOT NULL)))
        UNION ALL
        SELECT a.id FROM transfers.derived_artifacts a
        JOIN transfers.jobs j ON j.id=a.job_id
          AND j.organization_id=a.organization_id AND j.project_id=a.project_id
        WHERE a.state='ready' AND j.status<>'succeeded'
      ) partial
    ),
    'feature_fingerprint', (
      SELECT encode(sha256(convert_to(COALESCE(string_agg(
        encode(sha256(convert_to(jsonb_build_array(
          organization_id, project_id, source_id, feature_id, attributes,
          encode(ST_AsEWKB(geometry, 'NDR'), 'hex'), geometry_state,
          content_revision, schema_revision
        )::text, 'UTF8')), 'hex'), ''
        ORDER BY organization_id, project_id, source_id, feature_id), ''), 'UTF8')), 'hex')
      FROM spatial.reference_features
    ),
    'source_fingerprint', (
      SELECT encode(sha256(convert_to(COALESCE(string_agg(
        encode(sha256(convert_to(to_jsonb(s)::text,'UTF8')), 'hex'), ''
        ORDER BY s.id), ''), 'UTF8')), 'hex') FROM spatial.data_sources s
    ),
    'layer_fingerprint', (
      SELECT encode(sha256(convert_to(COALESCE(string_agg(
        encode(sha256(convert_to(to_jsonb(l)::text,'UTF8')), 'hex'), ''
        ORDER BY l.id), ''), 'UTF8')), 'hex') FROM spatial.layers l
    )
);
"""


def _digest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Not a regular backup file: {path.name}")
    sha = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
            size += len(chunk)
    return {"sha256": sha.hexdigest(), "byte_size": size}


def _safe_key(key: str) -> None:
    if (
        not isinstance(key, str)
        or not key
        or not re.fullmatch(r"[a-z0-9][a-z0-9/_.-]{0,199}", key)
        or any(part in ("", ".", "..") for part in key.split("/"))
    ):
        raise RuntimeError("Unsafe artifact storage key")


def _disjoint(a: Path, b: Path) -> None:
    a, b = a.resolve(), b.resolve()
    if a == b or a.is_relative_to(b) or b.is_relative_to(a):
        raise RuntimeError("Backup and artifact roots must be disjoint")


def compute_artifact_manifest(artifact_dir: Path) -> dict[str, dict[str, Any]]:
    """Hash every stored regular file, rejecting unreadable or unsafe trees."""
    if artifact_dir.is_symlink() or not artifact_dir.is_dir():
        raise RuntimeError("Artifact directory missing or unsafe")
    manifest: dict[str, dict[str, Any]] = {}
    for path in sorted(artifact_dir.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("Artifact symbolic links are forbidden")
        if path.is_dir():
            continue
        key = path.relative_to(artifact_dir).as_posix()
        _safe_key(key)
        manifest[key] = _digest(path)
    return manifest


def _exclusive(path: Path):
    return os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb")


def _copy_verified(source: Path, target: Path, expected: dict[str, Any]) -> None:
    if compute_artifact_manifest(source) != expected:
        raise RuntimeError("Artifact manifest missing, extra, or corrupt files")
    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    for key in expected:
        _safe_key(key)
        destination = target / key
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (source / key).open("rb") as src, _exclusive(destination) as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
    if compute_artifact_manifest(target) != expected:
        raise RuntimeError("Copied artifact verification failed")


def _finish_manifest(root: Path, manifest: dict[str, Any]) -> None:
    # Publish the completion marker atomically, after durable bytes. A partial
    # marker is never a valid backup; neither path may overwrite an older file.
    staged = root / ".backup-manifest-staged"
    with _exclusive(staged) as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    os.link(staged, root / "backup-manifest.json")
    staged.unlink()
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_db_identifier(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
        raise RuntimeError(
            "Database/user must be a PostgreSQL identifier, not a connection URI"
        )


def _sql(container: str, user: str, database: str, query: str) -> str:
    _validate_db_identifier(user)
    _validate_db_identifier(database)
    return subprocess.run(
        [
            "docker",
            "exec",
            container,
            "psql",
            "-X",
            "-U",
            user,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-tAc",
            query,
        ],
        env=os.environ,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def _sql_script(container: str, user: str, database: str, script: str) -> None:
    subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-U",
            user,
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=script,
        text=True,
        capture_output=True,
        check=True,
    )


def _authority(container: str, user: str, database: str) -> dict[str, Any]:
    return json.loads(
        _sql(
            container, user, database, "SET row_security=off; " + AUTHORITY_QUERY
        ).splitlines()[-1]
    )


def _inventory(container: str, user: str, database: str) -> tuple[list, dict]:
    references = json.loads(
        _sql(
            container, user, database, "SET row_security=off; " + _ARTIFACT_QUERY
        ).splitlines()[-1]
    )
    checks = json.loads(
        _sql(
            container, user, database, "SET row_security=off; " + _DB_CHECK
        ).splitlines()[-1]
    )
    if checks["inconsistent_publications"]:
        raise RuntimeError("Snapshot contains a partially published unsuccessful job")
    return references, checks


def _verify_references(references: list, files: dict) -> None:
    for ref in references:
        key = ref["storage_key"]
        _safe_key(key)
        if key not in files and not ref["required"]:
            continue
        if files.get(key) != {"sha256": ref["sha256"], "byte_size": ref["byte_size"]}:
            raise RuntimeError(f"Database artifact reference missing or corrupt: {key}")


def backup_docker_postgres_and_artifacts(
    *,
    container_name: str,
    db_user: str,
    db_name: str,
    artifact_dir: Path,
    backup_dir: Path,
    quiesced: bool = False,
) -> dict[str, Any]:
    """Create a recoverable set; a completed manifest is written last."""
    if not quiesced:
        raise RuntimeError(
            "Quiesce all database/artifact writers and expiry cleanup first"
        )
    _disjoint(artifact_dir, backup_dir)
    _validate_db_identifier(db_user)
    _validate_db_identifier(db_name)
    started = datetime.now(UTC)
    references, checks = _inventory(container_name, db_user, db_name)
    authority = _authority(container_name, db_user, db_name)
    files = compute_artifact_manifest(artifact_dir)
    _verify_references(references, files)
    backup_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    dump = backup_dir / "database.sql"
    with _exclusive(dump) as out:
        subprocess.run(
            ["docker", "exec", container_name, "pg_dump", "-U", db_user, "-d", db_name],
            stdout=out,
            stderr=subprocess.PIPE,
            check=True,
        )
        out.flush()
        os.fsync(out.fileno())
    _copy_verified(artifact_dir, backup_dir / "artifacts", files)
    if _inventory(container_name, db_user, db_name) != (references, checks):
        raise RuntimeError("Database changed during backup")
    if _authority(container_name, db_user, db_name) != authority:
        raise RuntimeError("Authority changed during backup")
    if compute_artifact_manifest(artifact_dir) != files:
        raise RuntimeError("Artifact store changed during backup")
    digest = _digest(dump)
    meta = {
        "manifest_version": 3,
        "created_at": started.isoformat(),
        "consistency": "operator-attested-quiesced",
        "database": db_name,
        "dump_file": dump.name,
        "dump_sha256": digest["sha256"],
        "dump_bytes": digest["byte_size"],
        "artifact_count": len(files),
        "artifacts": files,
        "references": references,
        "database_checks": checks,
        "authority_fingerprint": hashlib.sha256(
            json.dumps(authority, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "authorization_reconciled": False,
    }
    _finish_manifest(backup_dir, meta)
    return meta


def verify_isolated_restore_docker(
    *,
    container_name: str,
    db_user: str,
    restore_db_name: str,
    backup_dir: Path,
    restore_artifact_dir: Path,
    isolated_target_confirmed: bool = False,
    current_authority: tuple[str, str, str] | None = None,
    current_authority_confirmed: bool = False,
) -> dict[str, Any]:
    """Restore new targets and quarantine historical authority/jobs.

    To retain unchanged human authority, an operator must separately attest that
    current_authority=(container, user, database) is a trusted current source,
    frozen during comparison. Otherwise the database stays deny-all.
    """
    started = time.monotonic()
    if not isolated_target_confirmed:
        raise RuntimeError(
            "Confirm a dedicated isolated instance, not an application runtime"
        )
    _disjoint(backup_dir, restore_artifact_dir)
    manifest_file = backup_dir / "backup-manifest.json"
    _digest(manifest_file)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 3:
        raise RuntimeError(
            "Incomplete or unsupported backup format; create a v3 snapshot"
        )
    if (current_authority is not None) != current_authority_confirmed:
        raise RuntimeError("Explicitly confirm an independent current authority source")
    _validate_db_identifier(db_user)
    if current_authority is not None:
        _, authority_user, authority_db = current_authority
        _validate_db_identifier(authority_user)
        _validate_db_identifier(authority_db)
        if authority_db == restore_db_name:
            raise RuntimeError(
                "A restored historical database is not current authority"
            )
    if not re.fullmatch(
        r"[a-z][a-z0-9_]{0,62}", restore_db_name
    ) or restore_db_name in {
        manifest["database"],
        "postgres",
        "template0",
        "template1",
    }:
        raise RuntimeError("Unsafe or non-isolated restore database name")
    created_at = datetime.fromisoformat(manifest["created_at"])
    if created_at.tzinfo is None or created_at > datetime.now(UTC):
        raise RuntimeError("Invalid backup consistency timestamp")
    if manifest.get("dump_file") != "database.sql":
        raise RuntimeError("Invalid dump file")
    dump = backup_dir / "database.sql"
    if _digest(dump) != {
        "sha256": manifest["dump_sha256"],
        "byte_size": manifest["dump_bytes"],
    }:
        raise RuntimeError("Backup SQL dump integrity mismatch")
    files = manifest["artifacts"]
    if manifest["artifact_count"] != len(files):
        raise RuntimeError("Backup artifact count mismatch")
    _verify_references(manifest["references"], files)
    if restore_artifact_dir.exists() or restore_artifact_dir.is_symlink():
        raise RuntimeError("Restore artifact target already exists")
    if compute_artifact_manifest(backup_dir / "artifacts") != files:
        raise RuntimeError("Backup artifact integrity mismatch")
    # createdb fails if target already exists. Never DROP an existing database.
    subprocess.run(
        [
            "docker",
            "exec",
            container_name,
            "createdb",
            "-U",
            db_user,
            "--template=template0",
            restore_db_name,
        ],
        check=True,
        capture_output=True,
    )
    try:
        _sql(
            container_name,
            db_user,
            "postgres",
            f'REVOKE CONNECT ON DATABASE "{restore_db_name}" FROM PUBLIC, openvietgis_runtime;',
        )
        if (
            _sql(
                container_name,
                db_user,
                "postgres",
                f"SELECT has_database_privilege('openvietgis_runtime', '{restore_db_name}', 'CONNECT')",
            )
            != "f"
        ):
            raise RuntimeError("Runtime role still has database CONNECT privilege")
        with dump.open("rb") as raw:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    container_name,
                    "psql",
                    "-X",
                    "-U",
                    db_user,
                    "-d",
                    restore_db_name,
                    "-v",
                    "ON_ERROR_STOP=1",
                ],
                stdin=raw,
                check=True,
                capture_output=True,
            )
        references, checks = _inventory(container_name, db_user, restore_db_name)
        if (
            references != manifest["references"]
            or checks != manifest["database_checks"]
        ):
            raise RuntimeError("Restored database inventory mismatch")
        old_authority = _authority(container_name, db_user, restore_db_name)
        if (
            hashlib.sha256(
                json.dumps(old_authority, sort_keys=True).encode("utf-8")
            ).hexdigest()
            != manifest["authority_fingerprint"]
        ):
            raise RuntimeError("Restored authority inventory mismatch")
        latest_authority = (
            _authority(*current_authority) if current_authority is not None else None
        )
        users, members = safe_human_authority(old_authority, latest_authority)
        _sql_script(
            container_name, db_user, restore_db_name, reconciliation_sql(users, members)
        )
        if (
            current_authority is not None
            and _authority(*current_authority) != latest_authority
        ):
            # Authority source changed despite attestation; leave deny-all, no certification.
            _sql_script(
                container_name, db_user, restore_db_name, reconciliation_sql([], [])
            )
            raise RuntimeError("Current authority changed during reconciliation")
        quarantine_report = json.loads(
            _sql(
                container_name,
                db_user,
                restore_db_name,
                "SET row_security=off; " + QUARANTINE_REPORT_QUERY,
            ).splitlines()[-1]
        )
        if _inventory(container_name, db_user, restore_db_name) != (references, checks):
            raise RuntimeError(
                "Reconciliation unexpectedly changed spatial data or artifacts"
            )
        _copy_verified(backup_dir / "artifacts", restore_artifact_dir, files)
        _verify_references(references, compute_artifact_manifest(restore_artifact_dir))
        snapshot_age = (datetime.now(UTC) - created_at).total_seconds()
        return {
            "restored_alembic_revision": checks["revision"],
            "database_checks": checks,
            "dump_sha256_verified": True,
            "restored_artifact_count": len(files),
            "artifact_references_verified": len(references),
            "isolated_restore_passed": True,
            "elapsed_seconds": time.monotonic() - started,
            "snapshot_age_seconds": snapshot_age,
            "authority_quarantined": True,
            "quarantine_report": quarantine_report,
            "authorization_reconciled": current_authority_confirmed,
            "authorization_reconciliation_scope": "database_human_authority_intersection",
            "runtime_activation_performed": False,
            "production_ready": False,
        }
    except BaseException:
        # Never drop a target. A partial or failed recovery cannot remain
        # connectable; the operator inspects it only after explicit isolation.
        _sql(
            container_name,
            db_user,
            "postgres",
            f'ALTER DATABASE "{restore_db_name}" ALLOW_CONNECTIONS false;',
        )
        raise
