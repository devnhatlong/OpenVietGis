"""Strict bounded COG pyramid and window decoder over immutable HTTP ranges.

Supports classic TIFF, north-up pixel-area EPSG:4326/3857, uint8 contiguous
gray/RGB, uncompressed/zlib Deflate and horizontal Predictor 2. Only approved
output regions and selected tile offsets are requested; no external CRS
transforms or arbitrary provider URL or bbox forwarding.
"""

from __future__ import annotations

import base64
import io
import math
import re
import struct
import time
import zlib
from dataclasses import dataclass
from typing import Any, Literal

from PIL import Image

from openvietgis_api.domains.external_sources.provider import (
    BBox,
    ProviderProfile,
    ProviderUnavailable,
    RangeFetch,
    _bbox,
    _contains,
    _near_bbox,
)
from openvietgis_api.domains.platform_errors import PlatformForbiddenError, PlatformValidationError

PREFIX_LIMIT = 64 * 1024
MAX_RANGES = 17  # one metadata range plus <=16 data tiles
MAX_BYTES = 4 * 1024 * 1024
MAX_TILE_COMPRESSED = 1024 * 1024
MAX_TILES_IN_METADATA = 4096
MAX_LEVELS = 6
MAX_OUTPUT = 512
MAX_OBJECT = 2**31
TOTAL_SECONDS = 15.0


class _Reader:
    def __init__(self, url: str, fetch: RangeFetch) -> None:
        self.url = url
        self.fetch = fetch
        self.deadline = time.monotonic() + TOTAL_SECONDS
        self.requests = 0
        self.bytes = 0
        self.etag: str | None = None
        self.total: int | None = None
        self.prefix = self._range(0, PREFIX_LIMIT - 1)

    def _range(self, first: int, last: int) -> bytes:
        remaining = self.deadline - time.monotonic()
        if (
            remaining <= 0
            or self.requests >= MAX_RANGES
            or not 0 <= first <= last < MAX_OBJECT
            or self.bytes + last - first + 1 > MAX_BYTES
        ):
            raise ValueError("COG request budget exceeded")
        response = self.fetch(self.url, first, last, self.etag, self.total, min(5.0, remaining))
        if (
            not 0 < response.total <= MAX_OBJECT
            or re.fullmatch(r'"[\x21\x23-\x7e]{1,128}"', response.etag) is None
            or (self.etag is not None and response.etag != self.etag)
            or (self.total is not None and response.total != self.total)
            or len(response.data) != min(last, response.total - 1) - first + 1
            or not response.data
            or time.monotonic() >= self.deadline
        ):
            raise ValueError("COG object version or range length changed")
        self.etag, self.total = response.etag, response.total
        self.requests += 1
        self.bytes += len(response.data)
        return response.data

    def tile(self, offset: int, length: int) -> bytes:
        if self.total is None or not 0 < length <= MAX_TILE_COMPRESSED:
            raise ValueError("invalid range length")
        if not 0 <= offset <= self.total - length:
            raise ValueError("invalid tile range")
        if offset + length <= len(self.prefix):
            return self.prefix[offset : offset + length]
        return self._range(offset, offset + length - 1)


Number = int | float
Tag = tuple[Number, ...] | bytes
Tags = dict[int, Tag]
_REQUIRED = {256, 257, 258, 259, 262, 277, 284, 322, 323, 324, 325}
_GEO = {33550, 33922, 34735}
_OPTIONAL = {254, 270, 274, 305, 306, 317, 330, 339, 34736, 34737, 42112} | _GEO
_NUMERIC_TYPES = {3: ("H", 2), 4: ("I", 4), 12: ("d", 8)}
_ASCII_TAGS = {270, 305, 306, 34737, 42112}


@dataclass(frozen=True, slots=True)
class _Level:
    width: int
    height: int
    tw: int
    th: int
    channels: int
    mode: Literal["L", "RGB"]
    compression: int
    predictor: int
    offsets: tuple[int, ...]
    lengths: tuple[int, ...]
    tags: Tags

    @property
    def cols(self) -> int:
        return math.ceil(self.width / self.tw)


def _ints(tags: Tags, tag: int) -> tuple[int, ...]:
    values = tags.get(tag)
    if not isinstance(values, tuple) or any(type(value) is not int for value in values):
        raise ValueError("invalid integer TIFF tag")
    return tuple(int(value) for value in values)


def _scalar(tags: Tags, tag: int, default: int | None = None) -> int:
    if tag not in tags and default is not None:
        return default
    values = _ints(tags, tag)
    if len(values) != 1:
        raise ValueError("invalid scalar TIFF tag")
    return values[0]


def _numbers(tags: Tags, tag: int) -> tuple[Number, ...]:
    values = tags.get(tag)
    if not isinstance(values, tuple) or not all(math.isfinite(value) for value in values):
        raise ValueError("invalid numeric TIFF tag")
    return values


def _interval(intervals: list[tuple[int, int]], first: int, last: int) -> None:
    if any(first < right and left < last for left, right in intervals):
        raise ValueError("overlapping TIFF metadata")
    intervals.append((first, last))


def _directory(
    raw: bytes, endian: str, offset: int, intervals: list[tuple[int, int]]
) -> tuple[Tags, int]:
    if not 8 <= offset <= len(raw) - 2:
        raise ValueError("directory not in bounded metadata prefix")
    count = struct.unpack_from(endian + "H", raw, offset)[0]
    end = offset + 2 + count * 12 + 4
    if not len(_REQUIRED) <= count <= len(_REQUIRED | _OPTIONAL) or end > len(raw):
        raise ValueError("invalid TIFF directory")
    _interval(intervals, offset, end)
    tags: Tags = {}
    for index in range(count):
        pos = offset + 2 + 12 * index
        tag, kind, n = struct.unpack_from(endian + "HHI", raw, pos)
        if tag not in _REQUIRED | _OPTIONAL or tag in tags or not 1 <= n <= MAX_TILES_IN_METADATA:
            raise ValueError("unsupported TIFF tag")
        if kind == 2:
            if tag not in _ASCII_TAGS or n > 4096:
                raise ValueError("unexpected TIFF text field")
            size = n
        else:
            if tag in _ASCII_TAGS or kind not in _NUMERIC_TYPES:
                raise ValueError("invalid TIFF tag representation")
            if (tag in (33550, 33922, 34736)) != (kind == 12):
                raise ValueError("invalid TIFF numeric representation")
            if tag == 34735 and kind != 3:
                raise ValueError("invalid geokey type")
            if kind == 12 and n > 32:
                raise ValueError("invalid georeference length")
            fmt, width = _NUMERIC_TYPES[kind]
            size = n * width
        if size <= 4:
            value_offset = pos + 8
        else:
            value_offset = struct.unpack_from(endian + "I", raw, pos + 8)[0]
            if not 8 <= value_offset <= len(raw) - size:
                raise ValueError("metadata outside bounded prefix")
            _interval(intervals, value_offset, value_offset + size)
        if kind == 2:
            value = raw[value_offset : value_offset + size]
            if not value.isascii() or b"\x00" in value[:-1]:
                raise ValueError("invalid TIFF text metadata")
            tags[tag] = value
        else:
            tags[tag] = struct.unpack_from(endian + fmt * n, raw, value_offset)
    if not _REQUIRED <= tags.keys():
        raise ValueError("required tiled fields absent")
    return tags, struct.unpack_from(endian + "I", raw, end - 4)[0]


def _level(tags: Tags) -> _Level:
    width, height = _scalar(tags, 256), _scalar(tags, 257)
    tw, th = _scalar(tags, 322), _scalar(tags, 323)
    channels, photo = _scalar(tags, 277), _scalar(tags, 262)
    if channels == 1 and photo == 1:
        mode: Literal["L", "RGB"] = "L"
    elif channels == 3 and photo == 2:
        mode = "RGB"
    else:
        raise ValueError("unsupported band/photometric layout")
    compression, predictor = _scalar(tags, 259), _scalar(tags, 317, 1)
    if (
        not 1 <= width <= 32768
        or not 1 <= height <= 32768
        or not 16 <= tw <= 512
        or not 16 <= th <= 512
        or tw % 16
        or th % 16
        or _ints(tags, 258) != (8,) * channels
        or compression not in (1, 8, 32946)
        or predictor not in (1, 2)
        or (compression == 1 and predictor != 1)
        or _scalar(tags, 284) != 1
        or _scalar(tags, 274, 1) != 1
        or (339 in tags and _ints(tags, 339) != (1,) * channels)
    ):
        raise ValueError("unsupported classic tiled uint8 profile")
    offsets, lengths = _ints(tags, 324), _ints(tags, 325)
    n = math.ceil(width / tw) * math.ceil(height / th)
    if n > MAX_TILES_IN_METADATA or len(offsets) != n or len(lengths) != n:
        raise ValueError("inconsistent TIFF tile count")
    return _Level(
        width, height, tw, th, channels, mode, compression, predictor, offsets, lengths, tags
    )


def _georeference(level: _Level, crs: int) -> BBox:
    tags = level.tags
    scale, tie = _numbers(tags, 33550), _numbers(tags, 33922)
    if (
        len(scale) != 3
        or len(tie) != 6
        or not scale[0] > 0
        or not scale[1] > 0
        or scale[2] != 0
        or tie[:3] != (0, 0, 0)
        or tie[5] != 0
    ):
        raise ValueError("only north-up pixel-area raster allowed")
    keys = _ints(tags, 34735)
    if not 4 <= len(keys) <= 128 or keys[:3] != (1, 1, 0) or len(keys) != 4 + 4 * keys[3]:
        raise ValueError("invalid geokey directory")
    actual: dict[int, int] = {}
    seen: set[int] = set()
    for i in range(4, len(keys), 4):
        key, location, count, index = keys[i : i + 4]
        if key in seen or count <= 0:
            raise ValueError("duplicate/invalid geokey")
        seen.add(key)
        if location == 0 and count == 1:
            actual[key] = index
        elif location == 34737 and key in (1026, 2049, 3073):
            # Citations are bounded ignored labels; do not read external references.
            strings = tags.get(34737)
            if not isinstance(strings, bytes) or not 0 <= index <= len(strings) - count:
                raise ValueError("invalid citation")
        elif location == 34736 and count == 1 and key in (2057, 2059):
            values = _numbers(tags, 34736)
            expected = 6378137.0 if key == 2057 else 298.257223563
            if not 0 <= index < len(values) or not math.isclose(
                values[index], expected, rel_tol=1e-12
            ):
                raise ValueError("unsupported ellipsoid")
        else:
            raise ValueError("unsupported geokey")
    required = (
        {1024: 2, 1025: 1, 2048: 4326}
        if crs == 4326
        else {
            1024: 1,
            1025: 1,
            3072: 3857,
        }
    )
    optional = {2054: 9102, 2050: 6326, 2056: 7030}
    if crs == 3857:
        optional.update({2048: 4326, 3076: 9001})
    if not all(actual.get(k) == v for k, v in required.items()) or any(
        k not in required and optional.get(k) != v for k, v in actual.items()
    ):
        raise ValueError("invalid CRS, datum, units or raster type")
    return _bbox(
        [tie[3], tie[4] - level.height * scale[1], tie[3] + level.width * scale[0], tie[4]],
        crs,
    )


def _pyramid(reader: _Reader, profile: ProviderProfile) -> list[_Level]:
    raw = reader.prefix
    total = reader.total
    config = profile.cog
    if total is None or config is None or len(raw) < 8:
        raise ValueError("missing COG metadata")
    if raw[:2] == b"II":
        endian = "<"
    elif raw[:2] == b"MM":
        endian = ">"
    else:
        raise ValueError("invalid TIFF byte order")
    version, first = struct.unpack_from(endian + "HI", raw, 2)
    if version != 42 or not 8 <= first <= 4096:
        raise ValueError("unsupported TIFF header")
    if b"KNOWN_INCOMPATIBLE_EDITION=YES" in raw[:first]:
        raise ValueError("incompatible COG structural marker")
    intervals = [(0, first)]
    todo = [first]
    seen: set[int] = set()
    levels: list[_Level] = []
    while todo:
        offset = todo.pop(0)
        if offset in seen or len(seen) >= MAX_LEVELS:
            raise ValueError("cyclic or oversized overview directory chain")
        seen.add(offset)
        tags, subsequent = _directory(raw, endian, offset, intervals)
        levels.append(_level(tags))
        if subsequent:
            todo.append(subsequent)
        if 330 in tags:
            todo.extend(_ints(tags, 330))
    if not levels:
        raise ValueError("missing COG image")
    # Base directory is first; all overview directories are explicitly reduced
    # image subfiles, no mask pages or a second full-resolution image.
    base = levels[0]
    if (
        _scalar(base.tags, 254, 0) != 0
        or (base.width, base.height) != (config.source_width, config.source_height)
        or not _near_bbox(_georeference(base, profile.crs), config.source_bbox)
    ):
        raise ValueError("source georeference or size mismatch")
    levels.sort(key=lambda level: -level.width)
    if levels[0] != base:
        raise ValueError("base directory not full resolution")
    last_factor = 0
    metadata_end = max(right for _, right in intervals)
    tiles_so_far = 0
    for level in levels:
        if level.mode != base.mode or base.width % level.width or base.height % level.height:
            raise ValueError("incompatible reduced resolution")
        factor = base.width // level.width
        if (
            factor != base.height // level.height
            or factor <= last_factor
            or factor & (factor - 1) != 0
            or (factor > 1 and _scalar(level.tags, 254, 0) != 1)
        ):
            raise ValueError("invalid overview pyramid")
        last_factor = factor
        if level is not base and (_GEO | {34736, 34737}) & level.tags.keys():
            if not _GEO <= level.tags.keys() or not _near_bbox(
                _georeference(level, profile.crs), config.source_bbox
            ):
                raise ValueError("overview georeference mismatch")
        tiles_so_far += len(level.offsets)
        if tiles_so_far > MAX_TILES_IN_METADATA:
            raise ValueError("excessive tile metadata")
    # Actual COG layout: smallest overview data first, monotonically
    # row-major; metadata before every tile, no overlaps/strips/masks.
    last = metadata_end
    for level in reversed(levels):
        for offset, length in zip(level.offsets, level.lengths, strict=True):
            if (
                offset < last
                or not 0 < length <= MAX_TILE_COMPRESSED
                or offset + length > total
                or (level.compression == 1 and length != level.tw * level.th * level.channels)
            ):
                raise ValueError("not a range-safe COG tile layout")
            last = offset + length
    return levels


def _decode_tile(data: bytes, level: _Level) -> bytes:
    size = level.tw * level.th * level.channels
    if level.compression == 1:
        pixels = data
    else:
        # Bound decompression by the exact expected expanded tile dimensions.
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(data, size + 1)
        if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise ValueError("invalid Deflate tile")
    if len(pixels) != size:
        raise ValueError("expanded TIFF tile size mismatch")
    if level.predictor == 2:
        decoded = bytearray(pixels)
        stride, channels = level.tw * level.channels, level.channels
        for start in range(0, size, stride):
            for pos in range(start + channels, start + stride):
                decoded[pos] = (decoded[pos] + decoded[pos - channels]) & 255
        return bytes(decoded)
    return pixels


def _indices(
    minimum: float,
    maximum: float,
    origin: float,
    scale: float,
    size: int,
    n: int,
    *,
    north: bool = False,
) -> list[int]:
    step = (maximum - minimum) / n
    coordinates = [
        (maximum - (idx + 0.5) * step) if north else (minimum + (idx + 0.5) * step)
        for idx in range(n)
    ]
    # Pixel-center nearest sample; BBOX is already strictly contained, only
    # floating-point arithmetic at the outermost boundary can need clamping.
    return [
        min(size - 1, max(0, math.floor((origin - value if north else value - origin) / scale)))
        for value in coordinates
    ]


def cog_preview(
    profile: ProviderProfile, range_fetch: RangeFetch, bbox: BBox, width: int, height: int
) -> dict[str, Any]:
    """Select an appropriate overview, request intersecting tiles, and sample actual pixels."""
    if profile.cog is None:
        raise PlatformForbiddenError("COG viewport not approved", code="PROVIDER_DISABLED")
    try:
        viewport = _bbox(bbox, profile.crs)
    except (ValueError, TypeError, OverflowError) as exc:
        raise PlatformValidationError("invalid viewport bounds", code="INVALID_VIEWPORT") from exc
    if not _contains(profile.bbox, viewport):
        raise PlatformForbiddenError("viewport outside approved bounds", code="VIEWPORT_FORBIDDEN")
    if not (
        type(width) is int
        and type(height) is int
        and 1 <= width <= MAX_OUTPUT
        and 1 <= height <= MAX_OUTPUT
    ):
        raise PlatformValidationError("unsupported viewport dimensions", code="INVALID_VIEWPORT")
    try:
        reader = _Reader(profile.endpoint, range_fetch)
        levels = _pyramid(reader, profile)
        a, b, c, d = profile.cog.source_bbox
        x0, y0, x1, y1 = viewport
        desired_x, desired_y = (x1 - x0) / width, (y1 - y0) / height
        level_index = 0
        for i, candidate in enumerate(levels):
            # Choose coarsest native resolution no coarser than requested.
            if (c - a) / candidate.width <= desired_x * (1 + 1e-10) and (
                d - b
            ) / candidate.height <= desired_y * (1 + 1e-10):
                level_index = i
        level = levels[level_index]
        dx, dy = (c - a) / level.width, (d - b) / level.height
        xs = _indices(x0, x1, a, dx, level.width, width)
        ys = _indices(y0, y1, d, dy, level.height, height, north=True)
        ids = sorted(
            {
                row * level.cols + col
                for row in {y // level.th for y in ys}
                for col in {x // level.tw for x in xs}
            }
        )
        if len(ids) > MAX_RANGES - 1:
            raise ValueError("viewport exceeds tile budget")
        tiles = {
            i: _decode_tile(reader.tile(level.offsets[i], level.lengths[i]), level) for i in ids
        }
        if time.monotonic() >= reader.deadline:
            raise ValueError("COG deadline exceeded")
        pixels = bytearray(width * height * level.channels)
        for row, y in enumerate(ys):
            for col, x in enumerate(xs):
                tile = tiles[(y // level.th) * level.cols + x // level.tw]
                address = ((y % level.th) * level.tw + x % level.tw) * level.channels
                target = (row * width + col) * level.channels
                pixels[target : target + level.channels] = tile[address : address + level.channels]
        image = Image.frombytes(level.mode, (width, height), bytes(pixels))
        output = io.BytesIO()
        image.convert("RGBA").save(output, format="PNG")
        if time.monotonic() >= reader.deadline:
            raise ValueError("COG deadline exceeded")
        return {
            "image_png_base64": base64.b64encode(output.getvalue()).decode("ascii"),
            "width": width,
            "height": height,
            "sample": {
                "kind": "cog_window_sample",
                "tile_width": level.tw,
                "tile_height": level.th,
                "tile_count": len(ids),
                "band_count": level.channels,
                "overview_index": level_index,
                "overview_scale": levels[0].width // level.width,
                "overview_count": len(levels) - 1,
                "source_size": [levels[0].width, levels[0].height],
                "overview_pixel_window": [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
                "source_pixel_window": [
                    min(xs) * (levels[0].width // level.width),
                    min(ys) * (levels[0].height // level.height),
                    (max(xs) + 1) * (levels[0].width // level.width),
                    (max(ys) + 1) * (levels[0].height // level.height),
                ],
                "pixel_size": [dx, dy],
                "compression": "none" if level.compression == 1 else "deflate",
                "predictor": level.predictor,
                "range_requests": reader.requests,
                "range_bytes": reader.bytes,
                "object_bytes": reader.total,
                "allow_viewport": profile.cog.allow_viewport,
                "approved_bbox": profile.bbox,
            },
        }
    except (ValueError, OSError, struct.error, OverflowError, zlib.error) as exc:
        raise ProviderUnavailable() from exc
