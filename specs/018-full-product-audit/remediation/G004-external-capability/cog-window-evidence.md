# R010 — bounded, compressed COG viewport and overview

This is a real partial-range raster adapter, distinct from the earlier
small, uncompressed complete-object GeoTIFF profile. An operator must opt
in and pin the exact file, rights, CRS, full source dimensions and source
extent. The approved display bbox must be inside that extent. No new
dependency or migration; no production or customer endpoint accessed.

Synthetic policy example in `OPENVIETGIS_EXTERNAL_PROVIDER_PROFILES`:

```json
{
  "endpoint": "https://provider.example.org/cog.tif",
  "protocol": "cog_geotiff",
  "layer": "raster",
  "crs": 4326,
  "bbox": [105, 20, 106, 21],
  "attribution": "Controlled fixture",
  "license_text": "CC-BY-4.0",
  "cog": {
    "source_bbox": [105, 20, 106, 21],
    "source_width": 1024,
    "source_height": 1024,
    "allow_viewport": true
  }
}
```

The existing protected preview route reads the approved sample. The new
protected POST `.../external-sources/{connection_id}/viewport` accepts only
`crs`, `bbox`, `width`, `height` in its JSON body. It requires explicit
viewport opt-in, exact approved CRS and a strictly contained bbox; neither
coordinates nor arbitrary URLs are forwarded to providers. Shared
authorization, CSRF, project read permissions, row locks and live rights/
profile recheck apply. No-store proof returns the current generation but
does not persist renderability, cache bytes, or override revocation.

The reader verifies real TIFF metadata: classic 32-bit offsets, <=6 image
directories/levels, <=4096 tile entries, north-up PixelIsArea, EPSG:4326
or 3857, operator-pinned source dimensions/extent, contiguous uint8 gray
or RGB, no strips, no masks/alpha, tiled uncompressed or zlib Deflate with
optional horizontal predictor. Tile dimensions 16..512, non-overlapping
metadata and tile intervals, smallest-first overview raster order,
row-major within each level, consistent power-of-two reduction and
georeference. Decoder reads exact selected tiles, reconstructs predictor,
samples output pixel centers, chooses the coarsest suitable overview
without undersampling output, and emits only the requested PNG. Tile
granularity may fetch surrounding source pixels inside a tile; those are
not delivered in the viewport image.

Each operation is bounded to 64 KiB initial metadata range, <=16 selected
tiles, <=17 HTTP requests, <=4 MiB network payload, <=2 GiB source object,
<=15 s total and <=5 s per range, 1..512 pixels per output axis and
32768 pixels per source axis. The previous pinned public IP/DNS and
hostname-verifying TLS, redirect refusal, media, response size and request
slot controls apply to every call. HTTP 206, Content-Range and length must
match exactly; a strong ETag pins all subsequent If-Match responses and
total object size. Range-ignored 200, weak or changing ETag, changing size,
malformed metadata, incorrect bounds, unsupported layouts, decompression
bombs or excessive budgets fail closed without full-object fallback.

The Hub offers the approved numeric viewport only after fresh verification
indicates that it is enabled; shows actual rendered sample, selected
overview, tile count, source pixel window, range count and actual fetched
bytes. Render is true only in the request result. Metadata registration,
edit, query, analysis, exports and offline capabilities are unchanged.

## Evidence and limitations

- Independent hand-built compressed TIFF fixture and independent Pillow
  TIFF decoder: exact 256x256 overview pixels and 128x128 native crop
  pixels; controlled actual HTTP request/response parser checks Range and
  If-Match. Denials include wrong CRS, invalid offset, Deflate expansion,
  malformed/truncated range, ETag/size drift, ignored Range and tile budget.
- Real GDAL-generated COG (GDAL 3.10.3, 1024x1024, two overviews,
  128x128 tiled Deflate/predictor). Independent GDAL overview/crop reads
  compared every output pixel. Grayscale object 1,379,446 bytes:
  both the whole 256x256 overview and 128x128 native crop fetched
  81,931 bytes via two ranges (5.94% of object); not a complete download. A
  second GDAL-generated projected EPSG:3857 RGB COG independently verifies
  all three interleaved channels for overview and native crop; each read
  transfers less than 10% of the TIFF object.
- 42 targeted provider unit tests pass, including 15 advanced COG tests;
  targeted Ruff and mypy, SDK and web TypeScript checks pass. Controlled
  socket/DNS/TLS fixture, not a live external provider or real-provider TLS
  acceptance. New protected project-route integration test collects (1);
  real DB execution deferred to parent-approved synthetic DB slot.
- General unrestricted COG compliance, BigTIFF, arbitrary CRS/reprojection,
  JPEG/LZW/ZSTD, multiband beyond RGB, nodata/masks/alpha, rotated grids,
  arbitrary odd-size pyramids and continuous Core map catalog/viewport
  overlay are not implemented or claimed. Existing fixed tile/WMS/WFS
  sample scopes remain. This is a strict opt-in coordinate window in Hub,
  not general-purpose external map composition.
