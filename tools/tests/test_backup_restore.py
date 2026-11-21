"""R015 safety regressions for local recovery bytes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.backup_restore import (
    _copy_verified,
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
