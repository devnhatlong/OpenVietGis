# Synthetic GIS fixtures — 2026-11-21

Candidate c6d449fc0ead93e259b79b87e63c1c894bd16c93. Generated only synthetic fixtures in ignored dist/audit018/fixtures, not production data. Each source GeoJSON uses WGS84 longitude/latitude and typed properties (including Vietnamese text, numeric zero, boolean false, null); point features P1/P2, one line L1, one closed polygon A1. Bounds [106.6,10.7] to [106.61,10.71]. Expected counts: 2 points, 1 line, 1 polygon.

Independent oracle GDAL ogr2ogr/ogrinfo 3.10.3 generated GPKG and UTF-8 Shapefile profiles (ZIP via Python standard zipfile CLI), inspected each of 9 formats: all 9 have expected family/count/bounds and EPSG:4326. This is input fixture proof, not proof that the product round-trips these files; verify output semantics later. Shapefile representational limitations must be explicitly accounted for; no assumed losslessness.
CRS control sources are frozen R003 independent EPSG/analytic controls and VN-2000 control evidence; actual target transforms will be retested with runtime.

Checksums (SHA256; generated originals and independent controls):
```
aef1a0ec5c385eaaf201590eee7ca3a583d4a9248befc10b10af54541f7962e0  lines.geojson
7b413713be29691728d5ff18ca55e9af4556d4c3846dd27ff5e53d6e400f65d2  points.geojson
80ccbe2f67ca58f43e3d91ad5a5512665cb0d2d24fdc68bebff2e4d97af8aac3  polygons.geojson
95b1e5dedfa7870c16756a7a813d062a03b47588fe943e4a052574ccbc140d80  lines.gpkg
c1b5a6713c7b4fa54796f63f48494fce6631010c46f518de84f0a65cd1e80ea9  points.gpkg
667c84a2fcb466cdb3ff5056365ce3b7bdd77ba3a5f175eb9e97faf0184ab51b  polygons.gpkg
5a0d2103de30e4bb6c2b369ba09a2b79d982d4cbab51c5cdf3021afc59d61e39  lines.zip
da626764a43788ba0b7beaecbaeac20ac8907e3b1e4c493f9d92a4630f9a4087  points.zip
13587f18a42f2b65e81ea4e6cc3bfedb43f682cdf2a951b1a325bb1f5b7900c1  polygons.zip
2e0a598138242b2a8b425133cd223b5ff4a0a361a758882ac8105b1f0a971c71  apps/api/tests/fixtures/spatial_controls.py
388c2459e5e9a4d1ec7616171a18dab34a836cbf2f24897c26c798475df9c172  specs/003-spatial-catalog-crs/vn2000-control-evidence.md
```
