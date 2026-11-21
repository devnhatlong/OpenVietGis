"""Independent bounded planar COGO oracles."""

from __future__ import annotations

import math

import pytest

from openvietgis_api.domains.cad.domain import (
    compute_line_intersection,
    compute_parallel_offset,
    compute_precision_snap,
    compute_traverse_point,
)
from openvietgis_api.domains.platform_errors import PlatformValidationError


@pytest.mark.parametrize(
    ("bearing", "expected"),
    [
        (0, (0, 100)),
        (90, (100, 0)),
        (180, (0, -100)),
        (270, (-100, 0)),
    ],
)
def test_cardinal_bearings(bearing, expected):
    result = compute_traverse_point(origin=(0, 0), distance=100, azimuth_degrees=bearing)
    assert result["endpoint"] == pytest.approx(expected, abs=1e-10)


def test_intersection_offset_and_deterministic_snap():
    crossing = compute_line_intersection(seg_a=((0, 0), (10, 10)), seg_b=((0, 10), (10, 0)))
    assert crossing["point"] == [5, 5]
    assert crossing["within_segments"]
    offset = compute_parallel_offset(segment=((0, 0), (10, 0)), offset_distance=2)
    assert offset["segment"] == [[0, -2], [10, -2]]
    refs = [((-1, 0), (-5, 0)), ((1, 0), (5, 0))]
    a = compute_precision_snap(target=(0, 0), segments=refs, tolerance=1)
    b = compute_precision_snap(target=(0, 0), segments=list(reversed(refs)), tolerance=1)
    assert a == b and a["point"] == [-1, 0]


@pytest.mark.parametrize(
    "case",
    [
        lambda: compute_traverse_point(origin=(math.inf, 0), distance=3, azimuth_degrees=0),
        lambda: compute_line_intersection(seg_a=((1, 1), (1, 1)), seg_b=((0, 0), (2, 2))),
        lambda: compute_parallel_offset(segment=((0, 0), (1, 1)), offset_distance=math.nan),
        lambda: compute_precision_snap(target=(0, 0), segments=[], tolerance=-1),
        lambda: compute_precision_snap(
            target=(0, 0), segments=[((0, 0), (1, 1))] * 10001, tolerance=1
        ),
    ],
)
def test_invalid_controls_fail_before_output(case):
    with pytest.raises(PlatformValidationError):
        case()
