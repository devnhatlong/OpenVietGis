"""R012 CAD Interoperability (2D DXF) & Precision COGO math domain."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import PlatformValidationError


class CadUnit(StrEnum):
    METER = "meter"
    CENTIMETER = "centimeter"
    MILLIMETER = "millimeter"


UNIT_TO_METERS: dict[CadUnit, float] = {
    CadUnit.METER: 1.0,
    CadUnit.CENTIMETER: 0.01,
    CadUnit.MILLIMETER: 0.001,
}


@dataclass(frozen=True, slots=True)
class CadConversionRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    direction: str
    cad_format: str
    filename: str
    units: CadUnit
    crs_code: int
    status: str
    entity_summary: dict[str, Any]
    loss_report: dict[str, Any]
    storage_key: str
    sha256: str
    byte_size: int
    source_id: UUID | None
    layer_id: UUID | None
    content_revision: str | None
    actor_id: UUID
    created_at: datetime


def compute_traverse_point(
    *,
    origin: tuple[float, float],
    distance: float,
    azimuth_degrees: float,
) -> dict[str, Any]:
    """COGO traverse: azimuth 0=North (+Y), 90=East (+X), clockwise in planar CRS."""
    if distance <= 0.0 or not math.isfinite(distance):
        raise PlatformValidationError("distance must be > 0", code="INVALID_COGO")
    if not math.isfinite(azimuth_degrees):
        raise PlatformValidationError("azimuth_degrees must be finite", code="INVALID_COGO")
    rad = math.radians(azimuth_degrees % 360.0)
    dx = distance * math.sin(rad)
    dy = distance * math.cos(rad)
    end = (origin[0] + dx, origin[1] + dy)
    return {
        "operation": "traverse",
        "origin": [origin[0], origin[1]],
        "endpoint": [end[0], end[1]],
        "delta": [dx, dy],
        "distance": distance,
        "azimuth_degrees": azimuth_degrees % 360.0,
    }


def compute_line_intersection(
    *,
    seg_a: tuple[tuple[float, float], tuple[float, float]],
    seg_b: tuple[tuple[float, float], tuple[float, float]],
) -> dict[str, Any]:
    """Exact 2D line-line intersection (and whether intersection lies on both segments)."""
    (x1, y1), (x2, y2) = seg_a
    (x3, y3), (x4, y4) = seg_b
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return {"intersects": False, "parallel": True, "point": None, "within_segments": False}
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    px = x1 + t * (x2 - x1)
    py = y1 + t * (y2 - y1)
    within = (0.0 <= t <= 1.0) and (0.0 <= u <= 1.0)
    return {
        "intersects": True,
        "parallel": False,
        "point": [px, py],
        "within_segments": within,
        "t": t,
        "u": u,
    }


def compute_parallel_offset(
    *,
    segment: tuple[tuple[float, float], tuple[float, float]],
    offset_distance: float,
) -> dict[str, Any]:
    """Offset a 2D segment perpendicularly (positive = right of direction A->B, negative = left)."""
    (x1, y1), (x2, y2) = segment
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-12:
        raise PlatformValidationError("degenerate zero-length segment", code="INVALID_COGO")
    # Right-hand unit normal: (dy/L, -dx/L)
    nx, ny = dy / length, -dx / length
    ox, oy = nx * offset_distance, ny * offset_distance
    return {
        "operation": "parallel_offset",
        "offset_distance": offset_distance,
        "segment": [[x1 + ox, y1 + oy], [x2 + ox, y2 + oy]],
    }


def compute_precision_snap(
    *,
    target: tuple[float, float],
    segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
    tolerance: float,
) -> dict[str, Any]:
    """Deterministic CAD snap checking vertices, exact midpoints, then perpendicular foot."""
    tx, ty = target
    best_dist = tolerance
    best_pt: tuple[float, float] = (tx, ty)
    kind = "none"

    for a, b in segments:
        for vx, vy in (a, b):
            d = math.hypot(tx - vx, ty - vy)
            if d <= best_dist:
                best_dist, best_pt, kind = d, (vx, vy), "vertex"
    if kind == "none":
        for (ax, ay), (bx, by) in segments:
            mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
            d = math.hypot(tx - mx, ty - my)
            if d <= best_dist:
                best_dist, best_pt, kind = d, (mx, my), "midpoint"
    if kind == "none":
        for (ax, ay), (bx, by) in segments:
            dx, dy = bx - ax, by - ay
            lsq = dx * dx + dy * dy
            if lsq <= 1e-18:
                continue
            t = max(0.0, min(1.0, ((tx - ax) * dx + (ty - ay) * dy) / lsq))
            px, py = ax + t * dx, ay + t * dy
            d = math.hypot(tx - px, ty - py)
            if d <= best_dist:
                best_dist, best_pt, kind = d, (px, py), "perpendicular"
    return {
        "snapped": kind != "none",
        "kind": kind,
        "point": [best_pt[0], best_pt[1]],
        "distance": best_dist if kind != "none" else None,
    }
