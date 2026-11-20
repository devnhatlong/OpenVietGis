"""Atomic, SHA-256-verified immutable local object store."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from openvietgis_api.domains.transfers.ports import (
    TransferArtifactUnavailableError,
    TransferValidationError,
)

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9/_.-]{0,199}$")


class LocalObjectStore:
    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        if not _KEY_RE.match(storage_key) or ".." in storage_key.split("/"):
            raise TransferValidationError("INVALID_STORAGE_KEY", "Invalid storage key.")
        target = (self._root / storage_key).resolve()
        if self._root not in target.parents:
            raise TransferValidationError("INVALID_STORAGE_KEY", "Invalid storage key.")
        return target

    def put_bytes(self, storage_key: str, data: bytes) -> tuple[str, int]:
        target = self._resolve(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp_", dir=str(target.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return digest, len(data)

    def get_bytes(self, storage_key: str, *, expected_sha256: str) -> bytes:
        target = self._resolve(storage_key)
        if not target.is_file():
            raise TransferArtifactUnavailableError(
                "ARTIFACT_MISSING", "Stored immutable object is missing."
            )
        data = target.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            raise TransferArtifactUnavailableError(
                "ARTIFACT_CORRUPTED", "Stored immutable object failed integrity check."
            )
        return data

    def delete_object(self, storage_key: str) -> None:
        try:
            target = self._resolve(storage_key)
        except TransferValidationError:
            return
        target.unlink(missing_ok=True)
