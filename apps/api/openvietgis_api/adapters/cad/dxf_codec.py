"""R012 bounded 2D DXF codec: exact straight mappings and opt-in circular curves."""

from __future__ import annotations

import io
import math
from collections import Counter
from typing import Any

from ezdxf.filemanagement import new, read

from openvietgis_api.domains.cad.domain import UNIT_TO_METERS, CadUnit
from openvietgis_api.domains.editing.domain import validate_geometry_payload
from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.spatial.domain import MAX_POSITIONS, GeometryFamily

MAX_DRAWING_POSITIONS = 200_000
MAX_ENTITIES = 10_000
MAX_COORDINATE_M = 1e9


def _coordinate(x: float, y: float) -> list[float]:
    if not all(math.isfinite(v) and abs(v) <= MAX_COORDINATE_M for v in (x, y)):
        raise PlatformValidationError(
            "invalid or unbounded CAD coordinate", code="CAD_COORDINATE_LIMIT"
        )
    return [x, y]


def _flat(ent: Any, *, elevation: float = 0.0) -> None:
    if elevation != 0 or float(ent.dxf.get("thickness", 0)) != 0:
        raise PlatformValidationError(
            "nonzero CAD elevation/thickness requires a 3D profile", code="CAD_3D_UNSUPPORTED"
        )
    if tuple(ent.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1):
        raise PlatformValidationError(
            "nonstandard object-coordinate extrusion cannot be imported safely",
            code="CAD_OCS_UNSUPPORTED",
        )


def _segments(
    radius: float, angle: float, tolerance: float, numerical_margin: float
) -> tuple[int, float]:
    # In grid metres: circular-arc to chord max distance r * (1-cos(step/2)).
    # Stable half-angle form avoids cancellation for finely sampled arcs.
    if not math.isfinite(radius) or radius <= 0 or numerical_margin >= tolerance:
        raise PlatformValidationError(
            "curve cannot meet the selected tolerance at numeric precision", code="CAD_CURVE_LIMIT"
        )
    budget = tolerance - numerical_margin
    ratio = min(1.0, budget / (2 * radius))
    step = min(math.pi / 2, 4 * math.asin(math.sqrt(ratio)))
    if step <= 0 or angle / step > MAX_POSITIONS - 1:
        raise PlatformValidationError(
            "curve exceeds tessellation position limit", code="CAD_CURVE_LIMIT"
        )
    count = max(1, math.ceil(angle / step))
    bound = 2 * radius * math.sin(angle / count / 4) ** 2 + numerical_margin
    return count, bound


def _curve_points(
    center: list[float],
    radius: float,
    start: float,
    sweep: float,
    tolerance: float,
    *,
    max_positions: int = MAX_POSITIONS,
) -> tuple[list[list[float]], float]:
    # Reserve a conservative floating-point margin: error from trigonometric
    # evaluation and world-coordinate translation, in the same planar units.
    magnitude = max(abs(center[0]), abs(center[1]), radius, 1.0)
    count, bound = _segments(radius, abs(sweep), tolerance, 64 * math.ulp(magnitude))
    if count + 1 > max_positions:
        raise PlatformValidationError(
            "curve exceeds remaining position budget", code="CAD_CURVE_LIMIT"
        )
    pts = [
        _coordinate(
            center[0] + radius * math.cos(start + sweep * k / count),
            center[1] + radius * math.sin(start + sweep * k / count),
        )
        for k in range(count + 1)
    ]
    if any(a == b for a, b in zip(pts[:-1], pts[1:], strict=True)):
        raise PlatformValidationError(
            "curve collapses at numeric precision", code="CAD_CURVE_LIMIT"
        )
    return pts, bound


def _bulge_points(
    a: list[float],
    b: list[float],
    bulge: float,
    tolerance: float,
    *,
    max_positions: int,
) -> tuple[list[list[float]], float]:
    if not math.isfinite(bulge):
        raise PlatformValidationError("nonfinite polyline bulge", code="INVALID_DXF")
    dx, dy = b[0] - a[0], b[1] - a[1]
    chord = math.hypot(dx, dy)
    if not chord:
        raise PlatformValidationError("bulged segment has coincident endpoints", code="INVALID_DXF")
    sweep = 4 * math.atan(bulge)
    # A nearly straight arc can use its original endpoints without computing
    # an enormous remote center. Sagitta = chord * abs(bulge)/2.
    sagitta = chord * abs(bulge) / 2
    if abs(bulge) <= 1 and sagitta <= tolerance:
        return [a, b], sagitta
    radius = chord * (abs(bulge) + 1 / abs(bulge)) / 4
    offset = (1 / bulge - bulge) / 4
    center = [(a[0] + b[0]) / 2 - dy * offset, (a[1] + b[1]) / 2 + dx * offset]
    if not all(math.isfinite(x) for x in center):
        raise PlatformValidationError("invalid polyline curve center", code="CAD_CURVE_LIMIT")
    start = math.atan2(a[1] - center[1], a[0] - center[0])
    pts, bound = _curve_points(center, radius, start, sweep, tolerance, max_positions=max_positions)
    # Preserve the source endpoints exactly. Guard against ill-conditioned
    # reconstruction from near-collinear chords before making that replacement.
    error = max(math.dist(pts[0], a), math.dist(pts[-1], b))
    if error > 64 * math.ulp(max(abs(center[0]), abs(center[1]), radius, 1.0)):
        raise PlatformValidationError(
            "polyline curve reconstruction is numerically unstable", code="CAD_CURVE_LIMIT"
        )
    pts[0], pts[-1] = a, b
    return pts, bound


def parse_dxf_2d(
    payload: bytes,
    *,
    units: CadUnit,
    curve_tolerance_m: float | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Parse bounded 2D model-space entities; tolerances are projected grid metres."""
    scale = UNIT_TO_METERS[units]
    if curve_tolerance_m is not None and (
        not math.isfinite(curve_tolerance_m) or not 1e-6 <= curve_tolerance_m <= 1000
    ):
        raise PlatformValidationError(
            "curve tolerance must be within [0.000001, 1000] grid metres",
            code="INVALID_CAD_TOLERANCE",
        )
    try:
        doc = read(io.StringIO(payload.decode("utf-8", errors="strict")))
    except Exception as exc:
        raise PlatformValidationError(f"invalid DXF document: {exc}", code="INVALID_DXF") from exc

    if doc.dxfversion not in {"AC1024", "AC1027", "AC1032"}:
        raise PlatformValidationError(
            "supported DXF versions are R2010, R2013 and R2018", code="CAD_VERSION_UNSUPPORTED"
        )
    declared_units = int(doc.header.get("$INSUNITS", 0))
    expected_units = {CadUnit.METER: 6, CadUnit.CENTIMETER: 5, CadUnit.MILLIMETER: 4}[units]
    if declared_units not in (0, expected_units):
        raise PlatformValidationError(
            "DXF declared units do not match the selected supported units", code="CAD_UNIT_MISMATCH"
        )

    buckets: dict[str, list[dict[str, Any]]] = {"Polygon": [], "LineString": [], "Point": []}
    entity_counts: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()
    unsupported_counts: Counter[str] = Counter()
    approximations: set[str] = set()
    curve_details: list[dict[str, Any]] = []
    entity_mapping: list[dict[str, Any]] = []
    total_positions = 0

    for idx, ent in enumerate(doc.modelspace(), start=1):
        if idx > MAX_ENTITIES:
            raise PlatformValidationError("DXF entity limit exceeded", code="CAD_ENTITY_LIMIT")
        etype = ent.dxftype()
        layer = str(ent.dxf.get("layer", "0"))
        handle = str(ent.dxf.handle)
        feature_id = f"dxf_{idx}"
        entity_counts[etype] += 1
        layer_counts[layer] += 1
        row: dict[str, Any] = {
            "handle": handle,
            "entity": etype,
            "layer": layer,
            "feature_id": feature_id,
        }
        entity_mapping.append(row)
        family: str
        mapped_type = etype
        pts: list[list[float]]
        bound = 0.0
        is_curve = False
        if etype == "POINT":
            loc = ent.dxf.location
            _flat(ent, elevation=loc.z)
            pts = [_coordinate(loc.x * scale, loc.y * scale)]
            family = "Point"
        elif etype == "LINE":
            a, b = ent.dxf.start, ent.dxf.end
            _flat(ent, elevation=a.z)
            _flat(ent, elevation=b.z)
            if a == b:
                raise PlatformValidationError("zero-length LINE", code="INVALID_DXF")
            pts = [_coordinate(v.x * scale, v.y * scale) for v in (a, b)]
            family = "LineString"
        elif etype == "LWPOLYLINE":
            lw: Any = ent
            _flat(ent, elevation=float(lw.dxf.elevation))
            raw = lw.get_points("xyseb")
            if len(raw) > MAX_POSITIONS:
                raise PlatformValidationError(
                    "polyline position limit exceeded", code="CAD_CURVE_LIMIT"
                )
            if float(lw.dxf.const_width) != 0 or any(
                float(p[2]) != 0 or float(p[3]) != 0 for p in raw
            ):
                raise PlatformValidationError(
                    "wide polyline cannot be represented as a simple centerline or polygon",
                    code="CAD_WIDTH_UNSUPPORTED",
                )
            vertices = [_coordinate(float(p[0]) * scale, float(p[1]) * scale) for p in raw]
            if len(vertices) < 2:
                raise PlatformValidationError("degenerate LWPOLYLINE", code="INVALID_DXF")
            explicit_closed = bool(lw.closed)
            if not explicit_closed and float(raw[-1][4]) != 0:
                raise PlatformValidationError(
                    "open polyline has dangling final bulge", code="INVALID_DXF"
                )
            closed = explicit_closed or (len(vertices) >= 4 and vertices[0] == vertices[-1])
            pts = [vertices[0]]
            edges = (
                len(vertices)
                if explicit_closed and vertices[-1] != vertices[0]
                else len(vertices) - 1
            )
            for i in range(edges):
                a, b = vertices[i], vertices[(i + 1) % len(vertices)]
                bulge = float(raw[i][4])
                if bulge != 0:
                    if curve_tolerance_m is None:
                        raise PlatformValidationError(
                            "curved LWPOLYLINE bulges require explicit curve_tolerance_m",
                            code="CAD_BULGE_UNSUPPORTED",
                        )
                    edge, error = _bulge_points(
                        a, b, bulge, curve_tolerance_m, max_positions=MAX_POSITIONS - len(pts) + 1
                    )
                    bound = max(bound, error)
                    pts.extend(edge[1:])
                    is_curve = True
                elif a != b:
                    pts.append(b)
                else:
                    raise PlatformValidationError(
                        "polyline has coincident consecutive vertices", code="INVALID_DXF"
                    )
                if len(pts) > MAX_POSITIONS:
                    raise PlatformValidationError(
                        "polyline tessellation position limit exceeded", code="CAD_CURVE_LIMIT"
                    )
            if explicit_closed and vertices[-1] == vertices[0] and float(raw[-1][4]) != 0:
                raise PlatformValidationError(
                    "closed polyline has a bulge on a zero-length closing segment",
                    code="INVALID_DXF",
                )
            if closed and (len(pts) < 4 or pts[0] != pts[-1]):
                raise PlatformValidationError(
                    "closed polyline cannot form valid polygon ring", code="INVALID_DXF"
                )
            family = "Polygon" if closed else "LineString"
            if closed:
                mapped_type = "LWPOLYLINE_CLOSED"
        elif etype in ("ARC", "CIRCLE"):
            c = ent.dxf.center
            _flat(ent, elevation=c.z)
            if curve_tolerance_m is None:
                raise PlatformValidationError(
                    f"{etype} requires explicit curve_tolerance_m",
                    code="CAD_CURVE_TOLERANCE_REQUIRED",
                )
            center = _coordinate(c.x * scale, c.y * scale)
            radius = float(ent.dxf.radius) * scale
            start, sweep = 0.0, math.tau
            if etype == "ARC":
                start_deg, end_deg = float(ent.dxf.start_angle), float(ent.dxf.end_angle)
                if not all(math.isfinite(v) for v in (start_deg, end_deg)):
                    raise PlatformValidationError("nonfinite arc angle", code="INVALID_DXF")
                start, sweep = (
                    math.radians(start_deg % 360),
                    math.radians((end_deg % 360 - start_deg % 360) % 360),
                )
                if sweep == 0:
                    raise PlatformValidationError(
                        "ARC with zero or full sweep is ambiguous; use CIRCLE for full circle",
                        code="INVALID_DXF",
                    )
            pts, bound = _curve_points(center, radius, start, sweep, curve_tolerance_m)
            if etype == "CIRCLE":
                pts[-1] = pts[0]
                family = "Polygon"
            else:
                family = "LineString"
            is_curve = True
        else:
            unsupported_counts[etype] += 1
            row["disposition"] = "unsupported"
            row["feature_id"] = None
            continue

        total_positions += len(pts)
        if total_positions > MAX_DRAWING_POSITIONS:
            raise PlatformValidationError(
                "DXF total position limit exceeded", code="CAD_CURVE_LIMIT"
            )
        if is_curve:
            approximations.add(f"{etype}_TESSELLATED_BOUNDED")
            curve_details.append(
                {
                    "handle": handle,
                    "feature_id": feature_id,
                    "entity": etype,
                    "position_count": len(pts),
                    "max_chord_deviation_grid_m": bound,
                }
            )
        row["family"] = family
        row["disposition"] = "approximated" if is_curve else "mapped"
        coords = pts[0] if family == "Point" else ([pts] if family == "Polygon" else pts)
        buckets[family].append(
            {
                "feature_id": feature_id,
                "attributes": {"cad_layer": layer, "cad_entity": mapped_type},
                "geometry": {"type": family, "coordinates": coords},
            }
        )

    # Preserve the existing one-homogeneous-layer contract; excluded entities
    # remain visible in the inspection and conversion report, never hidden.
    ranked = sorted(buckets.items(), key=lambda item: len(item[1]), reverse=True)
    dominant_family, features = ranked[0]
    dropped_families = {fam: len(items) for fam, items in ranked[1:] if items}
    if not features:
        raise PlatformValidationError(
            "DXF contains no supported 2D vector entities", code="EMPTY_CAD_IMPORT"
        )
    excluded_handles = set()
    for row in entity_mapping:
        if row.get("family") is not None and row["family"] != dominant_family:
            row["disposition"] = "excluded_secondary_family"
            row["feature_id"] = None
            excluded_handles.add(row["handle"])
    for curve in curve_details:
        curve["disposition"] = (
            "excluded_secondary_family" if curve["handle"] in excluded_handles else "approximated"
        )
        if curve["handle"] in excluded_handles:
            curve["feature_id"] = None

    entity_summary = {
        "dxf_version": doc.dxfversion,
        "profile": "dxf-2d-bounded-v1",
        "scope": "modelspace_only",
        "units": units.value,
        "declared_insunits": declared_units,
        "scale_to_meters": scale,
        "entity_counts": dict(entity_counts),
        "layer_counts": dict(layer_counts),
        "published_family": dominant_family,
        "published_feature_count": len(features),
        "entity_mapping": entity_mapping,
    }
    loss_report = {
        "unsupported_entities": dict(unsupported_counts),
        "dropped_secondary_families": dropped_families,
        "curve_approximations": sorted(approximations),
        "curve_tolerance_grid_m": curve_tolerance_m,
        "curve_details": curve_details,
        "elevation_z_dropped": False,
        "requires_acknowledgement": bool(unsupported_counts or dropped_families or approximations),
        "silent_loss": False,
        "survey_grade": False,
    }
    return dominant_family, features, entity_summary, loss_report


def write_dxf_2d(
    features: list[dict[str, Any]],
    *,
    layer_name: str,
    units: CadUnit,
) -> bytes:
    """Export 2D vector features into a clean R2010 DXF document."""
    inv_scale = 1.0 / UNIT_TO_METERS[units]
    doc = new("R2010")
    doc.header["$INSUNITS"] = {CadUnit.METER: 6, CadUnit.CENTIMETER: 5, CadUnit.MILLIMETER: 4}[
        units
    ]
    msp = doc.modelspace()
    safe_layer = "".join(c if c.isalnum() or c in "_-" else "_" for c in layer_name)[:48] or "GIS"
    if safe_layer not in doc.layers:
        doc.layers.add(safe_layer)

    if not features or len(features) > MAX_ENTITIES:
        raise PlatformValidationError(
            "DXF export requires 1–10000 features", code="CAD_FEATURE_LIMIT"
        )
    total_positions = 0
    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            raise PlatformValidationError(
                "DXF cannot preserve missing geometry", code="CAD_GEOMETRY_UNSUPPORTED"
            )
        gtype = geom.get("type")
        if gtype not in {"Point", "LineString", "Polygon"}:
            raise PlatformValidationError(
                f"unsupported DXF geometry: {gtype}", code="CAD_GEOMETRY_UNSUPPORTED"
            )
        _, coords = validate_geometry_payload(geom, GeometryFamily(gtype))
        positions = (
            [coords]
            if gtype == "Point"
            else (coords if gtype == "LineString" else [p for ring in coords for p in ring])
        )
        total_positions += len(positions)
        if len(positions) > MAX_POSITIONS or total_positions > MAX_DRAWING_POSITIONS:
            raise PlatformValidationError(
                "DXF export position limit exceeded", code="CAD_CURVE_LIMIT"
            )
        for point in positions:
            _coordinate(float(point[0]), float(point[1]))
        if gtype == "Point":
            msp.add_point(
                (float(coords[0]) * inv_scale, float(coords[1]) * inv_scale),
                dxfattribs={"layer": safe_layer},
            )
        elif gtype == "LineString":
            pts = [(float(p[0]) * inv_scale, float(p[1]) * inv_scale) for p in coords]
            msp.add_lwpolyline(pts, dxfattribs={"layer": safe_layer})
        elif gtype == "Polygon":
            if len(coords) != 1:
                raise PlatformValidationError(
                    "DXF simple polylines cannot preserve polygon holes",
                    code="CAD_GEOMETRY_UNSUPPORTED",
                )
            for ring in coords:
                pts = [(float(p[0]) * inv_scale, float(p[1]) * inv_scale) for p in ring]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": safe_layer})
        else:
            raise PlatformValidationError(
                f"unsupported DXF geometry: {gtype}", code="CAD_GEOMETRY_UNSUPPORTED"
            )

    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode("utf-8")
