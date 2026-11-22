"""Independent compressed TIFF/pixel and real HTTP-range oracles, no external network."""

from __future__ import annotations

import base64
import io
import json
import random
import re
import shutil
import struct
import subprocess
import zlib
from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from PIL import Image

from openvietgis_api.adapters.http.external_provider_transport import (
    fetch_provider_bytes,
    fetch_provider_range,
)
from openvietgis_api.domains.external_sources.cog_provider import PREFIX_LIMIT
from openvietgis_api.domains.external_sources.domain import ExternalProtocol
from openvietgis_api.domains.external_sources.provider import (
    PROFILE_ENV,
    CogProfile,
    ProviderProfile,
    ProviderUnavailable,
    load_profiles,
    provider_preview,
    provider_viewport,
)
from openvietgis_api.domains.platform_errors import PlatformForbiddenError, PlatformValidationError
from tests.unit.test_external_provider import ATTRIBUTION, HOST, RIGHTS, FixtureProvider

BBOX = (105.0, 20.0, 106.0, 21.0)
PROFILE = ProviderProfile(
    f"https://{HOST}/cog.tif",
    ExternalProtocol.COG_GEOTIFF,
    "raster",
    4326,
    BBOX,
    ATTRIBUTION,
    RIGHTS,
    cog=CogProfile(BBOX, 1024, 1024, True),
)
CROP = (105.0, 20.875, 105.125, 21.0)
TILE_SIZE = 128


def _pack(kind, values):
    return struct.pack("<" + {3: "H", 4: "I", 12: "d"}[kind] * len(values), *values)


def manual_cog(*, bad_offset=False, wrong_crs=False, bomb=False):
    """Hand-built classic tiled Deflate TIFF with two actual reduced-image IFDs."""
    widths = [1024, 512, 256]
    base = random.Random(314159).randbytes(1024 * 1024)
    planes = [
        bytes(base[y * factor * 1024 + x * factor] for y in range(w) for x in range(w))
        for w, factor in zip(widths, (1, 2, 4), strict=True)
    ]
    tags = []
    blocks = []
    for level, (w, pixels) in enumerate(zip(widths, planes, strict=True)):
        tile_blocks = []
        for tile_y in range(0, w, TILE_SIZE):
            for tile_x in range(0, w, TILE_SIZE):
                encoded = bytearray()
                for iy in range(tile_y, tile_y + TILE_SIZE):
                    line = pixels[iy * w + tile_x : iy * w + tile_x + TILE_SIZE]
                    encoded.append(line[0])
                    encoded.extend((line[i] - line[i - 1]) & 255 for i in range(1, TILE_SIZE))
                if bomb and level == 0 and tile_x == 0 and tile_y == 0:
                    encoded = bytearray(b"x" * (TILE_SIZE**2 + 1))
                tile_blocks.append(zlib.compress(encoded))
        blocks.append(tile_blocks)
        d = {
            256: (4, (w,)),
            257: (4, (w,)),
            258: (3, (8,)),
            259: (3, (8,)),
            262: (3, (1,)),
            277: (3, (1,)),
            284: (3, (1,)),
            317: (3, (2,)),
            322: (4, (TILE_SIZE,)),
            323: (4, (TILE_SIZE,)),
            324: (4, (0,) * len(tile_blocks)),
            325: (4, tuple(map(len, tile_blocks))),
            339: (3, (1,)),
        }
        if level:
            d[254] = (4, (1,))
        else:
            d.update(
                {
                    33550: (12, (1 / 1024, 1 / 1024, 0)),
                    33922: (12, (0, 0, 0, 105, 21, 0)),
                    34735: (
                        3,
                        (
                            1,
                            1,
                            0,
                            3,
                            1024,
                            0,
                            1,
                            2,
                            1025,
                            0,
                            1,
                            1,
                            2048,
                            0,
                            1,
                            3857 if wrong_crs else 4326,
                        ),
                    ),
                }
            )
        tags.append(d)
    ifd_offsets = []
    pos = 8
    for d in tags:
        ifd_offsets.append(pos)
        pos += 2 + 12 * len(d) + 4
    ifd_end = pos
    for d in tags:
        for kind, values in d.values():
            packed = _pack(kind, values)
            if len(packed) > 4:
                pos += len(packed)
    tile_start = pos
    for level in reversed(range(len(tags))):
        offsets = []
        for block in blocks[level]:
            offsets.append(pos)
            pos += len(block)
        if bad_offset and level == 0:
            offsets[0] = 8
        tags[level][324] = (4, tuple(offsets))
    directories, meta = bytearray(), bytearray()
    for level, d in enumerate(tags):
        directories.extend(struct.pack("<H", len(d)))
        for tag, (kind, values) in sorted(d.items()):
            data = _pack(kind, values)
            directories.extend(struct.pack("<HHI", tag, kind, len(values)))
            if len(data) <= 4:
                directories.extend(data.ljust(4, b"\0"))
            else:
                directories.extend(struct.pack("<I", ifd_end + len(meta)))
                meta.extend(data)
        next_ifd = ifd_offsets[level + 1] if level + 1 < len(tags) else 0
        directories.extend(struct.pack("<I", next_ifd))
    header = b"II" + struct.pack("<HI", 42, 8)
    assert len(header + directories + meta) == tile_start
    raw = (
        header
        + directories
        + meta
        + b"".join(block for level in reversed(blocks) for block in level)
    )
    return raw, planes


class CogFixture(FixtureProvider):
    def __init__(self, monkeypatch, raw):
        super().__init__(monkeypatch)
        self.raw = raw
        self.ranges: list[tuple[int, int]] = []
        self.status = "206 Partial Content"
        self.first_etag = '"fixture-v1"'
        self.next_etag = '"fixture-v1"'
        self.range_override: str | None = None
        self.total_delta = 0
        self.truncate = False

    def response(self, path):
        assert urlsplit(path).path == "/cog.tif"
        assert not urlsplit(path).query
        headers = self.request_headers[-1]
        match = next(
            re.fullmatch(r"Range: bytes=(\d+)-(\d+)", h) for h in headers if h.startswith("Range:")
        )
        assert match is not None
        first, requested_last = map(int, match.groups())
        actual_last = min(requested_last, len(self.raw) - 1)
        subsequent = bool(self.ranges)
        if subsequent:
            assert f"If-Match: {self.first_etag}" in headers
        else:
            assert not any(h.startswith("If-Match:") for h in headers)
        self.ranges.append((first, actual_last))
        payload = self.raw[first : actual_last + 1]
        if self.truncate:
            payload = payload[:-1]
        total = len(self.raw) + (self.total_delta if subsequent else 0)
        etag = self.next_etag if subsequent else self.first_etag
        content_range = self.range_override or f"bytes {first}-{actual_last}/{total}"
        extra = f"Content-Range: {content_range}\r\nETag: {etag}\r\n"
        return self.status, "image/tiff", payload, extra


@pytest.fixture(scope="module")
def fixture_bytes():
    return manual_cog()


def _gray(result):
    with Image.open(io.BytesIO(base64.b64decode(result["image_png_base64"]))) as out:
        return out.size, out.convert("L").tobytes()


def test_actual_cog_overview_and_native_window_pixels(monkeypatch, fixture_bytes):
    raw, planes = fixture_bytes
    # Verify hand-built TIFF itself using Pillow's independent TIFF decoder.
    with Image.open(io.BytesIO(raw)) as independent:
        assert independent.size == (1024, 1024)
        assert independent.tobytes() == planes[0]
        independent.seek(2)
        assert independent.size == (256, 256)
        assert independent.tobytes() == planes[2]
    fixture = CogFixture(monkeypatch, raw)
    result = provider_preview(PROFILE, fetch_provider_bytes, fetch_provider_range)
    assert result["availability"] == "available"
    assert result["capabilities"]["render"] and not result["capabilities"]["query"]
    assert result["sample"]["overview_index"] == 2
    assert result["sample"]["overview_scale"] == 4
    assert result["sample"]["compression"] == "deflate"
    assert result["sample"]["predictor"] == 2
    assert _gray(result) == ((256, 256), planes[2])
    assert result["sample"]["source_pixel_window"] == [0, 0, 1024, 1024]
    assert result["sample"]["range_bytes"] < len(raw) // 4
    assert result["sample"]["range_requests"] == len(fixture.ranges)
    assert fixture.ranges[0] == (0, PREFIX_LIMIT - 1)
    fixture.ranges.clear()
    crop = provider_viewport(
        PROFILE, fetch_provider_range, crs=4326, bbox=CROP, width=128, height=128
    )
    oracle = b"".join(planes[0][y * 1024 : y * 1024 + 128] for y in range(128))
    assert _gray(crop) == ((128, 128), oracle)
    assert crop["scope"] == "operator_approved_viewport"
    assert crop["sample"]["overview_index"] == 0
    assert crop["sample"]["tile_count"] == 1
    assert crop["sample"]["source_pixel_window"] == [0, 0, 128, 128]
    assert len(fixture.ranges) == 2
    assert fixture.ranges[-1][0] > PREFIX_LIMIT
    assert crop["sample"]["range_bytes"] < len(raw) // 4


def test_profile_and_viewport_default_deny_no_egress(monkeypatch, fixture_bytes):
    raw, _ = fixture_bytes
    fixture = CogFixture(monkeypatch, raw)
    monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(PROFILE)]))
    assert load_profiles() == (PROFILE,)
    for invalid in (
        replace(PROFILE, bbox=(104, 20, 106, 21)),
        replace(PROFILE, cog=replace(PROFILE.cog, source_width=0)),
        replace(PROFILE, protocol=ExternalProtocol.WMS),
    ):
        monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(invalid)]))
        assert not load_profiles()
    with pytest.raises(PlatformForbiddenError):
        provider_viewport(
            PROFILE, fetch_provider_range, crs=4326, bbox=(104, 20, 106, 21), width=128, height=128
        )
    with pytest.raises(PlatformForbiddenError):
        provider_viewport(
            replace(PROFILE, cog=replace(PROFILE.cog, allow_viewport=False)),
            fetch_provider_range,
            crs=4326,
            bbox=CROP,
            width=128,
            height=128,
        )
    with pytest.raises(PlatformForbiddenError):
        provider_viewport(
            replace(PROFILE, cog=None),
            fetch_provider_range,
            crs=4326,
            bbox=CROP,
            width=128,
            height=128,
        )
    with pytest.raises(PlatformValidationError):
        provider_viewport(PROFILE, fetch_provider_range, crs=3857, bbox=CROP, width=128, height=128)
    with pytest.raises(PlatformValidationError):
        provider_viewport(PROFILE, fetch_provider_range, crs=4326, bbox=CROP, width=513, height=128)
    assert not fixture.requests


@pytest.mark.parametrize(
    "condition",
    [
        "weak_etag",
        "changed_etag",
        "changed_size",
        "unknown_range",
        "wrong_range",
        "range_ignored",
        "truncated",
    ],
)
def test_bad_range_or_version_denied(monkeypatch, fixture_bytes, condition):
    fixture = CogFixture(monkeypatch, fixture_bytes[0])
    if condition == "weak_etag":
        fixture.first_etag = 'W/"weak"'
    elif condition == "changed_etag":
        fixture.next_etag = '"fixture-v2"'
    elif condition == "changed_size":
        fixture.total_delta = 1
    elif condition == "unknown_range":
        fixture.range_override = "bytes 0-65535/*"
    elif condition == "wrong_range":
        fixture.range_override = "bytes 1-65536/1000000"
    elif condition == "range_ignored":
        fixture.status = "200 OK"
    elif condition == "truncated":
        fixture.truncate = True
    with pytest.raises(ProviderUnavailable):
        provider_viewport(PROFILE, fetch_provider_range, crs=4326, bbox=CROP, width=128, height=128)


@pytest.mark.parametrize("variant", ["wrong_crs", "bad_offset", "bomb"])
def test_invalid_cog_directory_georeference_and_decompression_denied(monkeypatch, variant):
    raw, _ = manual_cog(**{variant: True})
    fixture = CogFixture(monkeypatch, raw)
    with pytest.raises(ProviderUnavailable):
        provider_viewport(PROFILE, fetch_provider_range, crs=4326, bbox=CROP, width=128, height=128)
    if variant != "bomb":
        assert len(fixture.ranges) == 1


def test_bounds_valid_but_excessive_tile_budget_denied(monkeypatch, fixture_bytes):
    fixture = CogFixture(monkeypatch, fixture_bytes[0])
    with pytest.raises(ProviderUnavailable):
        provider_viewport(
            PROFILE,
            fetch_provider_range,
            crs=4326,
            bbox=(105.05, 20.05, 105.95, 20.95),
            width=512,
            height=512,
        )
    assert len(fixture.ranges) == 1


@pytest.mark.skipif(not shutil.which("gdalinfo"), reason="independent GDAL CLI unavailable")
@pytest.mark.parametrize("crs,channels", [(4326, 1), (3857, 3)])
def test_real_gdal_cog_generator_and_independent_pixel_oracle(
    monkeypatch, tmp_path: Path, crs, channels
):
    system_python = Path("/usr/bin/python3")
    if not system_python.is_file():
        pytest.skip("GDAL Python unavailable")
    probe = subprocess.run(
        [str(system_python), "-c", "import osgeo.gdal, numpy"], capture_output=True
    )
    if probe.returncode:
        pytest.skip("GDAL Python unavailable")
    script = """
from osgeo import gdal, osr
import numpy as np
from pathlib import Path
import sys
root = Path(sys.argv[1])
crs, channels = map(int, sys.argv[2:])
src = gdal.GetDriverByName("MEM").Create("", 1024, 1024, channels, gdal.GDT_Byte)
srs = osr.SpatialReference()
srs.ImportFromEPSG(crs)
src.SetProjection(srs.ExportToWkt())
src.SetGeoTransform(
    (105, 1/1024, 0, 21, 0, -1/1024) if crs == 4326 else (1000000, 1, 0, 2000000, 0, -1)
)
rng = np.random.default_rng(42)
for i in range(channels):
    a = rng.integers(0, 256, (1024, 1024), dtype=np.uint8)
    band = src.GetRasterBand(i+1)
    band.WriteArray(a)
    colors = (gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand)
    band.SetColorInterpretation(gdal.GCI_GrayIndex if channels == 1 else colors[i])
out = gdal.Translate(str(root / "real.tif"), src, format="COG", creationOptions=[
    "BLOCKSIZE=128", "COMPRESS=DEFLATE", "PREDICTOR=YES", "OVERVIEW_COUNT=2", "RESAMPLING=NEAREST"
])
out = None
obj = gdal.Open(str(root / "real.tif"))
assert obj.GetMetadata("IMAGE_STRUCTURE")["LAYOUT"] == "COG"
assert obj.GetRasterBand(1).GetOverviewCount() == 2
overview = np.stack(
    [obj.GetRasterBand(i+1).GetOverview(1).ReadAsArray() for i in range(channels)], axis=-1
)
window = np.stack(
    [obj.GetRasterBand(i+1).ReadAsArray(0, 0, 128, 128) for i in range(channels)], axis=-1
)
(root / "overview.raw").write_bytes(overview.tobytes())
(root / "window.raw").write_bytes(window.tobytes())
"""
    subprocess.run(
        [str(system_python), "-c", script, str(tmp_path), str(crs), str(channels)],
        check=True,
        capture_output=True,
        timeout=25,
    )
    raw = (tmp_path / "real.tif").read_bytes()
    fixture = CogFixture(monkeypatch, raw)
    bounds = BBOX if crs == 4326 else (1000000, 1998976, 1001024, 2000000)
    window = CROP if crs == 4326 else (1000000, 1999872, 1000128, 2000000)
    profile = replace(PROFILE, crs=crs, bbox=bounds, cog=CogProfile(bounds, 1024, 1024, True))

    def pixels(result):
        with Image.open(io.BytesIO(base64.b64decode(result["image_png_base64"]))) as out:
            return out.size, out.convert("L" if channels == 1 else "RGB").tobytes()

    sample = provider_preview(profile, fetch_provider_bytes, fetch_provider_range)
    assert pixels(sample) == ((256, 256), (tmp_path / "overview.raw").read_bytes())
    assert sample["sample"]["overview_index"] == 2
    assert sample["sample"]["range_bytes"] < len(raw) // 10
    fixture.ranges.clear()
    crop = provider_viewport(
        profile, fetch_provider_range, crs=crs, bbox=window, width=128, height=128
    )
    assert pixels(crop) == ((128, 128), (tmp_path / "window.raw").read_bytes())
    assert crop["sample"]["tile_count"] == 1
    assert crop["sample"]["range_requests"] == 2
    assert crop["sample"]["range_bytes"] < len(raw) // 10
