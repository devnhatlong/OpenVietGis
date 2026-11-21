"""R012 Real 2D DXF codec using ezdxf with explicit entity mapping & loss disclosure."""

from __future__ import annotations

import io
import math
from typing import Any

import ezdxf

from openvietgis_api.domains.cad.domain import UNIT_TO_METERS, CadUnit
from openvietgis_api.domains.platform_errors import PlatformValidationError


def parse_dxf_2d(
    payload: bytes,
    *,
    units: CadUnit,
) -> tuple[str, list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Parse 2D DXF entities into GeoJSON-like features + explicit entity/loss report."""
    scale = UNIT_TO_METERS[units]
    try:
        text_stream = io.StringIO(payload.decode("utf-8", errors="strict"))
        doc = ezdxf.read(text_stream)
    except Exception as exc:
        raise PlatformValidationError(f"invalid DXF document: {exc}", code="INVALID_DXF") from exc

    declared_units = int(doc.header.get("$INSUNITS", 0))
    expected_units = {CadUnit.METER: 6, CadUnit.CENTIMETER: 5, CadUnit.MILLIMETER: 4}[units]
    if declared_units not in (0, expected_units):
        raise PlatformValidationError(
            "DXF declared units do not match the selected supported units",
            code="CAD_UNIT_MISMATCH",
        )
    msp = doc.modelspace()
    points: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    polygons: list[dict[str, Any]] = []
    entity_counts: dict[str, int] = {}
    unsupported_counts: dict[str, int] = {}
    approximations: list[str] = []

    idx = 0
    for ent in msp:
        etype = ent.dxftype()
        entity_counts[etype] = entity_counts.get(etype, 0) + 1
        layer_name = str(ent.dxf.get("layer", "0"))
        idx += 1
        if idx > 10000:
            raise PlatformValidationError("DXF entity limit exceeded", code="CAD_ENTITY_LIMIT")
        if etype in ("LWPOLYLINE", "CIRCLE") and tuple(ent.dxf.get("extrusion", (0, 0, 1))) != (
            0,
            0,
            1,
        ):
            raise PlatformValidationError(
                "nonstandard object-coordinate extrusion cannot be imported safely",
                code="CAD_OCS_UNSUPPORTED",
            )

        if etype == "POINT":
            loc = ent.dxf.location
            points.append(
                {
                    "feature_id": f"dxf_{idx}",
                    "attributes": {"cad_layer": layer_name, "cad_entity": "POINT"},
                    "geometry": {"type": "Point", "coordinates": [loc.x * scale, loc.y * scale]},
                }
            )
        elif etype == "LINE":
            s, e = ent.dxf.start, ent.dxf.end
            lines.append(
                {
                    "feature_id": f"dxf_{idx}",
                    "attributes": {"cad_layer": layer_name, "cad_entity": "LINE"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[s.x * scale, s.y * scale], [e.x * scale, e.y * scale]],
                    },
                }
            )
        elif etype == "LWPOLYLINE":
            lw: Any = ent
            points_with_bulges = lw.get_points("xyb")
            if any(float(p[2]) != 0 for p in points_with_bulges):
                raise PlatformValidationError(
                    "curved LWPOLYLINE bulges require a verified tessellation profile",
                    code="CAD_BULGE_UNSUPPORTED",
                )
            pts = [[float(p[0]) * scale, float(p[1]) * scale] for p in points_with_bulges]
            if len(pts) < 2:
                unsupported_counts["DEGENERATE_LWPOLYLINE"] = (
                    unsupported_counts.get("DEGENERATE_LWPOLYLINE", 0) + 1
                )
                continue
            is_closed = bool(lw.closed) or (len(pts) >= 4 and pts[0] == pts[-1])
            if is_closed and len(pts) >= 3:
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                polygons.append(
                    {
                        "feature_id": f"dxf_{idx}",
                        "attributes": {"cad_layer": layer_name, "cad_entity": "LWPOLYLINE_CLOSED"},
                        "geometry": {"type": "Polygon", "coordinates": [pts]},
                    }
                )
            else:
                lines.append(
                    {
                        "feature_id": f"dxf_{idx}",
                        "attributes": {"cad_layer": layer_name, "cad_entity": "LWPOLYLINE"},
                        "geometry": {"type": "LineString", "coordinates": pts},
                    }
                )
        elif etype == "CIRCLE":
            c = ent.dxf.center
            r = float(ent.dxf.radius) * scale
            segs = 32
            ring = [
                [
                    c.x * scale + r * math.cos(2 * math.pi * k / segs),
                    c.y * scale + r * math.sin(2 * math.pi * k / segs),
                ]
                for k in range(segs)
            ]
            ring.append(ring[0])
            polygons.append(
                {
                    "feature_id": f"dxf_{idx}",
                    "attributes": {"cad_layer": layer_name, "cad_entity": "CIRCLE"},
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            )
            if "CIRCLE_TESSELLATED_32_SEGMENTS" not in approximations:
                approximations.append("CIRCLE_TESSELLATED_32_SEGMENTS")
        else:
            unsupported_counts[etype] = unsupported_counts.get(etype, 0) + 1

    # Choose dominant homogeneous geometry family cleanly (explicit disclosure if mixed)
    buckets = [("Polygon", polygons), ("LineString", lines), ("Point", points)]
    buckets.sort(key=lambda b: len(b[1]), reverse=True)
    dominant_family, features = buckets[0]
    dropped_families = {fam: len(items) for fam, items in buckets[1:] if len(items) > 0}
    if not features:
        raise PlatformValidationError(
            "DXF contains no supported 2D vector entities (POINT, LINE, LWPOLYLINE, CIRCLE)",
            code="EMPTY_CAD_IMPORT",
        )

    entity_summary = {
        "dxf_version": doc.dxfversion,
        "units": units.value,
        "declared_insunits": declared_units,
        "scale_to_meters": scale,
        "entity_counts": entity_counts,
        "published_family": dominant_family,
        "published_feature_count": len(features),
    }
    loss_report = {
        "unsupported_entities": unsupported_counts,
        "dropped_secondary_families": dropped_families,
        "curve_approximations": approximations,
        "elevation_z_dropped": True,
        "silent_loss": False,
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
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = {CadUnit.METER: 6, CadUnit.CENTIMETER: 5, CadUnit.MILLIMETER: 4}[
        units
    ]
    msp = doc.modelspace()
    safe_layer = "".join(c if c.isalnum() or c in "_-" else "_" for c in layer_name)[:48] or "GIS"
    if safe_layer not in doc.layers:
        doc.layers.add(safe_layer)

    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            raise PlatformValidationError(
                "DXF cannot preserve missing geometry", code="CAD_GEOMETRY_UNSUPPORTED"
            )
        gtype = geom.get("type")
        coords = geom.get("coordinates")
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
