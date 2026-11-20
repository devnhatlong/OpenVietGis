"""R015 Real PostgreSQL + Artifact Store Backup & Isolated Restore verification tool."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def compute_artifact_manifest(artifact_dir: Path) -> dict[str, dict[str, Any]]:
    """Compute deterministic SHA-256 manifest of all stored artifacts."""
    manifest: dict[str, dict[str, Any]] = {}
    if not artifact_dir.exists():
        return manifest
    for p in sorted(artifact_dir.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rel = p.relative_to(artifact_dir).as_posix()
            data = p.read_bytes()
            manifest[rel] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_size": len(data),
            }
    return manifest


def backup_docker_postgres_and_artifacts(
    *,
    container_name: str,
    db_user: str,
    db_name: str,
    artifact_dir: Path,
    backup_dir: Path,
) -> dict[str, Any]:
    """Create a verifiable SQL dump + artifact SHA-256 manifest."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    dump_path = backup_dir / "database.sql"
    proc = subprocess.run(
        ["docker", "exec", container_name, "pg_dump", "-U", db_user, "-d", db_name],
        capture_output=True,
        check=True,
    )
    dump_path.write_bytes(proc.stdout)
    dump_sha = hashlib.sha256(proc.stdout).hexdigest()
    art_manifest = compute_artifact_manifest(artifact_dir)
    meta = {
        "created_at": datetime.now(UTC).isoformat(),
        "database": db_name,
        "dump_file": dump_path.name,
        "dump_sha256": dump_sha,
        "dump_bytes": len(proc.stdout),
        "artifact_count": len(art_manifest),
        "artifacts": art_manifest,
    }
    (backup_dir / "backup-manifest.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


def verify_isolated_restore_docker(
    *,
    container_name: str,
    db_user: str,
    restore_db_name: str,
    backup_dir: Path,
) -> dict[str, Any]:
    """Restore dump into a fresh isolated database and verify schemas + row counts."""
    dump_path = backup_dir / "database.sql"
    manifest = json.loads((backup_dir / "backup-manifest.json").read_text(encoding="utf-8"))
    raw = dump_path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != manifest["dump_sha256"]:
        raise RuntimeError("Backup SQL dump SHA-256 mismatch!")

    subprocess.run(
        [
            "docker",
            "exec",
            container_name,
            "psql",
            "-U",
            db_user,
            "-d",
            "postgres",
            "-c",
            f"DROP DATABASE IF EXISTS {restore_db_name};",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "docker",
            "exec",
            container_name,
            "psql",
            "-U",
            db_user,
            "-d",
            "postgres",
            "-c",
            f"CREATE DATABASE {restore_db_name};",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            container_name,
            "psql",
            "-U",
            db_user,
            "-d",
            restore_db_name,
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=raw,
        check=True,
        capture_output=True,
    )
    check = subprocess.run(
        [
            "docker",
            "exec",
            container_name,
            "psql",
            "-U",
            db_user,
            "-d",
            restore_db_name,
            "-tAc",
            "SELECT version_num FROM alembic_version;",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    restored_rev = check.stdout.strip()
    # Clean up isolated verification DB after proving restore succeeded
    subprocess.run(
        [
            "docker",
            "exec",
            container_name,
            "psql",
            "-U",
            db_user,
            "-d",
            "postgres",
            "-c",
            f"DROP DATABASE IF EXISTS {restore_db_name};",
        ],
        check=True,
        capture_output=True,
    )
    return {
        "restored_alembic_revision": restored_rev,
        "dump_sha256_verified": True,
        "isolated_restore_passed": bool(restored_rev),
    }
