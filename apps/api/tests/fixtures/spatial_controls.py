"""Independent acceptance controls for R003 US5 (SC-004).

Transcribed directly from the public tables cited in
specs/003-spatial-catalog-crs/vn2000-control-evidence.md, and from the analytic
formula and guard rails in research.md and crs-support-matrix.md (2026-11-18).
This module deliberately imports no OpenVietGIS, PostGIS or PROJ code.

Geographic coordinates use application XY = longitude, latitude, even though
the originals print latitude first; projected XY = easting, northing, although
the EIA prints X=northing/Y=easting. Published precision is retained in DMS.
Inverse controls start with the published counterpart, not the result of a
forward transformation under test. Tolerances are software acceptance limits,
not a cadastral/survey accuracy claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import atan, degrees, log, nextafter, pi, radians, sinh, tan
from typing import Literal

type XY = tuple[float, float]
type DMS = tuple[int, int, str]
type Metric = Literal["euclidean_metre", "geodesic_metre", "max_axis_degree"]
type Unit = Literal["metre", "degree"]

CIRCULAR_EVIDENCE_URL = "https://moc.gov.vn/Images/FileVanBan/BXD_50-2025-TT-BXD_15122025.pdf"
HVS_EVIDENCE_URL = (
    "https://thamvan.mae.gov.vn/Uploads/26072025/"
    "CL25.7.%20BC%20DTM%20DA%20CHUYEN%20TAI%20HANG%20HOA%20QUANG%20NINH.pdf"
)
WEB_MERCATOR_EVIDENCE_URL = "https://proj.org/en/stable/operations/projections/webmerc.html"
CIRCULAR_EVIDENCE_ID = "circular-50-2025-tt-bxd-quang-ninh"
HVS_EVIDENCE_ID = "mae-eia-quang-ninh-table-1-4-qh-04"
WEB_MERCATOR_EVIDENCE_ID = "analytic-webmercator-formula"

CIRCULAR_TOLERANCE_METRE = 3.0
HVS_TOLERANCE_METRE = 1.0
WEB_MERCATOR_TOLERANCE_METRE = 0.001
WEB_MERCATOR_TOLERANCE_DEGREE = 1e-8
WEB_MERCATOR_RADIUS_METRE = 6378137.0
WEB_MERCATOR_MAX_LATITUDE = 85.0511287798066
WEB_MERCATOR_MAX_COORDINATE_METRE = pi * WEB_MERCATOR_RADIUS_METRE
WEB_MERCATOR_OUTPUT_EPSILON_METRE = 1e-6


def _decimal_degrees(dms: DMS) -> float:
    degree, minute, seconds = dms
    # Parsing only, retaining the independent document's decimal precision.
    assert 0 <= minute < 60 and 0 <= Decimal(seconds) < 60
    return float(Decimal(degree) + Decimal(minute) / 60 + Decimal(seconds) / 3600)


def _xy(latitude: DMS, longitude: DMS) -> XY:
    # Original printed order is lat/N first, lon/E second.
    return _decimal_degrees(longitude), _decimal_degrees(latitude)


@dataclass(frozen=True)
class GeographicControl:
    point_id: str
    vn2000_lat_dms: DMS
    vn2000_lon_dms: DMS
    wgs84_lat_dms: DMS
    wgs84_lon_dms: DMS

    @property
    def vn2000_xy(self) -> XY:
        return _xy(self.vn2000_lat_dms, self.vn2000_lon_dms)

    @property
    def wgs84_xy(self) -> XY:
        return _xy(self.wgs84_lat_dms, self.wgs84_lon_dms)


# Circular 50/2025/TT-BXD appendix: Quang Ninh port-water boundary, 0.1".
GEOGRAPHIC_CONTROLS: tuple[GeographicControl, ...] = (
    GeographicControl(
        "VH1", (21, 24, "40.0"), (108, 1, "10.0"), (21, 24, "36.4"), (108, 1, "16.8")
    ),
    GeographicControl(
        "VH2", (21, 24, "52.1"), (108, 3, "35.3"), (21, 24, "48.5"), (108, 3, "42.1")
    ),
    GeographicControl(
        "VH10", (21, 14, "10.5"), (107, 56, "46.0"), (21, 14, "06.9"), (107, 56, "52.8")
    ),
    GeographicControl(
        "CT1", (20, 58, "14.3"), (107, 45, "40.8"), (20, 58, "10.7"), (107, 45, "47.6")
    ),
    GeographicControl(
        "QY1", (20, 50, "07.8"), (106, 52, "59.2"), (20, 50, "04.2"), (106, 53, "06.0")
    ),
)


@dataclass(frozen=True)
class ProjectedControl(GeographicControl):
    # EIA Table 1.4 headers X (northing), Y (easting); decimals in metres.
    published_x_northing: float
    published_y_easting: float

    @property
    def projected_xy(self) -> XY:
        return self.published_y_easting, self.published_x_northing


# MAE EIA July 2025, printed p.45 Table 1.4 and QH-04 drawing:
# TM-3 107°45', projected 0.01 metre, geographic DMS to 0.01 arc-second.
PROJECTED_CONTROLS: tuple[ProjectedControl, ...] = (
    ProjectedControl(
        "HVS-QN1",
        (20, 42, "42.09"),
        (107, 9, "32.44"),
        (20, 42, "38.48"),
        (107, 9, "39.19"),
        2291039.83,
        438442.69,
    ),
    ProjectedControl(
        "HVS-QN2",
        (20, 43, "09.30"),
        (107, 9, "15.56"),
        (20, 43, "05.69"),
        (107, 9, "22.31"),
        2291878.33,
        437957.55,
    ),
    ProjectedControl(
        "HVS-QN3",
        (20, 43, "19.41"),
        (107, 9, "47.82"),
        (20, 43, "15.80"),
        (107, 9, "54.57"),
        2292185.83,
        438891.96,
    ),
    ProjectedControl(
        "HVS-QN4",
        (20, 42, "53.22"),
        (107, 10, "04.30"),
        (20, 42, "49.61"),
        (107, 10, "11.05"),
        2291378.72,
        439365.92,
    ),
)


def web_mercator_forward(xy: XY) -> XY:
    """Analytic EPSG:1024, independent standard-library math; no clamping."""
    longitude, latitude = xy
    radius = WEB_MERCATOR_RADIUS_METRE
    return (
        radius * radians(longitude),
        0.0 if latitude == 0.0 else radius * log(tan(pi / 4 + radians(latitude) / 2)),
    )


def web_mercator_inverse(xy: XY) -> XY:
    """Analytic inverse EPSG:1024 from independently chosen projected input."""
    easting, northing = xy
    radius = WEB_MERCATOR_RADIUS_METRE
    return degrees(easting / radius), degrees(atan(sinh(northing / radius)))


@dataclass(frozen=True)
class WebMercatorControl:
    control_id: str
    wgs84_xy: XY
    projected_xy: XY
    wgs84_point_id: str | None = None
    projected_point_id: str | None = None


def _analytic(
    control_id: str,
    xy: XY,
    wgs84_point_id: str | None = None,
    projected_point_id: str | None = None,
) -> WebMercatorControl:
    return WebMercatorControl(
        control_id, xy, web_mercator_forward(xy), wgs84_point_id, projected_point_id
    )


# Positive analytic controls: origin; deterministic Vietnam synthetic points
# (including points underlying native 3857 fixtures); near and exact
# antimeridian limits on both signs, and both exact supported latitude limits.
# At exact limit use the analytic square pi*R as inverse INPUT (not a noisy
# forward value that could be infinitesimally outside the native range).
_WEB_LIMIT = WEB_MERCATOR_MAX_COORDINATE_METRE
_WEB_LAT = WEB_MERCATOR_MAX_LATITUDE
WEB_MERCATOR_CONTROLS: tuple[WebMercatorControl, ...] = (
    _analytic("origin", (0.0, 0.0)),
    _analytic("vn-grid-origin", (106.6, 10.7), "point-000001", "merc-000001"),
    _analytic("vn-grid-upper", (106.6996, 10.7294), None, "merc-000002"),
    _analytic("quang-ninh", (107.157, 20.715), None, "merc-000003"),
    _analytic("vn-grid-last-point", (106.699, 10.739), "point-004000"),
    _analytic("positive-near-antimeridian", (179.999999, 30.0)),
    _analytic("negative-near-antimeridian", (-179.999999, -30.0)),
    WebMercatorControl("positive-exact-boundary", (180.0, _WEB_LAT), (_WEB_LIMIT, _WEB_LIMIT)),
    WebMercatorControl("negative-exact-boundary", (-180.0, -_WEB_LAT), (-_WEB_LIMIT, -_WEB_LIMIT)),
)


@dataclass(frozen=True)
class CoordinateControl:
    point_id: str
    source_xy: XY
    expected_xy: XY
    # None = direct mathematical or repository control only, not an existing
    # materialized fixture point that can be selected through the HTTP API.
    reference_key: str | None


@dataclass(frozen=True)
class DirectedControlSet:
    source_code: int
    target_code: int
    operation_id: str
    tolerance: float
    tolerance_unit: Unit
    evidence_id: str
    evidence_url: str
    controls: tuple[CoordinateControl, ...]
    metric: Metric


def _web_controls(forward: bool) -> tuple[CoordinateControl, ...]:
    if forward:
        return tuple(
            CoordinateControl(
                control.wgs84_point_id or control.control_id,
                control.wgs84_xy,
                web_mercator_forward(control.wgs84_xy),
                "reference_points_4326" if control.wgs84_point_id else None,
            )
            for control in WEB_MERCATOR_CONTROLS
        )
    return tuple(
        CoordinateControl(
            control.projected_point_id or control.control_id,
            control.projected_xy,
            web_mercator_inverse(control.projected_xy),
            "reference_points_3857" if control.projected_point_id else None,
        )
        for control in WEB_MERCATOR_CONTROLS
    )


def _geographic_controls(forward: bool) -> tuple[CoordinateControl, ...]:
    return tuple(
        CoordinateControl(
            control.point_id,
            control.vn2000_xy if forward else control.wgs84_xy,
            control.wgs84_xy if forward else control.vn2000_xy,
            "reference_points_4756" if forward else "reference_points_4326_quang_ninh",
        )
        for control in GEOGRAPHIC_CONTROLS
    )


def _projected_controls(
    source_code: Literal[4326, 4756, 5899],
    target_code: Literal[4326, 4756, 5899],
) -> tuple[CoordinateControl, ...]:
    # Every source *and* target is independently published in the EIA.
    key = {
        4326: "reference_points_4326_hvs",
        4756: "reference_points_4756_hvs",
        5899: "reference_points_5899",
    }[source_code]
    controls = []
    for control in PROJECTED_CONTROLS:
        coordinates = {
            4326: control.wgs84_xy,
            4756: control.vn2000_xy,
            5899: control.projected_xy,
        }
        controls.append(
            CoordinateControl(
                control.point_id, coordinates[source_code], coordinates[target_code], key
            )
        )
    return tuple(controls)


# Explicit allow-list of eight coordinate-changing directions only. Neither
# identity nor any 3405/3406, indirect, arbitrary, or custom edge is included.
# Metric is target-space: same-datum geodesic metres for geographic VN-2000
# controls, Euclidean metres for projected output, maximum axis degrees for
# analytic inverse. Do not compare coordinates across datums.
DIRECTED_CONTROL_SETS: tuple[DirectedControlSet, ...] = (
    DirectedControlSet(
        4326,
        3857,
        "epsg-1024-forward",
        WEB_MERCATOR_TOLERANCE_METRE,
        "metre",
        WEB_MERCATOR_EVIDENCE_ID,
        WEB_MERCATOR_EVIDENCE_URL,
        _web_controls(True),
        "euclidean_metre",
    ),
    DirectedControlSet(
        3857,
        4326,
        "epsg-1024-inverse",
        WEB_MERCATOR_TOLERANCE_DEGREE,
        "degree",
        WEB_MERCATOR_EVIDENCE_ID,
        WEB_MERCATOR_EVIDENCE_URL,
        _web_controls(False),
        "max_axis_degree",
    ),
    DirectedControlSet(
        4756,
        4326,
        "epsg-6960-forward",
        CIRCULAR_TOLERANCE_METRE,
        "metre",
        CIRCULAR_EVIDENCE_ID,
        CIRCULAR_EVIDENCE_URL,
        _geographic_controls(True),
        "geodesic_metre",
    ),
    DirectedControlSet(
        4326,
        4756,
        "epsg-6960-inverse",
        CIRCULAR_TOLERANCE_METRE,
        "metre",
        CIRCULAR_EVIDENCE_ID,
        CIRCULAR_EVIDENCE_URL,
        _geographic_controls(False),
        "geodesic_metre",
    ),
    DirectedControlSet(
        5899,
        4756,
        "epsg-5899-inverse-tm3",
        HVS_TOLERANCE_METRE,
        "metre",
        HVS_EVIDENCE_ID,
        HVS_EVIDENCE_URL,
        _projected_controls(5899, 4756),
        "geodesic_metre",
    ),
    DirectedControlSet(
        4756,
        5899,
        "epsg-5899-forward-tm3",
        HVS_TOLERANCE_METRE,
        "metre",
        HVS_EVIDENCE_ID,
        HVS_EVIDENCE_URL,
        _projected_controls(4756, 5899),
        "euclidean_metre",
    ),
    DirectedControlSet(
        5899,
        4326,
        "epsg-5899-to-4326-via-6960",
        HVS_TOLERANCE_METRE,
        "metre",
        HVS_EVIDENCE_ID,
        HVS_EVIDENCE_URL,
        _projected_controls(5899, 4326),
        "geodesic_metre",
    ),
    DirectedControlSet(
        4326,
        5899,
        "epsg-4326-to-5899-via-6960",
        HVS_TOLERANCE_METRE,
        "metre",
        HVS_EVIDENCE_ID,
        HVS_EVIDENCE_URL,
        _projected_controls(4326, 5899),
        "euclidean_metre",
    ),
)


@dataclass(frozen=True)
class DomainControl:
    control_id: str
    source_code: int
    target_code: int
    source_xy: XY
    # A source may be valid natively yet fail the requested operation's domain.
    valid_native: bool
    reference_key: str | None = None
    point_id: str | None = None


OUT_OF_DOMAIN_CONTROLS: tuple[DomainControl, ...] = (
    DomainControl(
        "web-latitude-positive-just-outside",
        4326,
        3857,
        (0.0, nextafter(_WEB_LAT, 90.0)),
        True,
    ),
    DomainControl(
        "web-latitude-negative-just-outside",
        4326,
        3857,
        (0.0, nextafter(-_WEB_LAT, -90.0)),
        True,
    ),
    DomainControl(
        "web-valid-native-latitude-86",
        4326,
        3857,
        (0.0, 86.0),
        True,
        "reference_points_4326_webmerc_out_of_area",
        "point-000001",
    ),
    DomainControl("longitude-positive-outside", 4326, 3857, (180.000001, 0.0), False),
    DomainControl("longitude-negative-outside", 4326, 3857, (-180.000001, 0.0), False),
    DomainControl("nonfinite", 4326, 3857, (float("nan"), 0.0), False),
    DomainControl("infinite", 4326, 3857, (0.0, float("inf")), False),
    DomainControl("web-easting-positive-outside", 3857, 4326, (_WEB_LIMIT + 1e-7, 0.0), False),
    DomainControl("web-easting-negative-outside", 3857, 4326, (-_WEB_LIMIT - 1e-7, 0.0), False),
    DomainControl("web-northing-positive-outside", 3857, 4326, (0.0, _WEB_LIMIT + 1e-7), False),
    DomainControl("web-northing-negative-outside", 3857, 4326, (0.0, -_WEB_LIMIT - 1e-7), False),
    DomainControl(
        "vn2000-region-wgs84-outside",
        4326,
        4756,
        (106.6, 10.7),
        True,
        "reference_points_4326",
        "point-000001",
    ),
    DomainControl("vn2000-region-native-outside", 4756, 4326, (108.071, 21.0), True),
    DomainControl("tm3-region-wgs84-outside", 4326, 5899, (107.181, 20.715), True),
    DomainControl("tm3-region-vn2000-outside", 4756, 5899, (107.149, 20.715), True),
    # TM-3 projection false easting at the equator is unambiguously outside
    # the closed Quang Ninh applicability region, independently of a transform.
    DomainControl("tm3-to-vn2000-outside", 5899, 4756, (500000.0, 0.0), True),
    DomainControl("tm3-to-wgs84-outside", 5899, 4326, (500000.0, 0.0), True),
)


@dataclass(frozen=True)
class RegionBoundary:
    """Closed application XY rectangle from research.md, not official boundary."""

    region_id: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def inside(self) -> tuple[XY, ...]:
        mid_x = (self.min_x + self.max_x) / 2
        mid_y = (self.min_y + self.max_y) / 2
        return (
            (self.min_x, self.min_y),
            (self.min_x, self.max_y),
            (self.max_x, self.min_y),
            (self.max_x, self.max_y),
            (self.min_x, mid_y),
            (self.max_x, mid_y),
            (mid_x, self.min_y),
            (mid_x, self.max_y),
            (mid_x, mid_y),
        )

    @property
    def outside(self) -> tuple[XY, ...]:
        mid_x = (self.min_x + self.max_x) / 2
        mid_y = (self.min_y + self.max_y) / 2
        return (
            (nextafter(self.min_x, float("-inf")), mid_y),
            (nextafter(self.max_x, float("inf")), mid_y),
            (mid_x, nextafter(self.min_y, float("-inf"))),
            (mid_x, nextafter(self.max_y, float("inf"))),
        )


# Points concern *one* input/output domain check. They are not promised
# transformations at region corners: the target vertex must also stay inside
# the rectangle, and VN-2000 requires trusted reference fixture provenance.
CLOSED_REGION_BOUNDARIES: tuple[RegionBoundary, ...] = (
    RegionBoundary("web-mercator", -180.0, -_WEB_LAT, 180.0, _WEB_LAT),
    RegionBoundary("quang-ninh-geographic", 106.88, 20.70, 108.07, 21.42),
    RegionBoundary("quang-ninh-tm3", 107.15, 20.70, 107.18, 20.73),
)
