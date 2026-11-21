"""Independent tile matrix, pixel and range oracles; no network or customer data."""

from __future__ import annotations

import base64
import io
import json
import math
import struct
from dataclasses import asdict, replace
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image

from openvietgis_api.adapters.http.external_provider_transport import fetch_provider_bytes
from openvietgis_api.domains.external_sources.domain import ExternalProtocol
from openvietgis_api.domains.external_sources.provider import (
    PROFILE_ENV,
    BBox,
    ProviderProfile,
    ProviderUnavailable,
    TileProfile,
    load_profiles,
    provider_preview,
)
from tests.unit.test_external_provider import (
    ATTRIBUTION,
    HOST,
    RIGHTS,
    FixtureProvider,
    png,
)

# Independent tile matrix oracle: OSM Web Mercator radius and canonical tile
# coordinates at z=2, x=3, y=1, not derived from implementation.
HALF = 20037508.342789244
TILE_BBOX: BBox = (HALF / 2, 0, HALF, HALF / 2)
XYZ_TILE = TileProfile("xyz", 2, 3, 1, template=f"https://{HOST}/tiles/{{z}}/{{x}}/{{y}}.png")
WMTS_TILE = TileProfile("wmts", 2, 3, 1, matrix_set="WebMercatorQuad", matrix="2", style="default")
XYZ = ProviderProfile(
    f"https://{HOST}/tilejson.json",
    ExternalProtocol.WMTS_XYZ,
    "tiles",
    3857,
    TILE_BBOX,
    ATTRIBUTION,
    RIGHTS,
    XYZ_TILE,
)
WMTS = replace(XYZ, endpoint=f"https://{HOST}/wmts", tile=WMTS_TILE)
TIFF_BBOX = (105.5, 20.5, 106.5, 21.5)
TIFF = ProviderProfile(
    f"https://{HOST}/sample.tif",
    ExternalProtocol.COG_GEOTIFF,
    "raster",
    4326,
    TIFF_BBOX,
    ATTRIBUTION,
    RIGHTS,
)
TILE_JSON = {
    "tilejson": "3.0.0",
    "name": "tiles",
    "scheme": "xyz",
    "tiles": [XYZ_TILE.template],
    "attribution": ATTRIBUTION,
    "minzoom": 0,
    "maxzoom": 4,
    "bounds": [-180, -85.0511287798066, 180, 85.0511287798066],
}
SCALE = 2 * HALF / (4 * 256) / 0.00028
WMTS_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0"
 xmlns:ows="http://www.opengis.net/ows/1.1" version="1.0.0">
 <ows:OperationsMetadata><ows:Operation name="GetTile">
 <ows:DCP><ows:HTTP><ows:Get><ows:Constraint name="GetEncoding">
 <ows:AllowedValues><ows:Value>KVP</ows:Value></ows:AllowedValues>
 </ows:Constraint></ows:Get></ows:HTTP></ows:DCP></ows:Operation></ows:OperationsMetadata>
 <Contents><Layer><ows:Identifier>tiles</ows:Identifier>
 <Style isDefault="true"><ows:Identifier>default</ows:Identifier></Style>
 <Format>image/png</Format><TileMatrixSetLink><TileMatrixSet>WebMercatorQuad</TileMatrixSet>
 <TileMatrixSetLimits><TileMatrixLimits><TileMatrix>2</TileMatrix>
 <MinTileRow>0</MinTileRow><MaxTileRow>3</MaxTileRow>
 <MinTileCol>0</MinTileCol><MaxTileCol>3</MaxTileCol>
 </TileMatrixLimits></TileMatrixSetLimits></TileMatrixSetLink></Layer>
 <TileMatrixSet><ows:Identifier>WebMercatorQuad</ows:Identifier>
 <ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
 <TileMatrix><ows:Identifier>2</ows:Identifier>
 <ScaleDenominator>{SCALE}</ScaleDenominator>
 <TopLeftCorner>{-HALF} {HALF}</TopLeftCorner>
 <TileWidth>256</TileWidth><TileHeight>256</TileHeight>
 <MatrixWidth>4</MatrixWidth><MatrixHeight>4</MatrixHeight>
 </TileMatrix></TileMatrixSet></Contents></Capabilities>""".encode()


def fixture_tiff(*, epsg: int = 4326, compression: int = 1, bad_offset: bool = False) -> bytes:
    """Hand-build valid tiled TIFF with four independent 16x16 pixel quadrants."""
    tags = {
        256: (4, (32,)),
        257: (4, (32,)),
        258: (3, (8,)),
        259: (3, (compression,)),
        262: (3, (1,)),
        277: (3, (1,)),
        284: (3, (1,)),
        322: (4, (16,)),
        323: (4, (16,)),
        324: (4, (0, 0, 0, 0)),
        325: (4, (256,) * 4),
        33550: (12, (1 / 32, 1 / 32, 0)),
        33922: (12, (0, 0, 0, 105.5, 21.5, 0)),
        34735: (3, (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, epsg)),
    }
    fmt = {3: "H", 4: "I", 12: "d"}
    count = len(tags)
    ifd_end = 8 + 2 + count * 12 + 4
    # Pre-compute data area, then set tile offsets correctly.
    meta_size = sum(
        len(values) * struct.calcsize("<" + fmt[kind])
        for kind, values in tags.values()
        if len(values) * struct.calcsize("<" + fmt[kind]) > 4
    )
    tile_start = ifd_end + meta_size
    tags[324] = (4, tuple((8 if bad_offset and i == 0 else tile_start + i * 256) for i in range(4)))
    directory = bytearray()
    values_area = bytearray()
    for tag, (kind, values) in sorted(tags.items()):
        packed = struct.pack("<" + fmt[kind] * len(values), *values)
        directory.extend(struct.pack("<HHI", tag, kind, len(values)))
        if len(packed) <= 4:
            directory.extend(packed.ljust(4, b"\0"))
        else:
            directory.extend(struct.pack("<I", ifd_end + len(values_area)))
            values_area.extend(packed)
    tiles = b"".join(bytes([color]) * 256 for color in (12, 99, 188, 240))
    return (
        b"II"
        + struct.pack("<HIH", 42, 8, count)
        + directory
        + struct.pack("<I", 0)
        + values_area
        + tiles
    )


class RasterFixture(FixtureProvider):
    def __init__(self, monkeypatch):
        super().__init__(monkeypatch)
        self.tilejson = json.dumps(TILE_JSON).encode()
        self.wmts_xml = WMTS_XML
        self.tiff = fixture_tiff()
        self.range_status = "206 Partial Content"
        self.range_override: str | None = None

    def response(self, path):
        parsed = urlsplit(path)
        if parsed.path == "/tilejson.json":
            return "200 OK", "application/json", self.tilejson, ""
        if parsed.path == "/tiles/2/3/1.png":
            return "200 OK", "image/png", self.image, ""
        if parsed.path == "/wmts":
            params = parse_qs(parsed.query)
            if params["REQUEST"] == ["GetCapabilities"]:
                return "200 OK", "application/xml", self.wmts_xml, ""
            assert params == {
                "SERVICE": ["WMTS"],
                "VERSION": ["1.0.0"],
                "REQUEST": ["GetTile"],
                "LAYER": ["tiles"],
                "STYLE": ["default"],
                "FORMAT": ["image/png"],
                "TILEMATRIXSET": ["WebMercatorQuad"],
                "TILEMATRIX": ["2"],
                "TILEROW": ["1"],
                "TILECOL": ["3"],
            }
            return "200 OK", "image/png", self.image, ""
        if parsed.path == "/sample.tif":
            assert "Range: bytes=0-2097151" in self.request_headers[-1]
            extra = (
                self.range_override
                if self.range_override is not None
                else f"Content-Range: bytes 0-{len(self.tiff) - 1}/{len(self.tiff)}\r\n"
            )
            return self.range_status, "image/tiff", self.tiff, extra
        raise AssertionError("unexpected outbound destination")


@pytest.fixture
def raster(monkeypatch):
    return RasterFixture(monkeypatch)


@pytest.mark.parametrize("profile", (XYZ, WMTS))
def test_fixed_approved_tile_real_pixel_proof(raster, profile):
    assert all(
        math.isclose(a, b, abs_tol=1e-6) for a, b in zip(profile.tile.bbox, TILE_BBOX, strict=True)
    )
    out = provider_preview(profile, fetch_provider_bytes)
    assert out["availability"] == "available"
    assert out["sample"] == {"kind": profile.tile.kind, "z": 2, "x": 3, "y": 1}
    assert {key for key, active in out["capabilities"].items() if active} == {
        "metadata_read",
        "render",
    }
    with Image.open(io.BytesIO(base64.b64decode(out["image_png_base64"]))) as img:
        assert img.size == (256, 256)
        assert img.getpixel((12, 34)) == (99, 89, 79, 255)
    assert len(raster.requests) == 2


def test_tile_policy_valid_and_invalid_coordinates_bounds_origin(monkeypatch):
    monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(XYZ), asdict(WMTS), asdict(TIFF)]))
    assert load_profiles() == (XYZ, WMTS, TIFF)
    for bad in (
        replace(XYZ, bbox=(0, 0, 1, 1)),
        replace(XYZ, tile=replace(XYZ_TILE, z=1)),
        replace(XYZ, tile=replace(XYZ_TILE, template="https://other.example.org/{z}/{x}/{y}")),
        replace(XYZ, tile=replace(XYZ_TILE, template=f"https://{HOST}/{{z}}/{{x}}.png")),
        replace(WMTS, tile=replace(WMTS_TILE, matrix_set="bad?matrix")),
        replace(TIFF, tile=XYZ_TILE),
    ):
        monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(bad)]))
        assert not load_profiles()


def test_xyz_metadata_mismatch_never_requests_tile(raster):
    for meta in (
        {**TILE_JSON, "tiles": ["https://other.example.org/{z}/{x}/{y}"]},
        {**TILE_JSON, "scheme": "tms"},
        {**TILE_JSON, "maxzoom": 1},
        {**TILE_JSON, "bounds": [-90, -85, 90, 85]},
        {**TILE_JSON, "attribution": "unexpected rights"},
    ):
        raster.tilejson = json.dumps(meta).encode()
        before = len(raster.requests)
        with pytest.raises(ProviderUnavailable):
            provider_preview(XYZ, fetch_provider_bytes)
        assert len(raster.requests) == before + 1


def test_wmts_metadata_wrong_matrix_crs_scale_or_limits_denied(raster):
    for bad in (
        WMTS_XML.replace(b"EPSG::3857", b"EPSG::4326"),
        WMTS_XML.replace(b"<MatrixWidth>4", b"<MatrixWidth>2"),
        WMTS_XML.replace(str(SCALE).encode(), b"1234"),
        WMTS_XML.replace(b"<MaxTileCol>3", b"<MaxTileCol>2"),
        WMTS_XML.replace(b"<ows:Value>KVP", b"<ows:Value>REST"),
        WMTS_XML.replace(b"image/png", b"image/jpeg"),
    ):
        raster.wmts_xml = bad
        before = len(raster.requests)
        with pytest.raises(ProviderUnavailable):
            provider_preview(WMTS, fetch_provider_bytes)
        assert len(raster.requests) == before + 1


def test_tiled_geotiff_real_range_pixels_and_georeference(raster):
    # Independent TIFF decoder confirms our hand-built fixture and pixel oracle.
    with Image.open(io.BytesIO(raster.tiff)) as original:
        assert original.size == (32, 32)
        assert [original.getpixel(p) for p in ((1, 1), (17, 1), (1, 17), (17, 17))] == [
            12,
            99,
            188,
            240,
        ]
    out = provider_preview(TIFF, fetch_provider_bytes)
    assert out["bbox"] == TIFF_BBOX and out["crs"] == 4326
    assert out["sample"] == {
        "kind": "geotiff_range_sample",
        "tile_width": 16,
        "tile_height": 16,
        "tile_count": 4,
        "pixel_size": [1 / 32, 1 / 32],
        "band_count": 1,
        "range_bytes": len(raster.tiff),
    }
    assert out["capabilities"]["render"] and not out["capabilities"]["query"]
    with Image.open(io.BytesIO(base64.b64decode(out["image_png_base64"]))) as img:
        assert [img.getpixel(p) for p in ((1, 1), (17, 1), (1, 17), (17, 17))] == [
            (v, v, v, 255) for v in (12, 99, 188, 240)
        ]
    assert raster.requests == ["/sample.tif"]


def test_tiff_wrong_range_response_and_large_source_denied(raster):
    raster.range_status = "200 OK"
    with pytest.raises(ProviderUnavailable):
        provider_preview(TIFF, fetch_provider_bytes)
    raster.range_status = "206 Partial Content"
    for header in (
        "",
        "Content-Range: bytes 0-99/*\r\n",
        "Content-Range: bytes 0-99/100\r\n",
        f"Content-Range: bytes 0-{len(raster.tiff) - 1}/99999999\r\n",
        f"Content-Range: bytes 1-{len(raster.tiff)}/{len(raster.tiff)}\r\n",
    ):
        raster.range_override = header
        with pytest.raises(ProviderUnavailable):
            provider_preview(TIFF, fetch_provider_bytes)


def test_tiff_bad_crs_georeference_offsets_compression_or_payload_denied(raster):
    for payload in (
        fixture_tiff(epsg=3857),
        fixture_tiff(compression=8),
        fixture_tiff(bad_offset=True),
        fixture_tiff()[:-1],
        fixture_tiff() + b"trailing",
        png(),
    ):
        raster.tiff = payload
        with pytest.raises(ProviderUnavailable):
            provider_preview(TIFF, fetch_provider_bytes)
    raster.tiff = fixture_tiff()
    with pytest.raises(ProviderUnavailable):
        provider_preview(replace(TIFF, bbox=(105.5, 20.5, 106.6, 21.5)), fetch_provider_bytes)
