"""R015 offline recovery drill: PostgreSQL dump plus verified artifact bytes.

The operator must quiesce writers/cleanup and use an isolated instance for
restore. This tool does not reconcile current authorization or certify readiness.
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
    'layers', (SELECT count(*) FROM spatial.layers)
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
        or "\\" in key
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
    if compute_artifact_manifest(target) != expected:
        raise RuntimeError("Copied artifact verification failed")


def _sql(container: str, user: str, database: str, query: str) -> str:
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
    started = datetime.now(UTC)
    references, checks = _inventory(container_name, db_user, db_name)
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
    _copy_verified(artifact_dir, backup_dir / "artifacts", files)
    if _inventory(container_name, db_user, db_name) != (references, checks):
        raise RuntimeError("Database changed during backup")
    if compute_artifact_manifest(artifact_dir) != files:
        raise RuntimeError("Artifact store changed during backup")
    digest = _digest(dump)
    meta = {
        "manifest_version": 2,
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
        "authorization_reconciled": False,
    }
    with _exclusive(backup_dir / "backup-manifest.json") as stream:
        stream.write(json.dumps(meta, indent=2, sort_keys=True).encode("utf-8"))
    return meta


def verify_isolated_restore_docker(
    *,
    container_name: str,
    db_user: str,
    restore_db_name: str,
    backup_dir: Path,
    restore_artifact_dir: Path,
    isolated_target_confirmed: bool = False,
) -> dict[str, Any]:
    """Verify and restore into new targets; leave the isolated DB for inspection."""
    started = time.monotonic()
    if not isolated_target_confirmed:
        raise RuntimeError(
            "Confirm a dedicated isolated instance, not an application runtime"
        )
    _disjoint(backup_dir, restore_artifact_dir)
    manifest_file = backup_dir / "backup-manifest.json"
    _digest(manifest_file)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 2:
        raise RuntimeError("Incomplete or unsupported backup format")
    if not re.fullmatch(
        r"[a-z][a-z0-9_]{0,62}", restore_db_name
    ) or restore_db_name in {
        manifest["database"],
        "postgres",
        "template0",
        "template1",
    }:
        raise RuntimeError("Unsafe or non-isolated restore database name")
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
    _sql(
        container_name,
        db_user,
        "postgres",
        f'REVOKE CONNECT ON DATABASE "{restore_db_name}" FROM PUBLIC;',
    )
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
    if references != manifest["references"] or checks != manifest["database_checks"]:
        raise RuntimeError("Restored database inventory mismatch")
    _copy_verified(backup_dir / "artifacts", restore_artifact_dir, files)
    _verify_references(references, compute_artifact_manifest(restore_artifact_dir))
    return {
        "restored_alembic_revision": checks["revision"],
        "database_checks": checks,
        "dump_sha256_verified": True,
        "restored_artifact_count": len(files),
        "artifact_references_verified": len(references),
        "isolated_restore_passed": True,
        "elapsed_seconds": time.monotonic() - started,
        "authorization_reconciled": False,
        "production_ready": False,
    }
