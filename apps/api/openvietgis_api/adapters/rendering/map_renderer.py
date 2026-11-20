"""R009 Cartography print renderer producing real 150/300 DPI PNG and PDF outputs."""

from __future__ import annotations

import io
import math
from typing import Any

from PIL import Image, ImageDraw

from openvietgis_api.domains.cartography.domain import (
    Orientation,
    PaperSize,
    PrintFormat,
    paper_dimensions_px,
)


def _hex_to_rgba(hex_color: str, alpha: int = 220) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _resolve_feature_color(
    style: dict[str, Any] | None,
    attributes: dict[str, Any],
) -> tuple[str, str]:
    if not style:
        return "#2563eb", "#1e3a8a"
    mode = style.get("mode", "single")
    spec = style.get("style_spec", {})
    if mode == "single":
        return str(spec.get("fill_color", "#2563eb")), str(spec.get("stroke_color", "#1e3a8a"))
    if mode == "categorical":
        field = str(spec.get("field", ""))
        val = attributes.get(field)
        for cat in spec.get("categories", []):
            if str(cat.get("value")) == str(val):
                return str(cat.get("color", "#2563eb")), "#111827"
        return str(spec.get("default_color", "#9ca3af")), "#111827"
    if mode == "range":
        field = str(spec.get("field", ""))
        raw = attributes.get(field)
        try:
            num = float(raw) if raw is not None else None
        except (ValueError, TypeError):
            num = None
        if num is not None:
            for brk in spec.get("breaks", []):
                if float(brk["min"]) <= num <= float(brk["max"]):
                    return str(brk.get("color", "#2563eb")), "#111827"
        return "#9ca3af", "#111827"
    return "#2563eb", "#1e3a8a"


def render_print_map(
    *,
    title: str,
    paper_size: PaperSize,
    orientation: Orientation,
    dpi: int,
    output_format: PrintFormat,
    crs_code: int,
    attribution: str,
    show_north_arrow: bool,
    show_scale_bar: bool,
    show_legend: bool,
    extent: dict[str, float],
    layers_payload: list[dict[str, Any]],
) -> tuple[bytes, int, str]:
    """Render an A4/A3 print-ready PNG or PDF with geometries, legend, scale bar & north arrow."""
    width, height = paper_dimensions_px(paper_size, orientation, dpi)
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    margin = max(40, width // 25)
    header_h = max(60, height // 14)
    footer_h = max(70, height // 12)
    legend_w = (width // 4) if show_legend else 0

    map_x0 = margin
    map_y0 = margin + header_h
    map_x1 = width - margin - legend_w - (margin // 2 if show_legend else 0)
    map_y1 = height - margin - footer_h
    map_w = max(100, map_x1 - map_x0)
    map_h = max(100, map_y1 - map_y0)

    # Outer border & title
    draw.rectangle(
        [margin // 2, margin // 2, width - margin // 2, height - margin // 2],
        outline=(30, 41, 59, 255),
        width=3,
    )
    draw.text((map_x0, margin), title, fill=(15, 23, 42, 255))
    draw.text(
        (map_x0, margin + 24),
        f"CRS: EPSG:{crs_code}  |  Paper: {paper_size.value} {orientation.value}  |  {dpi} DPI",
        fill=(71, 85, 105, 255),
    )

    # Map frame background
    draw.rectangle(
        [map_x0, map_y0, map_x1, map_y1],
        fill=(248, 250, 252, 255),
        outline=(51, 65, 85, 255),
        width=2,
    )

    min_x = float(extent["min_x"])
    min_y = float(extent["min_y"])
    max_x = float(extent["max_x"])
    max_y = float(extent["max_y"])
    span_x = max(1e-6, max_x - min_x)
    span_y = max(1e-6, max_y - min_y)
    # Pad 8% around data
    min_x -= span_x * 0.08
    max_x += span_x * 0.08
    min_y -= span_y * 0.08
    max_y += span_y * 0.08
    span_x = max_x - min_x
    span_y = max_y - min_y

    # Preserve aspect ratio
    scale_px = min(map_w / span_x, map_h / span_y)
    pad_x = (map_w - span_x * scale_px) / 2.0
    pad_y = (map_h - span_y * scale_px) / 2.0

    def to_px(x: float, y: float) -> tuple[float, float]:
        px = map_x0 + pad_x + (x - min_x) * scale_px
        py = map_y1 - pad_y - (y - min_y) * scale_px
        return (px, py)

    # Draw subtle graticule grid
    for i in range(1, 4):
        gx = map_x0 + (map_w * i) / 4
        gy = map_y0 + (map_h * i) / 4
        draw.line([(gx, map_y0), (gx, map_y1)], fill=(226, 232, 240, 255), width=1)
        draw.line([(map_x0, gy), (map_x1, gy)], fill=(226, 232, 240, 255), width=1)

    # Draw layer geometries & labels
    legend_entries: list[tuple[str, str, str]] = []
    for layer in layers_payload:
        style = layer.get("style")
        label_field = style.get("label_field") if style else None
        if style and style.get("legend_items"):
            for li in style["legend_items"]:
                legend_entries.append(
                    (
                        f"{layer['name']}: {li['label']}",
                        str(li.get("fill_color", "#2563eb")),
                        str(li.get("stroke_color", "#1e3a8a")),
                    )
                )
        else:
            legend_entries.append((str(layer["name"]), "#2563eb", "#1e3a8a"))

        for feat in layer.get("features", []):
            geom = feat.get("geometry")
            if not geom:
                continue
            attrs = feat.get("attributes") or {}
            fill_hex, stroke_hex = _resolve_feature_color(style, attrs)
            fill_rgba = _hex_to_rgba(fill_hex, 180)
            stroke_rgba = _hex_to_rgba(stroke_hex, 255)
            gtype = geom.get("type")
            coords = geom.get("coordinates")
            label_anchor: tuple[float, float] | None = None

            if gtype == "Point":
                pt = to_px(float(coords[0]), float(coords[1]))
                r = max(4, width // 240)
                draw.ellipse(
                    [pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r],
                    fill=fill_rgba,
                    outline=stroke_rgba,
                    width=2,
                )
                label_anchor = (pt[0] + r + 4, pt[1] - r)
            elif gtype == "LineString":
                pts = [to_px(float(p[0]), float(p[1])) for p in coords]
                if len(pts) >= 2:
                    draw.line(pts, fill=stroke_rgba, width=max(2, width // 400))
                    label_anchor = pts[len(pts) // 2]
            elif gtype == "Polygon":
                for ring in coords:
                    pts = [to_px(float(p[0]), float(p[1])) for p in ring]
                    if len(pts) >= 3:
                        draw.polygon(pts, fill=fill_rgba, outline=stroke_rgba)
                        if label_anchor is None:
                            cx = sum(p[0] for p in pts) / len(pts)
                            cy = sum(p[1] for p in pts) / len(pts)
                            label_anchor = (cx, cy)

            if label_field and label_anchor and attrs.get(label_field) is not None:
                draw.text(label_anchor, str(attrs[label_field])[:32], fill=(15, 23, 42, 255))

    # North arrow
    if show_north_arrow:
        nx = map_x1 - 36
        ny = map_y0 + 54
        draw.polygon(
            [(nx, ny - 28), (nx - 12, ny + 8), (nx, ny), (nx + 12, ny + 8)], fill=(15, 23, 42, 255)
        )
        draw.text((nx - 4, ny - 44), "N", fill=(15, 23, 42, 255))

    # Compute approximate scale denominator (meters on ground per meter on paper)
    map_width_meters_paper = (map_w / float(dpi)) * 0.0254
    if crs_code in (4326, 4756):
        mid_lat = (min_y + max_y) / 2.0
        ground_width_m = span_x * 111_320.0 * max(0.1, math.cos(math.radians(mid_lat)))
    else:
        ground_width_m = span_x
    scale_denom = max(1, int(round(ground_width_m / max(1e-4, map_width_meters_paper))))

    # Scale bar
    if show_scale_bar:
        bar_px = max(80, map_w // 5)
        bar_ground_m = (bar_px / map_w) * ground_width_m
        label_txt = (
            f"{bar_ground_m / 1000.0:.2f} km" if bar_ground_m >= 1000 else f"{bar_ground_m:.0f} m"
        )
        bx0, by0 = map_x0 + 20, map_y1 - 28
        draw.rectangle(
            [bx0, by0, bx0 + bar_px, by0 + 10], fill=(15, 23, 42, 255), outline=(15, 23, 42, 255)
        )
        draw.rectangle(
            [bx0 + bar_px // 2, by0, bx0 + bar_px, by0 + 10],
            fill=(255, 255, 255, 255),
            outline=(15, 23, 42, 255),
        )
        draw.text((bx0, by0 - 18), f"Scale 1:{scale_denom:,} ({label_txt})", fill=(15, 23, 42, 255))

    # Auto legend panel
    if show_legend:
        lx0 = map_x1 + margin // 2
        ly0 = map_y0
        draw.rectangle(
            [lx0, ly0, width - margin, map_y1],
            fill=(255, 255, 255, 255),
            outline=(148, 163, 184, 255),
            width=2,
        )
        draw.text((lx0 + 12, ly0 + 12), "LEGEND", fill=(15, 23, 42, 255))
        cy = ly0 + 40
        for label, fhex, shex in legend_entries[:20]:
            draw.rectangle(
                [lx0 + 12, cy, lx0 + 30, cy + 16],
                fill=_hex_to_rgba(fhex, 220),
                outline=_hex_to_rgba(shex, 255),
                width=1,
            )
            draw.text((lx0 + 38, cy + 1), label[:26], fill=(30, 41, 59, 255))
            cy += 26

    # Footer attribution & accuracy disclosure
    scale_note = (
        f"Approximate map scale 1:{scale_denom:,} in EPSG:{crs_code} ({dpi} DPI). "
        "Cartographic output only; not a survey-grade cadastral certificate."
    )
    draw.text((map_x0, map_y1 + 14), f"Attribution: {attribution}", fill=(51, 65, 85, 255))
    draw.text((map_x0, map_y1 + 36), scale_note, fill=(100, 116, 139, 255))

    buf = io.BytesIO()
    if output_format == PrintFormat.PNG:
        img.save(buf, format="PNG", dpi=(dpi, dpi))
    else:
        img.save(buf, format="PDF", resolution=float(dpi), title=title, author="OpenVietGIS")
    return buf.getvalue(), scale_denom, scale_note
