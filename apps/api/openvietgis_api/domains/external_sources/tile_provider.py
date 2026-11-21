"""Operator-approved single-tile preview, XYZ TileJSON and WMTS KVP."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlsplit

from openvietgis_api.domains.external_sources.provider import (
    GEOJSON_MAX,
    MAP_MAX,
    MAP_SIZE,
    WEB_MERCATOR_HALF,
    WEB_MERCATOR_RADIUS,
    XML_MAX,
    Fetch,
    ProviderProfile,
    ProviderUnavailable,
    TileProfile,
    _bbox,
    _child,
    _children,
    _contains,
    _near_bbox,
    _reject_constant,
    _request_url,
    _unique_object,
    _value,
    _verified_png,
    _xml,
    endpoint_is_public_profile,
)


def _geographic_tile_bbox(tile: TileProfile) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = tile.bbox

    def lon(x: float) -> float:
        return max(-180.0, min(180.0, math.degrees(x / WEB_MERCATOR_RADIUS)))

    def lat(y: float) -> float:
        return math.degrees(math.atan(math.sinh(y / WEB_MERCATOR_RADIUS)))

    return lon(x0), lat(y0), lon(x1), lat(y1)


def _xyz(profile: ProviderProfile, tile: TileProfile, fetch: Fetch) -> bytes:
    raw = fetch(profile.endpoint, "json", GEOJSON_MAX)
    try:
        if len(raw) > GEOJSON_MAX:
            raise ValueError("tile metadata exceeds bounds")
        meta = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if (
            not isinstance(meta, dict)
            or meta.get("tilejson") not in ("2.2.0", "3.0.0")
            or meta.get("name") != profile.layer
            or meta.get("scheme", "xyz") != "xyz"
            or meta.get("attribution") != profile.attribution
            or meta.get("tiles") != [tile.template]
            or type(meta.get("minzoom")) is not int
            or type(meta.get("maxzoom")) is not int
            or not 0 <= meta["minzoom"] <= tile.z <= meta["maxzoom"] <= 30
        ):
            raise ValueError("tile metadata mismatch")
        extent = _bbox(meta.get("bounds"), 4326)
        if not _contains(extent, _geographic_tile_bbox(tile)):
            raise ValueError("tile not within provider extent")
        if tile.template is None:
            raise ValueError("template missing")
        # The advertised URL is never executed. The already approved template only.
        url = (
            tile.template.replace("{z}", str(tile.z))
            .replace("{x}", str(tile.x))
            .replace("{y}", str(tile.y))
        )
        if (
            not endpoint_is_public_profile(url)
            or urlsplit(url).netloc != urlsplit(profile.endpoint).netloc
        ):
            raise ValueError("tile URL invalid")
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise ProviderUnavailable() from exc
    return fetch(url, "png", MAP_MAX)


def _find_identifier(parent: ET.Element, kind: str, identifier: str | None) -> ET.Element:
    found = [node for node in _children(parent, kind) if _value(node, "Identifier") == identifier]
    if len(found) != 1:
        raise ProviderUnavailable()
    return found[0]


def _wmts(profile: ProviderProfile, tile: TileProfile, fetch: Fetch) -> bytes:
    raw = fetch(
        _request_url(profile, SERVICE="WMTS", VERSION="1.0.0", REQUEST="GetCapabilities"),
        "xml",
        XML_MAX,
    )
    root = _xml(raw)
    if (
        root.tag != "{http://www.opengis.net/wmts/1.0}Capabilities"
        or root.get("version") != "1.0.0"
    ):
        raise ProviderUnavailable()
    operations = _child(root, "OperationsMetadata")
    get_tile = [op for op in _children(operations, "Operation") if op.get("name") == "GetTile"]
    if len(get_tile) != 1:
        raise ProviderUnavailable()
    # Require advertised KVP support; never follow an advertised OnlineResource.
    encodings = [
        value.text
        for node in get_tile[0].iter()
        if node.tag.rsplit("}", 1)[-1] == "Constraint" and node.get("name") == "GetEncoding"
        for value in node.iter()
        if value.tag.rsplit("}", 1)[-1] == "Value"
    ]
    if "KVP" not in encodings:
        raise ProviderUnavailable()
    contents = _child(root, "Contents")
    layer = _find_identifier(contents, "Layer", profile.layer)
    if "image/png" not in {(f.text or "").strip() for f in _children(layer, "Format")}:
        raise ProviderUnavailable()
    _find_identifier(layer, "Style", tile.style)
    links = [
        link
        for link in _children(layer, "TileMatrixSetLink")
        if _value(link, "TileMatrixSet") == tile.matrix_set
    ]
    if len(links) != 1:
        raise ProviderUnavailable()
    matrix_set = _find_identifier(contents, "TileMatrixSet", tile.matrix_set)
    if _value(matrix_set, "SupportedCRS") not in (
        "urn:ogc:def:crs:EPSG::3857",
        "http://www.opengis.net/def/crs/EPSG/0/3857",
        "EPSG:3857",
    ):
        raise ProviderUnavailable()
    matrix = _find_identifier(matrix_set, "TileMatrix", tile.matrix)
    try:
        dimension = 2**tile.z
        resolution = 2 * WEB_MERCATOR_HALF / (dimension * MAP_SIZE)
        scale = float(_value(matrix, "ScaleDenominator"))
        corner = tuple(map(float, _value(matrix, "TopLeftCorner").split()))
        if (
            len(corner) != 2
            or not math.isclose(corner[0], -WEB_MERCATOR_HALF, rel_tol=0, abs_tol=1e-5)
            or not math.isclose(corner[1], WEB_MERCATOR_HALF, rel_tol=0, abs_tol=1e-5)
            or not math.isclose(scale, resolution / 0.00028, rel_tol=1e-8, abs_tol=1e-8)
            or int(_value(matrix, "TileWidth")) != MAP_SIZE
            or int(_value(matrix, "TileHeight")) != MAP_SIZE
            or int(_value(matrix, "MatrixWidth")) != dimension
            or int(_value(matrix, "MatrixHeight")) != dimension
        ):
            raise ValueError("not canonical Web Mercator tile matrix")
        limits = _children(links[0], "TileMatrixSetLimits")
        if limits:
            if len(limits) != 1:
                raise ValueError("ambiguous limits")
            chosen = [
                limit
                for limit in _children(limits[0], "TileMatrixLimits")
                if _value(limit, "TileMatrix") == tile.matrix
            ]
            if len(chosen) != 1:
                raise ValueError("matrix omitted by layer limits")
            limit = chosen[0]
            minrow, maxrow, mincol, maxcol = (
                int(_value(limit, field))
                for field in ("MinTileRow", "MaxTileRow", "MinTileCol", "MaxTileCol")
            )
            if not (
                0 <= minrow <= tile.y <= maxrow < dimension
                and 0 <= mincol <= tile.x <= maxcol < dimension
            ):
                raise ValueError("tile outside layer limits")
    except (ValueError, OverflowError) as exc:
        raise ProviderUnavailable() from exc
    return fetch(
        _request_url(
            profile,
            SERVICE="WMTS",
            VERSION="1.0.0",
            REQUEST="GetTile",
            LAYER=profile.layer,
            STYLE=str(tile.style),
            FORMAT="image/png",
            TILEMATRIXSET=str(tile.matrix_set),
            TILEMATRIX=str(tile.matrix),
            TILEROW=str(tile.y),
            TILECOL=str(tile.x),
        ),
        "png",
        MAP_MAX,
    )


def tile_preview(profile: ProviderProfile, fetch: Fetch) -> dict[str, Any]:
    tile = profile.tile
    if tile is None or profile.crs != 3857 or not _near_bbox(tile.bbox, profile.bbox):
        raise ProviderUnavailable()
    if tile.kind == "xyz":
        raw = _xyz(profile, tile, fetch)
    elif tile.kind == "wmts":
        raw = _wmts(profile, tile, fetch)
    else:
        raise ProviderUnavailable()
    return {
        **_verified_png(raw),
        "sample": {"kind": tile.kind, "z": tile.z, "x": tile.x, "y": tile.y},
    }
