"""Restricted, request-time provider profiles for R010.

Only explicitly operator-approved public sample regions are supported.
No user-supplied URL, credentials, or geometry reaches outbound transport.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import struct
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

from PIL import Image

from openvietgis_api.domains.external_sources.domain import (
    AllowlistedHostRecord,
    ExternalConnectionRecord,
    ExternalProtocol,
    default_external_capabilities,
    validate_endpoint_against_allowlist,
)
from openvietgis_api.domains.platform_errors import (
    PlatformDomainError,
    PlatformForbiddenError,
    PlatformValidationError,
)

PROFILE_ENV = "OPENVIETGIS_EXTERNAL_PROVIDER_PROFILES"
XML_MAX = 512 * 1024
MAP_MAX = 2 * 1024 * 1024
GEOJSON_MAX = 512 * 1024
FEATURE_LIMIT = 100
MAP_SIZE = 256

BBox = tuple[float, float, float, float]
Fetch = Callable[[str, str, int], bytes]


@dataclass(frozen=True, slots=True)
class RangeResponse:
    data: bytes
    total: int
    etag: str


RangeFetch = Callable[[str, int, int, str | None, int | None, float], RangeResponse]


class ProviderUnavailable(PlatformDomainError):
    def __init__(self, message: str = "external provider response could not be verified") -> None:
        super().__init__(
            message,
            code="PROVIDER_UNAVAILABLE",
            status_code=502,
            details={"availability": "unavailable"},
        )


WEB_MERCATOR_RADIUS = 6378137.0
WEB_MERCATOR_HALF = math.pi * WEB_MERCATOR_RADIUS


@dataclass(frozen=True, slots=True)
class TileProfile:
    kind: str
    z: int
    x: int
    y: int
    template: str | None = None
    matrix_set: str | None = None
    matrix: str | None = None
    style: str | None = None

    @property
    def bbox(self) -> BBox:
        step = 2 * WEB_MERCATOR_HALF / 2**self.z
        left = -WEB_MERCATOR_HALF + step * self.x
        top = WEB_MERCATOR_HALF - step * self.y
        return left, top - step, left + step, top


@dataclass(frozen=True, slots=True)
class CogProfile:
    source_bbox: BBox
    source_width: int
    source_height: int
    # Explicitly approve partial range/window access for this source.
    allow_viewport: bool = False


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    endpoint: str
    protocol: ExternalProtocol
    layer: str
    crs: int
    bbox: BBox
    attribution: str
    license_text: str
    tile: TileProfile | None = None
    cog: CogProfile | None = None


def _bbox(raw: Any, crs: int) -> BBox:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise ValueError("invalid bbox")
    if any(type(x) not in (float, int) for x in raw):
        raise ValueError("invalid bbox")
    a, b, c, d = (float(x) for x in raw)
    x_limit, y_limit = (180, 90) if crs == 4326 else (20037508.35, 20037508.35)
    if not (-x_limit <= a < c <= x_limit and -y_limit <= b < d <= y_limit):
        raise ValueError("invalid bbox")
    return a, b, c, d


def endpoint_is_public_profile(endpoint: str) -> bool:
    """Only a canonical HTTPS endpoint path; exclude query/auth/fragments."""
    try:
        p = urlsplit(endpoint)
        return bool(
            len(endpoint) <= 1000
            and p.scheme == "https"
            and p.hostname
            and p.netloc == p.hostname + (f":{p.port}" if p.port else "")
            and p.port in (None, 443)
            and p.path.startswith("/")
            and "?" not in endpoint
            and "#" not in endpoint
            and not p.query
            and not p.fragment
            and "%" not in p.path
            and "\\" not in p.path
            and "//" not in p.path
            and not any(x in (".", "..") for x in p.path.split("/"))
            and endpoint.isascii()
            and all(ord(c) > 32 and ord(c) != 127 for c in endpoint)
        )
    except ValueError:
        return False


def _near_bbox(a: BBox, b: BBox) -> bool:
    return all(math.isclose(x, y, rel_tol=0, abs_tol=1e-5) for x, y in zip(a, b, strict=True))


def _tile_profile(raw: Any, endpoint: str, bbox: BBox) -> TileProfile:
    if not isinstance(raw, dict):
        raise ValueError("tile profile required")
    kind, z, x, y = (raw.get(k) for k in ("kind", "z", "x", "y"))
    if not (
        kind in ("xyz", "wmts")
        and type(z) is int
        and 0 <= z <= 20
        and type(x) is int
        and 0 <= x < 2**z
        and type(y) is int
        and 0 <= y < 2**z
    ):
        raise ValueError("invalid fixed tile coordinates")
    if kind == "xyz":
        if set(raw) - {"kind", "z", "x", "y", "template", "matrix_set", "matrix", "style"}:
            raise ValueError("unknown tile fields")
        template = raw.get("template")
        if not isinstance(template, str) or any(
            template.count(token) != 1 for token in ("{z}", "{x}", "{y}")
        ):
            raise ValueError("invalid tile template")
        rendered = template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
        if (
            "{" in rendered
            or "}" in rendered
            or not endpoint_is_public_profile(rendered)
            or urlsplit(rendered).netloc != urlsplit(endpoint).netloc
            or any(raw.get(k) is not None for k in ("matrix_set", "matrix", "style"))
        ):
            raise ValueError("unsafe tile template")
        tile = TileProfile(kind, z, x, y, template=template)
    else:
        if (
            set(raw) - {"kind", "z", "x", "y", "template", "matrix_set", "matrix", "style"}
            or raw.get("template") is not None
        ):
            raise ValueError("unknown tile fields")
        matrix_set, matrix, style = (raw.get(k) for k in ("matrix_set", "matrix", "style"))
        if not all(
            isinstance(value, str)
            and 1 <= len(value) <= 200
            and all(c.isascii() and (c.isalnum() or c in "_-.:") for c in value)
            for value in (matrix_set, matrix, style)
        ):
            raise ValueError("invalid fixed WMTS matrix/style")
        tile = TileProfile(kind, z, x, y, matrix_set=matrix_set, matrix=matrix, style=style)
    if not _near_bbox(tile.bbox, bbox):
        raise ValueError("tile coordinates do not match approved extent")
    return tile


def _cog_profile(raw: Any, crs: int, approved_bbox: BBox) -> CogProfile:
    if not isinstance(raw, dict) or set(raw) != {
        "source_bbox",
        "source_width",
        "source_height",
        "allow_viewport",
    }:
        raise ValueError("invalid COG profile")
    source_bbox = _bbox(raw["source_bbox"], crs)
    width, height = raw["source_width"], raw["source_height"]
    allow_viewport = raw["allow_viewport"]
    if not (
        type(width) is int
        and type(height) is int
        and 1 <= width <= 32768
        and 1 <= height <= 32768
        and type(allow_viewport) is bool
        and _contains(source_bbox, approved_bbox)
    ):
        raise ValueError("invalid COG extent/dimensions")
    return CogProfile(source_bbox, width, height, allow_viewport)


def load_profiles() -> tuple[ProviderProfile, ...]:
    """Invalid deployment policy is fail-closed, never a wildcard."""
    try:
        raw = os.environ.get(PROFILE_ENV, "[]")
        if len(raw) > 64 * 1024:
            return ()
        entries = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if not isinstance(entries, list) or len(entries) > 100:
            return ()
        profiles = []
        for entry in entries:
            required = {
                "endpoint",
                "protocol",
                "layer",
                "crs",
                "bbox",
                "attribution",
                "license_text",
            }
            if not isinstance(entry, dict) or not required <= set(entry) <= required | {
                "tile",
                "cog",
            }:
                return ()
            endpoint = entry["endpoint"]
            protocol = ExternalProtocol(entry["protocol"])
            crs = entry["crs"]
            layer = entry["layer"]
            attribution, license_text = entry["attribution"], entry["license_text"]
            if (
                not isinstance(endpoint, str)
                or not endpoint_is_public_profile(endpoint)
                or type(crs) is not int
                or crs not in (4326, 3857)
                or (protocol == ExternalProtocol.WFS_OGC_FEATURES and crs != 4326)
                or (protocol == ExternalProtocol.WMTS_XYZ and crs != 3857)
                or (protocol != ExternalProtocol.WMTS_XYZ and entry.get("tile") is not None)
                or (protocol != ExternalProtocol.COG_GEOTIFF and entry.get("cog") is not None)
                or not isinstance(layer, str)
                or not (1 <= len(layer) <= 200)
                or not all(c.isascii() and (c.isalnum() or c in "_-.:") for c in layer)
                or not isinstance(attribution, str)
                or not isinstance(license_text, str)
                or not (1 <= len(attribution.strip()) <= 300)
                or not (1 <= len(license_text.strip()) <= 300)
                or attribution == "External Provider"
                or license_text.startswith("Provider License Terms")
            ):
                return ()
            bbox = _bbox(entry["bbox"], crs)
            tile = (
                _tile_profile(entry.get("tile"), endpoint, bbox)
                if protocol == ExternalProtocol.WMTS_XYZ
                else None
            )
            cog = (
                _cog_profile(entry.get("cog"), crs, bbox) if entry.get("cog") is not None else None
            )
            profiles.append(
                ProviderProfile(
                    endpoint, protocol, layer, crs, bbox, attribution, license_text, tile, cog
                )
            )
        return tuple(profiles)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return ()


def approved_profile(
    conn: ExternalConnectionRecord, allowlist: AllowlistedHostRecord
) -> ProviderProfile:
    """Match the full operator profile independently of tenant registration."""
    if conn.lifecycle != "active":
        raise PlatformForbiddenError(
            "external source is revoked",
            code="PROVIDER_REVOKED",
            details={"availability": "revoked"},
        )
    if not allowlist.enabled:
        raise PlatformForbiddenError(
            "external source is disabled",
            code="PROVIDER_DISABLED",
            details={"availability": "disabled"},
        )
    if allowlist.secret_ref_name:
        raise PlatformForbiddenError(
            "credentialed provider is unsupported",
            code="PROVIDER_DISABLED",
            details={"availability": "disabled"},
        )
    validate_endpoint_against_allowlist(conn.endpoint_url, allowlist)
    matches = [
        p
        for p in load_profiles()
        if p.endpoint == conn.endpoint_url
        and p.protocol == conn.protocol
        and p.layer == conn.layer_identifier
        and p.crs in conn.crs_codes
        and p.attribution == conn.attribution
        and p.license_text == conn.license_text
    ]
    if len(matches) != 1:
        raise PlatformForbiddenError(
            "no matching operator-approved provider profile",
            code="PROVIDER_DISABLED",
            details={"availability": "disabled"},
        )
    return matches[0]


def _request_url(profile: ProviderProfile, **parameters: str) -> str:
    return profile.endpoint + "?" + urlencode(parameters)


def _xml(raw: bytes) -> ET.Element:
    if len(raw) > XML_MAX:
        raise ProviderUnavailable()
    try:
        decoded = raw.decode("utf-8-sig")
        # Explicitly reject DTD, entity expansion, alternate encodings and XInclude.
        if "<!" in decoded or "\x00" in decoded:
            raise ValueError("unsafe XML declaration")
        root = ET.fromstring(decoded)
        stack = [(root, 0)]
        count = 0
        while stack:
            element, depth = stack.pop()
            count += 1
            if depth > 32 or count > 5000 or len(element.attrib) > 40:
                raise ValueError("XML structure limit")
            stack.extend((child, depth + 1) for child in element)
        return root
    except (UnicodeError, ET.ParseError, ValueError) as exc:
        raise ProviderUnavailable() from exc


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in parent if _tag(c) == name]


def _child(parent: ET.Element, name: str) -> ET.Element:
    items = _children(parent, name)
    if len(items) != 1:
        raise ProviderUnavailable()
    return items[0]


def _value(parent: ET.Element, name: str) -> str:
    return (_child(parent, name).text or "").strip()


def _contains(outer: BBox, inner: BBox) -> bool:
    return (
        outer[0] <= inner[0] < inner[2] <= outer[2] and outer[1] <= inner[1] < inner[3] <= outer[3]
    )


def _validate_wms(root: ET.Element, profile: ProviderProfile) -> None:
    if _tag(root) != "WMT_MS_Capabilities" or root.get("version") != "1.1.1":
        raise ProviderUnavailable()
    capability = _child(root, "Capability")
    getmap = _child(_child(capability, "Request"), "GetMap")
    if "image/png" not in {(f.text or "").strip() for f in _children(getmap, "Format")}:
        raise ProviderUnavailable()
    expected_srs = f"EPSG:{profile.crs}"
    valid = 0
    stack: list[tuple[ET.Element, set[str], BBox | None]] = [
        (layer, set(), None) for layer in _children(capability, "Layer")
    ]
    while stack:
        layer, inherited_srs, extent = stack.pop()
        srs = inherited_srs | {
            part for s in _children(layer, "SRS") for part in (s.text or "").split()
        }
        for box in _children(layer, "BoundingBox"):
            if box.get("SRS") == expected_srs:
                try:
                    extent = _bbox(
                        [float(box.attrib[k]) for k in ("minx", "miny", "maxx", "maxy")],
                        profile.crs,
                    )
                except (KeyError, ValueError) as exc:
                    raise ProviderUnavailable() from exc
        names = _children(layer, "Name")
        if len(names) == 1 and (names[0].text or "").strip() == profile.layer:
            if expected_srs not in srs or extent is None or not _contains(extent, profile.bbox):
                raise ProviderUnavailable()
            valid += 1
        stack.extend((child, srs, extent) for child in _children(layer, "Layer"))
    if valid != 1:
        raise ProviderUnavailable()


def _check_png_chunks(raw: bytes) -> None:
    """Reject ancillary compressed metadata, extra frames and oversized headers."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not PNG")
    offset = 8
    count = 0
    seen_idat = False
    seen_end = False
    allowed_small = {b"PLTE": 768, b"tRNS": 256, b"sRGB": 1, b"gAMA": 4, b"cHRM": 32, b"pHYs": 9}
    while offset < len(raw):
        if offset + 12 > len(raw) or count > 1024:
            raise ValueError("invalid PNG structure")
        length, kind = struct.unpack_from(">I4s", raw, offset)
        end = offset + 12 + length
        if end > len(raw):
            raise ValueError("truncated PNG")
        data = raw[offset + 8 : end - 4]
        if zlib.crc32(kind + data) != struct.unpack_from(">I", raw, end - 4)[0]:
            raise ValueError("PNG checksum mismatch")
        if count == 0:
            if kind != b"IHDR" or length != 13:
                raise ValueError("invalid PNG header")
            if struct.unpack_from(">II", data) != (MAP_SIZE, MAP_SIZE):
                raise ValueError("unexpected map dimensions")
        elif kind == b"IDAT":
            seen_idat = True
        elif kind == b"IEND":
            if length or end != len(raw) or not seen_idat:
                raise ValueError("invalid PNG end")
            seen_end = True
        elif kind not in allowed_small or length > allowed_small[kind]:
            raise ValueError("unsupported PNG metadata")
        offset = end
        count += 1
    if not seen_end:
        raise ValueError("incomplete PNG")


def _wms_preview(profile: ProviderProfile, fetch: Fetch) -> dict[str, Any]:
    caps = fetch(
        _request_url(profile, SERVICE="WMS", VERSION="1.1.1", REQUEST="GetCapabilities"),
        "xml",
        XML_MAX,
    )
    _validate_wms(_xml(caps), profile)
    raw = fetch(
        _request_url(
            profile,
            SERVICE="WMS",
            VERSION="1.1.1",
            REQUEST="GetMap",
            LAYERS=profile.layer,
            STYLES="",
            SRS=f"EPSG:{profile.crs}",
            BBOX=",".join(map(str, profile.bbox)),
            WIDTH=str(MAP_SIZE),
            HEIGHT=str(MAP_SIZE),
            FORMAT="image/png",
            TRANSPARENT="TRUE",
        ),
        "png",
        MAP_MAX,
    )
    return _verified_png(raw)


def _verified_png(raw: bytes) -> dict[str, Any]:
    try:
        if len(raw) > MAP_MAX:
            raise ValueError("response too large")
        _check_png_chunks(raw)
        with Image.open(io.BytesIO(raw), formats=["PNG"]) as img:
            if img.size != (MAP_SIZE, MAP_SIZE) or getattr(img, "n_frames", 1) != 1:
                raise ValueError("unexpected map dimensions")
            img.load()
            output = io.BytesIO()
            # Strip arbitrary provider metadata and re-encode validated pixels.
            img.convert("RGBA").save(output, format="PNG")
        return {
            "image_png_base64": base64.b64encode(output.getvalue()).decode("ascii"),
            "width": MAP_SIZE,
            "height": MAP_SIZE,
        }
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ProviderUnavailable() from exc


def _validate_wfs(root: ET.Element, profile: ProviderProfile) -> None:
    if _tag(root) != "WFS_Capabilities" or root.get("version") != "1.0.0":
        raise ProviderUnavailable()
    capability = _child(root, "Capability")
    formats = _child(_child(_child(capability, "Request"), "GetFeature"), "ResultFormat")
    # Bounded profile accepts either advertised GeoJSON spelling emitted by fixtures/providers.
    if not any(_tag(f).lower() in ("geojson", "json") for f in formats):
        raise ProviderUnavailable()
    feature_types = _child(root, "FeatureTypeList")
    matching = [
        feature
        for feature in _children(feature_types, "FeatureType")
        if _value(feature, "Name") == profile.layer
    ]
    if len(matching) != 1 or _value(matching[0], "SRS") != "EPSG:4326":
        raise ProviderUnavailable()
    allowed_ops = _children(feature_types, "Operations") + _children(matching[0], "Operations")
    if not any(_children(op, "Query") for op in allowed_ops):
        raise ProviderUnavailable()
    try:
        bounds = _child(matching[0], "LatLongBoundingBox")
        endpoint_extent = _bbox(
            [float(bounds.attrib[k]) for k in ("minx", "miny", "maxx", "maxy")], 4326
        )
    except (KeyError, ValueError) as exc:
        raise ProviderUnavailable() from exc
    if not _contains(endpoint_extent, profile.bbox):
        raise ProviderUnavailable()


def _validate_geometry(geometry: Any, bbox: BBox) -> None:
    """Narrow two-dimensional GeoJSON geometry; never interpret CRS override."""
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        raise ValueError("invalid geometry")
    geom_type = geometry["type"]
    depths = {
        "Point": 0,
        "MultiPoint": 1,
        "LineString": 1,
        "MultiLineString": 2,
        "Polygon": 2,
        "MultiPolygon": 3,
    }
    if type(geom_type) is not str or geom_type not in depths:
        raise ValueError("unsupported geometry")
    coords = geometry["coordinates"]
    if not isinstance(coords, list):
        raise ValueError("invalid coordinates")

    def line(value: Any, *, ring: bool = False) -> None:
        if not isinstance(value, list) or len(value) < (4 if ring else 2):
            raise ValueError("invalid line/ring")
        if ring and value[0] != value[-1]:
            raise ValueError("unclosed polygon ring")

    if geom_type == "LineString":
        line(coords)
    elif geom_type == "MultiLineString":
        for item in coords:
            line(item)
    elif geom_type == "Polygon":
        for item in coords:
            line(item, ring=True)
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            if not isinstance(polygon, list) or not polygon:
                raise ValueError("invalid polygon")
            for item in polygon:
                line(item, ring=True)
    points = 0
    stack = [(coords, depths[geom_type])]
    while stack:
        value, depth = stack.pop()
        if not isinstance(value, list) or not value:
            raise ValueError("invalid coordinates")
        if depth:
            stack.extend((x, depth - 1) for x in value)
        else:
            points += 1
            if points > 10000 or len(value) != 2 or any(type(x) not in (int, float) for x in value):
                raise ValueError("invalid point")
            x, y = value
            if not (bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]):
                raise ValueError("coordinates outside approved region")


def _reject_constant(value: str) -> Any:
    raise ValueError("non-finite JSON constant")


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _feature_collection(raw: bytes, profile: ProviderProfile) -> dict[str, Any]:
    try:
        if len(raw) > GEOJSON_MAX:
            raise ValueError("response too large")
        data = json.loads(
            raw.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_unique_object
        )
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise ValueError("expected FeatureCollection")
        # Reject response CRS override, topology/foreign members and nested properties.
        if not set(data) <= {
            "type",
            "features",
            "numberReturned",
            "totalFeatures",
            "numberMatched",
        }:
            raise ValueError("unsupported collection members")
        features = data.get("features")
        if not isinstance(features, list) or len(features) > FEATURE_LIMIT:
            raise ValueError("feature limit")
        if "numberReturned" in data and (
            type(data["numberReturned"]) is not int or data["numberReturned"] != len(features)
        ):
            raise ValueError("inconsistent feature count")
        # Match totals are upstream claims about this approved request only.
        # Missing or explicitly unknown totals cannot prove coverage, even
        # when a provider returns fewer records than MAXFEATURES.
        totals: set[int] = set()
        for name in ("numberMatched", "totalFeatures"):
            if name not in data or data[name] == "unknown":
                continue
            count = data[name]
            if type(count) is not int or not len(features) <= count <= 2**53 - 1:
                raise ValueError("invalid matched feature count")
            totals.add(count)
        if len(totals) > 1:
            raise ValueError("contradictory matched feature counts")
        matched = next(iter(totals), None)
        safe = []
        for feature in features:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise ValueError("invalid feature")
            if not set(feature) <= {"type", "id", "geometry", "properties"}:
                raise ValueError("unsupported feature members")
            _validate_geometry(feature.get("geometry"), profile.bbox)
            props = feature.get("properties")
            if not isinstance(props, dict) or len(props) > 50:
                raise ValueError("invalid properties")
            for name, value in props.items():
                if (
                    len(name) > 128
                    or type(value) not in (str, float, int, bool, type(None))
                    or (isinstance(value, str) and len(value) > 2000)
                    or (isinstance(value, float) and not math.isfinite(value))
                    or (type(value) is int and abs(value) > 2**53 - 1)
                ):
                    raise ValueError("unsupported property")
            feature_id = feature.get("id")
            if feature_id is not None and (
                type(feature_id) not in (str, int) or len(str(feature_id)) > 128
            ):
                raise ValueError("invalid id")
            safe.append(feature)
        return {
            "feature_collection": {"type": "FeatureCollection", "features": safe},
            "feature_result": {
                "returned": len(safe),
                "provider_reported_matched": matched,
                "request_limit": FEATURE_LIMIT,
                "limit_reached": len(safe) == FEATURE_LIMIT,
                "coverage": (
                    "unknown"
                    if matched is None
                    else "partial"
                    if matched > len(safe)
                    else "provider_reported_complete"
                ),
                "continuation_available": False,
            },
        }
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise ProviderUnavailable() from exc


def _wfs_preview(profile: ProviderProfile, fetch: Fetch) -> dict[str, Any]:
    caps = fetch(
        _request_url(profile, SERVICE="WFS", VERSION="1.0.0", REQUEST="GetCapabilities"),
        "xml",
        XML_MAX,
    )
    _validate_wfs(_xml(caps), profile)
    raw = fetch(
        _request_url(
            profile,
            SERVICE="WFS",
            VERSION="1.0.0",
            REQUEST="GetFeature",
            TYPENAME=profile.layer,
            SRSNAME="EPSG:4326",
            BBOX=",".join(map(str, profile.bbox)),
            MAXFEATURES=str(FEATURE_LIMIT),
            OUTPUTFORMAT="application/json",
        ),
        "json",
        GEOJSON_MAX,
    )
    return _feature_collection(raw, profile)


def provider_preview(
    profile: ProviderProfile, fetch: Fetch, range_fetch: RangeFetch | None = None
) -> dict[str, Any]:
    """No persisted success: each explicit preview verifies metadata and bytes."""
    caps = default_external_capabilities(profile.protocol)
    if profile.protocol == ExternalProtocol.WMS:
        content = _wms_preview(profile, fetch)
        caps["render"] = True
    elif profile.protocol == ExternalProtocol.WFS_OGC_FEATURES:
        content = _wfs_preview(profile, fetch)
        caps["feature_read"] = True
        caps["query"] = True  # only fixed approved bounding-box sample query
    elif profile.protocol == ExternalProtocol.WMTS_XYZ and profile.tile is not None:
        from openvietgis_api.domains.external_sources.tile_provider import tile_preview

        content = tile_preview(profile, fetch)
        caps["render"] = True
    elif profile.protocol == ExternalProtocol.COG_GEOTIFF:
        if profile.cog is not None:
            from openvietgis_api.domains.external_sources.cog_provider import cog_preview

            if range_fetch is None:
                raise ProviderUnavailable()
            content = cog_preview(profile, range_fetch, profile.bbox, MAP_SIZE, MAP_SIZE)
        else:
            from openvietgis_api.domains.external_sources.geotiff_provider import geotiff_preview

            content = geotiff_preview(profile, fetch)
        caps["render"] = True
    else:
        raise PlatformForbiddenError("unsupported provider protocol", code="PROVIDER_DISABLED")
    return {
        "availability": "available",
        "capabilities": caps,
        "scope": "operator_approved_sample",
        "layer_identifier": profile.layer,
        "crs": profile.crs,
        "bbox": profile.bbox,
        "attribution": profile.attribution,
        "license_text": profile.license_text,
        **content,
    }


def provider_viewport(
    profile: ProviderProfile,
    range_fetch: RangeFetch,
    *,
    crs: int,
    bbox: BBox,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Explicit operator-approved COG window, with no user geography sent to provider."""
    if (
        profile.protocol != ExternalProtocol.COG_GEOTIFF
        or profile.cog is None
        or not profile.cog.allow_viewport
    ):
        raise PlatformForbiddenError("provider viewport not approved", code="VIEWPORT_FORBIDDEN")
    if crs != profile.crs:
        raise PlatformValidationError("viewport CRS mismatch", code="INVALID_VIEWPORT")
    from openvietgis_api.domains.external_sources.cog_provider import cog_preview

    content = cog_preview(profile, range_fetch, bbox, width, height)
    caps = default_external_capabilities(profile.protocol)
    caps["render"] = True
    return {
        "availability": "available",
        "capabilities": caps,
        "scope": "operator_approved_viewport",
        "layer_identifier": profile.layer,
        "crs": profile.crs,
        "bbox": bbox,
        "attribution": profile.attribution,
        "license_text": profile.license_text,
        **content,
    }
