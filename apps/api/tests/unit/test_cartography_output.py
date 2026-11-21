"""Independent pixel and map-scale controls for cartographic rendering."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from openvietgis_api.adapters.rendering.map_renderer import render_print_map
from openvietgis_api.domains.cartography.domain import Orientation, PaperSize, PrintFormat
from openvietgis_api.domains.platform_errors import PlatformValidationError


def _render(features, extent=None, *, legend=False, layers=None):
    return render_print_map(
        title="Synthetic map",
        paper_size=PaperSize.A4,
        orientation=Orientation.LANDSCAPE,
        dpi=150,
        output_format=PrintFormat.PNG,
        crs_code=5899,
        attribution="Synthetic",
        show_north_arrow=False,
        show_scale_bar=False,
        show_legend=legend,
        extent=extent or {"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 100},
        layers_payload=layers or [{"name": "control", "features": features}],
    )


def test_scale_uses_actual_aspect_preserving_transform():
    _, narrow_scale, note = _render([], {"min_x": 0, "min_y": 0, "max_x": 10, "max_y": 100})
    _, wide_scale, _ = _render([], {"min_x": 0, "min_y": 0, "max_x": 30, "max_y": 100})
    # Both tall extents are constrained by the same vertical span. Thus their
    # exact grid scale must agree despite very different horizontal data spans.
    assert narrow_scale == wide_scale
    assert "grid scale" in note
    assert "not ground distance" in note


def test_polygon_hole_and_multi_geometries_render():
    outer = [[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]
    hole = [[40, 40], [60, 40], [60, 60], [40, 60], [40, 40]]
    polygon = {"geometry": {"type": "Polygon", "coordinates": [outer, hole]}}
    raw, _, _ = _render([polygon])
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    width, height = image.size
    margin, header, footer = max(40, width // 25), max(60, height // 14), max(70, height // 12)
    frame_top, frame_bottom = margin + header, height - margin - footer
    center_x, center_y = width // 2, (frame_top + frame_bottom) // 2
    center = image.getpixel((center_x, center_y))
    painted = image.getpixel((center_x - 150, center_y - 100))
    # Hole remains unpainted (light grid/background), while polygon is visibly blue.
    assert max(center) - min(center) < 25
    assert painted[2] > painted[0] + 40
    multi = {"geometry": {"type": "MultiPoint", "coordinates": [[25, 25], [75, 75]]}}
    raw_multi, _, _ = _render([multi])
    other = Image.open(io.BytesIO(raw_multi)).convert("RGB")
    blue = [0, 0]
    for y in range(frame_top, frame_bottom):
        for x in range(margin, width - margin):
            red, _, b = other.getpixel((x, y))
            if b > red + 40:
                blue[int(x >= center_x)] += 1
    assert min(blue) > 20


def test_legend_overflow_rejected_before_export():
    layers = [{"name": f"control-{i}", "features": []} for i in range(21)]
    with pytest.raises(PlatformValidationError, match="legend does not fit"):
        _render([], legend=True, layers=layers)
