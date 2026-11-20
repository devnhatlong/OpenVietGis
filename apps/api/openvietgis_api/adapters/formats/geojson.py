"""RFC 7946 GeoJSON reader and writer."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from openvietgis_api.domains.spatial.domain import (
    AttributeValue,
    FieldType,
    GeometryDimensions,
    GeometryFamily,
    NativeGeometry,
)
from openvietgis_api.domains.transfers.domain import (
    MAX_STRING_LEN,
    MAX_TRANSFER_FEATURES,
    MAX_TRANSFER_FIELDS,
    ExportFieldMapping,
    InspectedField,
    InspectedMember,
    ParsedFeatureRecord,
    ParsedMemberData,
    ValidationFinding,
    sanitize_field_id,
)
from openvietgis_api.domains.transfers.ports import TransferFormatError

_ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_DEC_STR_RE = re.compile(r"^-?\d+\.\d+$")
_FEAT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _check_coords(coords: Any, depth: int) -> tuple[bool, bool]:
    """Return (is_2d_finite_wgs84, has_non_2d)."""
    if depth == 0:
        if not isinstance(coords, list) or len(coords) < 2:
            return False, False
        if len(coords) > 2:
            return False, True
        x, y = coords[0], coords[1]
        if isinstance(x, bool) or isinstance(y, bool):
            return False, False
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False, False
        if not (math.isfinite(x) and math.isfinite(y)):
            return False, False
        if not (-180.0 <= float(x) <= 180.0 and -90.0 <= float(y) <= 90.0):
            return False, False
        return True, False
    if not isinstance(coords, list) or not coords:
        return False, False
    for child in coords:
        ok, non2d = _check_coords(child, depth - 1)
        if not ok:
            return False, non2d
    return True, False


def _to_tuple_coords(coords: Any, depth: int) -> Any:
    if depth == 0:
        return (float(coords[0]), float(coords[1]))
    return tuple(_to_tuple_coords(child, depth - 1) for child in coords)


def _infer_field_type(values: Sequence[Any]) -> tuple[FieldType, bool]:
    nullable = any(v is None for v in values)
    non_null = [v for v in values if v is not None]
    if not non_null:
        return FieldType.TEXT, True
    if all(isinstance(v, bool) for v in non_null):
        return FieldType.BOOLEAN, nullable
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        if all(-2147483648 <= v <= 2147483647 for v in non_null):
            return FieldType.INTEGER, nullable
        return FieldType.DECIMAL, nullable
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return FieldType.DECIMAL, nullable
    if all(isinstance(v, str) for v in non_null):
        if all(_ISO_TS_RE.match(v) for v in non_null):
            return FieldType.TIMESTAMP, nullable
        if all(_DEC_STR_RE.match(v) for v in non_null):
            return FieldType.DECIMAL, nullable
        return FieldType.TEXT, nullable
    return FieldType.TEXT, nullable


def _coerce_value(ftype: FieldType, value: Any) -> AttributeValue:
    if value is None:
        return None
    if ftype == FieldType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError("expected boolean")
        return value
    if ftype == FieldType.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("expected integer")
        return value
    if ftype == FieldType.DECIMAL:
        if isinstance(value, bool):
            raise ValueError("expected decimal")
        if isinstance(value, (int, float)):
            if not math.isfinite(float(value)):
                raise ValueError("non-finite decimal")
            return str(Decimal(str(value)).normalize())
        if isinstance(value, str):
            return str(Decimal(value).normalize())
        raise ValueError("expected decimal")
    if ftype == FieldType.TIMESTAMP:
        if not isinstance(value, str) or not _ISO_TS_RE.match(value):
            raise ValueError("expected ISO-8601 timestamp")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, (dict, list)):
        raise ValueError("nested JSON objects/arrays are not supported attributes")
    text = str(value)
    if len(text) > MAX_STRING_LEN:
        raise ValueError("text exceeds 4096 characters")
    return text


def _load_geojson(data: bytes) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TransferFormatError("INVALID_UTF8", "GeoJSON must be valid UTF-8.") from exc
    try:
        obj = json.loads(
            text,
            parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f"invalid {c}")),
        )
    except ValueError as exc:
        raise TransferFormatError("INVALID_JSON", "Malformed JSON document.") from exc
    if not isinstance(obj, dict) or obj.get("type") != "FeatureCollection":
        raise TransferFormatError(
            "UNSUPPORTED_GEOJSON", "GeoJSON root must be a FeatureCollection."
        )
    if "crs" in obj:
        raise TransferFormatError(
            "LEGACY_GEOJSON_CRS",
            "RFC 7946 forbids legacy 'crs' declarations; supply WGS84 RFC 7946 GeoJSON.",
        )
    features = obj.get("features")
    if not isinstance(features, list):
        raise TransferFormatError("INVALID_GEOJSON", "FeatureCollection 'features' must be a list.")
    if len(features) > MAX_TRANSFER_FEATURES:
        raise TransferFormatError(
            "FEATURE_LIMIT_EXCEEDED",
            f"GeoJSON feature count exceeds limit of {MAX_TRANSFER_FEATURES}.",
        )
    return obj


def inspect_geojson(data: bytes) -> tuple[InspectedMember, ...]:
    parsed = parse_geojson(data)
    has_err = any(f.severity == "error" for f in parsed.findings)
    reason = next((f.message for f in parsed.findings if f.severity == "error"), None)
    return (
        InspectedMember(
            name="features",
            eligible=not has_err,
            reason=reason,
            geometry_family=parsed.geometry_family.value,
            dimensions=parsed.dimensions.value,
            feature_count=len(parsed.features),
            detected_crs=4326,
            detected_encoding="utf-8",
            fields=parsed.fields,
        ),
    )


def parse_geojson(data: bytes) -> ParsedMemberData:
    obj = _load_geojson(data)
    raw_features: list[Any] = obj["features"]
    findings: list[ValidationFinding] = []
    families: set[str] = set()
    prop_names: list[str] = []
    prop_values: dict[str, list[Any]] = {}
    has_non_2d = False

    for idx, feat in enumerate(raw_features):
        if not isinstance(feat, dict) or feat.get("type") != "Feature":
            findings.append(
                ValidationFinding("error", "INVALID_FEATURE", "Invalid GeoJSON Feature.", idx)
            )
            continue
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            findings.append(
                ValidationFinding(
                    "error", "NULL_GEOMETRY", "Feature geometry is null/missing.", idx
                )
            )
            continue
        gtype = geom.get("type")
        if gtype not in ("Point", "LineString", "Polygon"):
            findings.append(
                ValidationFinding(
                    "error",
                    "UNSUPPORTED_GEOMETRY",
                    f"Geometry type '{gtype}' is outside supported 2D single-part profile.",
                    idx,
                )
            )
            continue
        families.add(gtype)
        depth = {"Point": 0, "LineString": 1, "Polygon": 2}[gtype]
        ok, non2d = _check_coords(geom.get("coordinates"), depth)
        if non2d:
            has_non_2d = True
            findings.append(
                ValidationFinding(
                    "error", "UNSUPPORTED_DIMENSIONS", "Only 2D XY coordinates are supported.", idx
                )
            )
        elif not ok:
            findings.append(
                ValidationFinding(
                    "error",
                    "INVALID_GEOMETRY",
                    "Geometry has non-finite or out-of-range WGS84 coordinates.",
                    idx,
                )
            )
        props = feat.get("properties")
        if props is not None and not isinstance(props, dict):
            findings.append(
                ValidationFinding(
                    "error", "INVALID_PROPERTIES", "Properties must be an object.", idx
                )
            )
            continue
        if isinstance(props, dict):
            for k, v in props.items():
                if k not in prop_values:
                    prop_names.append(k)
                    prop_values[k] = []
                prop_values[k].append(v)

    if len(prop_names) > MAX_TRANSFER_FIELDS:
        findings.append(
            ValidationFinding(
                "error", "TOO_MANY_FIELDS", f"Field count exceeds limit of {MAX_TRANSFER_FIELDS}."
            )
        )
    if len(families) > 1:
        findings.append(
            ValidationFinding(
                "error", "MIXED_GEOMETRY_FAMILY", "Mixed geometry families are not supported."
            )
        )

    used_ids: set[str] = set()
    fields: list[InspectedField] = []
    for ordinal, raw_name in enumerate(prop_names[:MAX_TRANSFER_FIELDS]):
        vals = [
            (f.get("properties") or {}).get(raw_name)
            for f in raw_features
            if isinstance(f, dict) and isinstance(f.get("properties") or {}, dict)
        ]
        ftype, nullable = _infer_field_type(vals)
        fid = sanitize_field_id(raw_name, used_ids, ordinal)
        fields.append(
            InspectedField(
                field_id=fid,
                name=raw_name[:120] or fid,
                type=ftype,
                nullable=nullable,
                ordinal=ordinal,
                source_name=raw_name,
            )
        )

    family = (
        GeometryFamily(next(iter(families)))
        if len(families) == 1
        else (GeometryFamily.MIXED if len(families) > 1 else GeometryFamily.POINT)
    )
    dims = GeometryDimensions.XYZ if has_non_2d else GeometryDimensions.XY
    records: list[ParsedFeatureRecord] = []
    seen_fids: set[str] = set()
    xs: list[float] = []
    ys: list[float] = []

    if not any(f.severity == "error" for f in findings):
        depth = {
            GeometryFamily.POINT: 0,
            GeometryFamily.LINE_STRING: 1,
            GeometryFamily.POLYGON: 2,
        }[family]
        for idx, feat in enumerate(raw_features):
            raw_id = feat.get("id")
            if isinstance(raw_id, (str, int)) and _FEAT_ID_RE.match(str(raw_id)):
                fid_str = str(raw_id)
            else:
                fid_str = f"feat-{idx + 1:06d}"
            if fid_str in seen_fids:
                fid_str = f"feat-{idx + 1:06d}"
            seen_fids.add(fid_str)
            props = feat.get("properties") or {}
            attrs: dict[str, AttributeValue] = {}
            for fld in fields:
                try:
                    attrs[fld.field_id] = _coerce_value(fld.type, props.get(fld.source_name))
                except ValueError as exc:
                    findings.append(
                        ValidationFinding(
                            "error", "INVALID_ATTRIBUTE_VALUE", str(exc), idx, fld.source_name
                        )
                    )
            coords = _to_tuple_coords(feat["geometry"]["coordinates"], depth)
            geom = NativeGeometry(family.value, coords, 4326)
            records.append(ParsedFeatureRecord(fid_str, attrs, geom))
            _collect_xy(coords, xs, ys)

    extent = (
        {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys), "crs_code": 4326}
        if xs and ys
        else None
    )
    return ParsedMemberData(
        member_name="features",
        geometry_family=family,
        dimensions=dims,
        detected_crs=4326,
        detected_encoding="utf-8",
        requires_encoding_resolution=False,
        fields=tuple(fields),
        features=tuple(records),
        findings=tuple(findings),
        extent=extent,
    )


def _collect_xy(coords: Any, xs: list[float], ys: list[float]) -> None:
    if isinstance(coords, tuple) and coords:
        if isinstance(coords[0], (int, float)):
            xs.append(float(coords[0]))
            ys.append(float(coords[1]))
        else:
            for child in coords:
                _collect_xy(child, xs, ys)


def _to_list_coords(coords: Any) -> Any:
    if isinstance(coords, tuple):
        return [_to_list_coords(c) for c in coords]
    return coords


def write_geojson(
    *,
    field_mappings: Sequence[ExportFieldMapping],
    features: Sequence[tuple[str, dict[str, Any], NativeGeometry]],
) -> tuple[bytes, str, str]:
    out_features = []
    for fid, attrs, geom in features:
        props = {m.output_name: attrs.get(m.field_id) for m in field_mappings}
        out_features.append(
            {
                "type": "Feature",
                "id": fid,
                "geometry": {
                    "type": geom.type,
                    "coordinates": _to_list_coords(geom.coordinates),
                },
                "properties": props,
            }
        )
    doc = {"type": "FeatureCollection", "features": out_features}
    payload = (json.dumps(doc, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    return payload, "geojson", "application/geo+json"
