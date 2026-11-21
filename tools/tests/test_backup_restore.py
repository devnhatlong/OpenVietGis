"""R015 safety regressions for local recovery bytes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tools.backup_restore import (
    _copy_verified,
    _finish_manifest,
    _verify_references,
    backup_docker_postgres_and_artifacts,
    compute_artifact_manifest,
    verify_isolated_restore_docker,
)


def test_verified_artifact_copy_and_tamper(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    (store / "data").mkdir()
    (store / "data" / "sample.bin").write_bytes(b"synthetic geometry")
    manifest = compute_artifact_manifest(store)
    target = tmp_path / "fresh"
    _copy_verified(store, target, manifest)
    assert (target / "data" / "sample.bin").read_bytes() == b"synthetic geometry"
    with pytest.raises(FileExistsError):
        _copy_verified(store, target, manifest)
    (store / "data" / "sample.bin").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="corrupt"):
        _copy_verified(store, tmp_path / "bad", manifest)
    (store / "data" / "sample.bin").unlink()
    with pytest.raises(RuntimeError, match="missing"):
        _copy_verified(store, tmp_path / "missing", manifest)


def test_reject_symlink_and_traversal(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    other = tmp_path / "external"
    other.write_bytes(b"outside store")
    (store / "link").symlink_to(other)
    with pytest.raises(RuntimeError, match="symbolic links"):
        compute_artifact_manifest(store)
    for key in ("../outside", "/absolute", "a/../../b", "a//b", "a\\b"):
        with pytest.raises(RuntimeError, match="Unsafe"):
            _verify_references([{"storage_key": key, "required": False}], {})


def test_required_database_reference_cannot_be_missing() -> None:
    reference = {
        "storage_key": "assets/sample.bin",
        "required": True,
        "sha256": "a" * 64,
        "byte_size": 10,
    }
    with pytest.raises(RuntimeError, match="missing or corrupt"):
        _verify_references([reference], {})


def test_restore_rejects_old_manifest_and_requires_isolation(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    backup.mkdir()
    (backup / "backup-manifest.json").write_text(json.dumps({"database": "source"}))
    kwargs = {
        "container_name": "unused",
        "db_user": "unused",
        "restore_db_name": "restore_test",
        "backup_dir": backup,
        "restore_artifact_dir": tmp_path / "restore",
    }
    with pytest.raises(RuntimeError, match="isolated instance"):
        verify_isolated_restore_docker(**kwargs)
    with pytest.raises(RuntimeError, match="unsupported backup"):
        verify_isolated_restore_docker(**kwargs, isolated_target_confirmed=True)


def test_backup_requires_consistency_attestation(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Quiesce"):
        backup_docker_postgres_and_artifacts(
            container_name="unused",
            db_user="unused",
            db_name="source",
            artifact_dir=tmp_path / "store",
            backup_dir=tmp_path / "backup",
        )


def test_completion_marker_is_atomic_and_never_overwritten(tmp_path: Path) -> None:
    root = tmp_path / "backup"
    root.mkdir()
    original = {"manifest_version": 3, "marker": "original"}
    _finish_manifest(root, original)
    assert json.loads((root / "backup-manifest.json").read_text()) == original
    assert not (root / ".backup-manifest-staged").exists()
    with pytest.raises(FileExistsError):
        _finish_manifest(root, {"marker": "replacement"})
    assert json.loads((root / "backup-manifest.json").read_text()) == original


@pytest.mark.parametrize("failure", ["missing", "tampered", "same_authority", "future"])
def test_v3_restore_preflight_fails_before_creation(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    backup = tmp_path / "backup"
    backup.mkdir()
    artifacts = backup / "artifacts"
    artifacts.mkdir()
    payload = b"GIS synthetic artifact"
    original = artifacts / "sample.bin"
    original.write_bytes(payload)
    sql = b"SELECT 1;"
    (backup / "database.sql").write_bytes(sql)
    manifest = {
        "manifest_version": 3,
        "created_at": datetime.now(UTC).isoformat(),
        "database": "source",
        "dump_file": "database.sql",
        "dump_bytes": len(sql),
        "dump_sha256": hashlib.sha256(sql).hexdigest(),
        "artifact_count": 1,
        "artifacts": compute_artifact_manifest(artifacts),
        "references": [
            {
                "storage_key": "sample.bin",
                "required": True,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_size": len(payload),
            }
        ],
    }
    kwargs = {
        "container_name": "unused",
        "db_user": "unused",
        "restore_db_name": "new_restore",
        "backup_dir": backup,
        "restore_artifact_dir": tmp_path / "restore",
        "isolated_target_confirmed": True,
    }
    if failure == "missing":
        original.unlink()
    elif failure == "tampered":
        original.write_bytes(b"corrupted")
    elif failure == "same_authority":
        kwargs["current_authority"] = (
            "different-name-for-same-db",
            "unused",
            "new_restore",
        )
        kwargs["current_authority_confirmed"] = True
    else:
        manifest["created_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    _finish_manifest(backup, manifest)

    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe preflight reached database creation")

    monkeypatch.setattr("tools.backup_restore.subprocess.run", forbidden)
    with pytest.raises(RuntimeError):
        verify_isolated_restore_docker(**kwargs)
    assert not (tmp_path / "restore").exists()
