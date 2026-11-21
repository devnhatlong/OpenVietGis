"""Integrity-bound browser projection and scoped offline intent validation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.spatial.domain import (
    FieldType,
    SourceField,
    SpatialValidationError,
    canonical_attribute_value,
)

MAX_SNAPSHOT_BYTES = 25 * 1024 * 1024


def canonical_json(data: Any) -> bytes:
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def embed_snapshot(gpkg: bytes, snapshot: dict[str, Any]) -> tuple[bytes, str]:
    """Store a lossless typed projection inside the checksummed GeoPackage.

    The normal vector table stays interoperable; this private application table
    preserves decimal strings, issuance scope and nullable field descriptions.
    """
    data = canonical_json(snapshot)
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise PlatformValidationError("offline snapshot size exceeded; narrow AOI")
    fd, name = tempfile.mkstemp(suffix=".gpkg")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(gpkg)
        conn = sqlite3.connect(name)
        try:
            conn.execute("CREATE TABLE ovg_offline_snapshot (payload BLOB NOT NULL)")
            conn.execute("INSERT INTO ovg_offline_snapshot VALUES (?)", (data,))
            conn.commit()
        finally:
            conn.close()
        return Path(name).read_bytes(), hashlib.sha256(data).hexdigest()
    finally:
        Path(name).unlink(missing_ok=True)


def extract_snapshot(gpkg: bytes, expected_sha256: str) -> bytes:
    fd, name = tempfile.mkstemp(suffix=".gpkg")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(gpkg)
        conn = sqlite3.connect(f"file:{name}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT payload FROM ovg_offline_snapshot").fetchone()
        finally:
            conn.close()
        if row is None or not isinstance(row[0], bytes):
            raise ValueError("projection unavailable")
        payload = row[0]
        if (
            len(payload) > MAX_SNAPSHOT_BYTES
            or hashlib.sha256(payload).hexdigest() != expected_sha256
        ):
            raise ValueError("projection checksum mismatch")
        return payload
    except (sqlite3.Error, ValueError) as exc:
        raise PlatformValidationError(
            "offline snapshot missing or invalid; create a fresh package", code="PACKAGE_INVALID"
        ) from exc
    finally:
        Path(name).unlink(missing_ok=True)


def validate_bbox(bbox: dict[str, float]) -> None:
    keys = {"min_x", "min_y", "max_x", "max_y"}
    if set(bbox) != keys or not all(math.isfinite(v) for v in bbox.values()):
        raise PlatformValidationError("AOI requires four finite native CRS coordinates")
    if bbox["min_x"] >= bbox["max_x"] or bbox["min_y"] >= bbox["max_y"]:
        raise PlatformValidationError("AOI bounds must be ordered and nonempty")


def validate_offline_ops(snapshot: dict[str, Any], operations: list[dict[str, Any]]) -> None:
    """Only included feature attributes or point creation inside issued native AOI."""
    if not operations or len(operations) > 2000:
        raise PlatformValidationError("offline group requires 1..2000 operations")
    feature_ids = {f["feature_id"] for f in snapshot["features"]}
    field_map = {
        f["field_id"]: SourceField(
            organization_id=UUID(snapshot["organization_id"]),
            project_id=UUID(snapshot["project_id"]),
            source_id=UUID(snapshot["source_id"]),
            field_id=f["field_id"],
            name=f["name"],
            ordinal=i,
            type=FieldType(f["type"]),
            nullable=f["nullable"],
            schema_revision=snapshot["schema_revision"],
        )
        for i, f in enumerate(snapshot["fields"])
    }
    seen: set[str] = set()
    bbox = snapshot["aoi_bbox"]
    for op in operations:
        if set(op) - {"op_type", "feature_id", "geometry", "properties"}:
            raise PlatformValidationError("unknown offline operation fields")
        ident = op.get("feature_id")
        if not isinstance(ident, str) or ident in seen:
            raise PlatformValidationError("missing or repeated feature identity")
        seen.add(ident)
        props = op.get("properties")
        if not isinstance(props, dict) or set(props) != field_map.keys():
            raise PlatformValidationError("offline properties must match packaged fields")
        try:
            for key, value in props.items():
                canonical = canonical_attribute_value(field_map[key], value)
                if type(value) is not type(canonical) or value != canonical:
                    raise SpatialValidationError("noncanonical attribute")
        except SpatialValidationError as exc:
            raise PlatformValidationError(
                "invalid typed offline field value", code="SCHEMA_MISMATCH"
            ) from exc
        if op.get("op_type") == "update":
            if ident not in feature_ids or op.get("geometry") is not None:
                raise PlatformValidationError(
                    "only attribute updates to included features are permitted",
                    code="OUTSIDE_PACKAGE_SCOPE",
                )
        elif op.get("op_type") == "create":
            geom = op.get("geometry")
            if (
                snapshot["geometry_family"] != "Point"
                or ident in feature_ids
                or not isinstance(geom, dict)
                or geom.get("type") != "Point"
            ):
                raise PlatformValidationError(
                    "only new points are permitted", code="OUTSIDE_PACKAGE_SCOPE"
                )
            coords = geom.get("coordinates")
            if (
                not isinstance(coords, list)
                or len(coords) != 2
                or any(type(c) not in (int, float) or not math.isfinite(c) for c in coords)
                or not bbox["min_x"] <= coords[0] <= bbox["max_x"]
                or not bbox["min_y"] <= coords[1] <= bbox["max_y"]
            ):
                raise PlatformValidationError(
                    "point outside package AOI", code="OUTSIDE_PACKAGE_SCOPE"
                )
        else:
            raise PlatformValidationError(
                "unsupported offline operation", code="OUTSIDE_PACKAGE_SCOPE"
            )
