# R010 — fixed XYZ/WMTS and bounded georeferenced TIFF sample adapters

Follow-on to the WMS/WFS slice at `0f87561`. This extends the previously
metadata-only WMTS_XYZ and COG_GEOTIFF registrations **only within these fixed,
operator-approved sample profiles**. No live endpoint, production data or
deployment. There is no new dependency or schema migration.

## Working tile sample profiles

Both use EPSG:3857 and a canonical Web Mercator 256-pixel tile at explicitly
approved fixed `z`, `x`, `y`. The coordinates must exactly match the
operator-approved `bbox` in projected metres (absolute tolerance 10 µm).
Require integer z=0..20 and 0 ≤ x,y < 2^z; no viewport, arbitrary tile,
or user geometry input.

- **XYZ/TileJSON 2.2.0 or 3.0.0**: actual metadata retrieval verifies name,
  attribution, coordinate order/scheme, min/max zoom, bounds containing the
  fixed tile, and the *exact* one operator-approved same-origin HTTPS tile
  template. No advertised template is followed. Only the validated fixed
  template is expanded using approved z/x/y and fetched. Actual PNG pixel
  verification and sanitization same as WMS.
- **WMTS 1.0.0 KVP**: actual GetCapabilities verifies advertised KVP GetTile,
  named layer, explicit style, PNG support, linked TileMatrixSet,
  TileMatrix identifier, EPSG:3857, exact canonical matrix width/height,
  256×256 tile, expected top-left and scale denominator at 0.28mm pixel,
  and row/column limits when present. Never follow advertised endpoints.
  Construct a fixed GetTile request to the exact approved endpoint, verify
  actual PNG bytes. No RESTful WMTS, alternate tile sizes, TMS,
  variable matrix width, arbitrary CRS or tile grids.

The operator policy uses the same default-deny process environment
`OPENVIETGIS_EXTERNAL_PROVIDER_PROFILES`; each deployment must explicitly
approve its source, rights, exact URL/layer and geography. Synthetic syntax
example (not a real provider):

```json
{
  "endpoint": "https://provider.example.org/tilejson.json",
  "protocol": "wmts_xyz",
  "layer": "tiles",
  "crs": 3857,
  "bbox": [10018754.171394622, 0, 20037508.342789244, 10018754.171394622],
  "attribution": "Controlled fixture",
  "license_text": "CC-BY-4.0",
  "tile": {
    "kind": "xyz", "z": 2, "x": 3, "y": 1,
    "template": "https://provider.example.org/tiles/{z}/{x}/{y}.png"
  }
}
```

For WMTS, endpoint is the exact KVP base and `tile` instead contains:
`{"kind":"wmts","z":2,"x":3,"y":1,"matrix_set":"WebMercatorQuad","matrix":"2","style":"default"}`.
Only `render` (plus local metadata) becomes true in the successfully
verified **sample**; nothing persisted to advertise continued availability.
A mismatch or absent profile fails before any tile request.

## Working tiled GeoTIFF range sample (not a general COG adapter)

- The transport emits actual `Range: bytes=0-2097151` with pinned HTTPS,
  exact endpoint, no redirect, five-second deadline, identity encoding,
  expected TIFF media. A valid response is HTTP 206 and a **complete
  bounded object range** `bytes 0-(total-1)/total`; total ≤2 MiB,
  exact Content-Length and bytes. Range-ignored 200, multipart, unknown
  total, oversized or partial object fail closed; no fallback full GET.
- Minimal classic TIFF parser verifies byte order/version, bounded single
  IFD, metadata lengths and offsets, non-overlapping metadata/raster
  intervals preceding the tiles; one <=512×512 image, <=16 row-major
  tiles sized 16..256 pixels, uncompressed contiguous 8-bit grayscale or
  RGB, no strips, no compression, no extra bands, no alternate orientation,
  no overview/sub-IFD/extra trailing payload.
- Real ModelPixelScale, ModelTiepoint and GeoKeyDirectory verify north-up
  RasterPixelIsArea, geographic EPSG:4326 or projected EPSG:3857, and exact
  operator-approved projected/geographic extent. Decode checked tiles from
  actual bytes and render sanitized PNG; actual tile count, band count,
  pixel size and range byte count returned under `sample.kind=geotiff_range_sample`.
  Only sample `render` is true. No feature query or analysis.
- This **does NOT certify full COG conformance** or implement large-object
  arbitrary byte windows, overview selection, compressed/BigTIFF/multiband
  or other GeoTIFF projection variants. Those remain unsupported. Profile
  kind `cog_geotiff` is the existing combined registration enum; successful
  output is explicitly named bounded GeoTIFF range sample, not COG.
  The operator matches exact approved raster file endpoint, CRS/extent,
  registration rights; file itself is the approved source identity
  (registration layer name is operator-local, not claimed TIFF layer metadata).

Synthetic profile:

```json
{
  "endpoint": "https://provider.example.org/sample.tif",
  "protocol": "cog_geotiff",
  "layer": "raster",
  "crs": 4326,
  "bbox": [105.5, 20.5, 106.5, 21.5],
  "attribution": "Controlled fixture",
  "license_text": "CC-BY-4.0"
}
```

## Independent evidence

- 27 unit tests pass (19 inherited WMS/WFS/domain/transport, eight new raster
  tests). Requests flow through the actual stdlib HTTP serializer/parser with
  controlled synthetic socket/DNS/TLS boundary; no Internet requests.
- Independent known Web Mercator extent at z=2 x=3 y=1, actual XYZ and WMTS
  tile response pixel proof at (12,34), exact tile/KVP request assertions.
  Wrong TileJSON attribution, template, scheme, zoom, bbox, WMTS CRS,
  matrix size, scale, limits, encoding or media causes zero tile egress.
  Malformed profile, cross-origin template, invalid coordinates/extent
  are rejected.
- Independent hand-built valid tiled TIFF: actual 32×32, four 16×16
  quadrants. Pillow's independent TIFF decoder confirms pixels 12,99,188,240
  before our decoder; sanitized preview has matching four RGBA values.
  Raw HTTP oracle checks actual 206 range header/size. Incorrect Content-Range,
  ignored Range, oversized source, unknown total, malformed TIFF,
  georeferencing mismatch, invalid offset, compression and extra/truncated
  payload all rejected.
- Strict targeted Ruff/mypy plus client SDK and web TypeScript typecheck
  pass. Existing WMS/WFS integration 3 passed before this follow-on.
  New protected raster-route integration test
  `test_r010_raster_provider.py` collects successfully; no live DB tests
  executed in this phase (coordinated DB slot belongs to parent).
  Integrated candidate still must run that test and browser proof for
  new raster profiles.

All registered external sources remain metadata-only until each explicit
preview proves the actual response. SDK and Hub let users request all four
registration protocols, and show actual sample type, tile coordinates or
GeoTIFF metadata. General Core map references/continuous viewport, broad
OGC protocol coverage, full COG functionality, live TLS-provider fixture
and independent exact-candidate security/browser acceptance remain open.
