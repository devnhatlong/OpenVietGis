"""Bounded tiled GeoTIFF sample through an exact, verified HTTP range.

This profile is deliberately NOT a general Cloud Optimized GeoTIFF reader:
only one <=2 MiB classic TIFF image, uncompressed 8-bit tiled data, north-up
EPSG:4326 or EPSG:3857, known geokeys, no arbitrary windows or overviews.
The transport must return the entire object from a bounded 206 response.
"""

from __future__ import annotations

import base64
import io
import math
import struct
from typing import Any

from PIL import Image

from openvietgis_api.domains.external_sources.provider import (
    MAP_MAX,
    Fetch,
    ProviderProfile,
    ProviderUnavailable,
    _bbox,
    _near_bbox,
)

# Only tags needed to decode uncompressed contiguous grayscale/RGB tiles
# and verify georeferencing. Reject extra parser-dependent metadata.
_REQUIRED = {
    256,
    257,
    258,
    259,
    262,
    277,
    284,
    322,
    323,
    324,
    325,
    33550,
    33922,
    34735,
}
_OPTIONAL = {254, 274, 339}
_TYPE = {3: ("H", 2), 4: ("I", 4), 12: ("d", 8)}


def _decode_tiff(raw: bytes, profile: ProviderProfile) -> tuple[Image.Image, dict[str, Any]]:
    if not 8 <= len(raw) <= MAP_MAX:
        raise ValueError("invalid TIFF size")
    if raw[:2] == b"II":
        endian = "<"
    elif raw[:2] == b"MM":
        endian = ">"
    else:
        raise ValueError("invalid TIFF byte order")
    version, ifd = struct.unpack_from(endian + "HI", raw, 2)
    if version != 42 or not 8 <= ifd <= min(4096, len(raw) - 2):
        raise ValueError("only bounded classic TIFF supported")
    count = struct.unpack_from(endian + "H", raw, ifd)[0]
    if not len(_REQUIRED) <= count <= len(_REQUIRED | _OPTIONAL):
        raise ValueError("unsupported TIFF tag count")
    end = ifd + 2 + count * 12 + 4
    if end > len(raw):
        raise ValueError("truncated TIFF directory")
    if struct.unpack_from(endian + "I", raw, end - 4)[0] != 0:
        raise ValueError("multiple images/overviews unsupported")

    tags: dict[int, tuple[int | float, ...]] = {}
    metadata_intervals: list[tuple[int, int]] = []
    for index in range(count):
        pos = ifd + 2 + 12 * index
        tag, field_type, n = struct.unpack_from(endian + "HHI", raw, pos)
        if (
            tag not in _REQUIRED | _OPTIONAL
            or tag in tags
            or field_type not in _TYPE
            or not 1 <= n <= 64
        ):
            raise ValueError("unknown TIFF tag or type")
        fmt, width = _TYPE[field_type]
        size = n * width
        if size <= 4:
            offset = pos + 8
        else:
            offset = struct.unpack_from(endian + "I", raw, pos + 8)[0]
            if not end <= offset <= min(65536, len(raw) - size):
                raise ValueError("metadata must precede raster tiles")
            if any(offset < right and left < offset + size for left, right in metadata_intervals):
                raise ValueError("overlapping TIFF metadata")
            metadata_intervals.append((offset, offset + size))
        values = struct.unpack_from(endian + fmt * n, raw, offset)
        # Every GeoTIFF field must use its canonical numeric representation.
        if field_type == 12 and tag not in (33550, 33922):
            raise ValueError("unexpected doubles")
        if tag in (33550, 33922) and field_type != 12:
            raise ValueError("missing georeferencing doubles")
        if tag == 34735 and field_type != 3:
            raise ValueError("invalid geokey type")
        tags[tag] = values

    if not _REQUIRED <= tags.keys():
        raise ValueError("missing TIFF metadata")

    def scalar(tag: int, default: int | None = None) -> int:
        values = tags.get(tag)
        if values is None and default is not None:
            return default
        if values is None or len(values) != 1 or type(values[0]) is not int:
            raise ValueError("invalid TIFF scalar")
        return values[0]

    width, height = scalar(256), scalar(257)
    tile_w, tile_h = scalar(322), scalar(323)
    channels = scalar(277)
    mode = (
        "L"
        if channels == 1 and scalar(262) == 1
        else "RGB"
        if (channels == 3 and scalar(262) == 2)
        else None
    )
    if (
        mode is None
        or not 1 <= width <= 512
        or not 1 <= height <= 512
        or not 16 <= tile_w <= 256
        or not 16 <= tile_h <= 256
        or tile_w % 16
        or tile_h % 16
        or tags[258] != (8,) * channels
        or scalar(259) != 1
        or scalar(284) != 1
        or scalar(274, 1) != 1
        or scalar(254, 0) != 0
        or tags.get(339, (1,) * channels) != (1,) * channels
    ):
        raise ValueError("unsupported TIFF layout")
    cols, rows = math.ceil(width / tile_w), math.ceil(height / tile_h)
    tile_count = cols * rows
    offsets, lengths = tags[324], tags[325]
    if (
        tile_count > 16
        or len(offsets) != tile_count
        or len(lengths) != tile_count
        or any(type(n) is not int for n in offsets + lengths)
    ):
        raise ValueError("inconsistent tile offset/count")
    previous = max([end, *(right for _, right in metadata_intervals)])
    pixels_per_tile = tile_w * tile_h * channels
    for offset, length in zip(offsets, lengths, strict=True):
        if (
            type(offset) is not int
            or type(length) is not int
            or offset < previous
            or length != pixels_per_tile
            or offset + length > len(raw)
        ):
            raise ValueError("invalid tile layout or offset")
        previous = offset + length
    if previous != len(raw):
        raise ValueError("extra/trailing raster bytes")

    scale, tie = tags[33550], tags[33922]
    if (
        len(scale) != 3
        or len(tie) != 6
        or not all(math.isfinite(x) for x in scale + tie)
        or not scale[0] > 0
        or not scale[1] > 0
        or scale[2] != 0
        or tie[:3] != (0, 0, 0)
        or tie[5] != 0
    ):
        raise ValueError("only north-up origin pixel-area georeference supported")
    keys = tags[34735]
    if len(keys) != 16 or keys[:4] != (1, 1, 0, 3):
        raise ValueError("unsupported geokey directory")
    parsed_keys: dict[int, int] = {}
    for i in range(4, len(keys), 4):
        key, location, key_count, value = keys[i : i + 4]
        if (
            any(type(v) is not int for v in (key, location, key_count, value))
            or location != 0
            or key_count != 1
            or key in parsed_keys
        ):
            raise ValueError("unsupported geokey")
        # Validated exact integer representation above.
        assert isinstance(key, int) and isinstance(value, int)
        parsed_keys[key] = value
    expected = (
        {1024: 2, 1025: 1, 2048: 4326} if profile.crs == 4326 else {1024: 1, 1025: 1, 3072: 3857}
    )
    if profile.crs not in (4326, 3857) or parsed_keys != expected:
        raise ValueError("incorrect raster CRS/georeference")
    extent = _bbox(
        [tie[3], tie[4] - height * scale[1], tie[3] + width * scale[0], tie[4]],
        profile.crs,
    )
    if not _near_bbox(extent, profile.bbox):
        raise ValueError("raster extent does not match approved bbox")
    # Decode only the checked tile byte spans. No generic TIFF parser and no
    # metadata-driven file reads or compression expansion.
    image = Image.new(mode, (width, height))
    for i, offset in enumerate(offsets):
        assert type(offset) is int  # checked above
        x, y = (i % cols) * tile_w, (i // cols) * tile_h
        tw, th = min(tile_w, width - x), min(tile_h, height - y)
        tile = Image.frombytes(mode, (tile_w, tile_h), raw[offset : offset + pixels_per_tile])
        image.paste(tile.crop((0, 0, tw, th)), (x, y))
    return image, {
        "kind": "geotiff_range_sample",
        "tile_width": tile_w,
        "tile_height": tile_h,
        "tile_count": tile_count,
        "pixel_size": [scale[0], scale[1]],
        "band_count": channels,
        "range_bytes": len(raw),
    }


def geotiff_preview(profile: ProviderProfile, fetch: Fetch) -> dict[str, Any]:
    # The secure transport interprets the "tiff" media profile as a bounded
    # byte-range GET and requires exact 206 Content-Range, never 200 fallback.
    raw = fetch(profile.endpoint, "tiff", MAP_MAX)
    try:
        image, metadata = _decode_tiff(raw, profile)
        output = io.BytesIO()
        image.convert("RGBA").save(output, format="PNG")
        return {
            "image_png_base64": base64.b64encode(output.getvalue()).decode("ascii"),
            "width": image.width,
            "height": image.height,
            "sample": metadata,
        }
    except (ValueError, OSError, struct.error, OverflowError) as exc:
        raise ProviderUnavailable() from exc
