# Implementation Plan: Import and Export (R005)

**Parent roadmap:** [ROADMAP.md, entry R005](../../ROADMAP.md#r005)
**Baseline:** Verified R004 (`990e735`) on `integration/005-import-export`.

## Supported Format & Interoperability Matrix

| Format | Key | Read (Import) | Write (Export) | Geometry Families | Dimensions | CRS Policy | Loss / Disclosure Policy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GeoPackage 1.2/1.3 | `geopackage` | Yes (multi-member selection; 1 member per import) | Yes (preferred lossless) | `Point`, `LineString`, `Polygon` | `XY` | Explicit `gpkg_spatial_ref_sys` EPSG `4326`, `3857`, `4756`, `5899` (or approved R003 transform) | Lossless across all 5 R003 field types (`text`, `integer`, `decimal`, `boolean`, `timestamp`) and NULL distinctions |
| RFC 7946 GeoJSON | `geojson` | Yes (`FeatureCollection` only) | Yes | `Point`, `LineString`, `Polygon` | `XY` | Strict RFC 7946 `EPSG:4326` X/Y (rejects legacy/contradictory `crs` member) | Explicit disclosure for `decimal`/`timestamp` string encoding; WGS84 only |
| ZIP Shapefile | `shapefile_zip` | Yes (coherent `.shp`/`.shx`/`.dbf`; `.prj` + `.cpg` or explicit approved choice) | Yes (`.shp`/`.shx`/`.dbf`/`.prj`/`.cpg`) | `Point`, `LineString`, `Polygon` | `XY` | Exact `.prj` WKT match to `4326`/`3857`/`4756`/`5899` or explicit attributable choice; never guessed | Explicit user approval required for DBF 10-char field name mapping, `text > 254` truncation, or `timestamp`/`boolean` DBF representation |

## Resource & Safety Limits

- Max upload size: `25 MiB` (`26,214,400` bytes)
- Max ZIP expanded bytes: `50 MiB` (`52,428,800` bytes), max ZIP entries: `64`, zero path traversal / absolute paths / symlinks / nested bombs
- Max features per import/export: `25,000`, max fields: `100`, max string attribute length: `4,096`
- Validated CRS operations: strictly R003 PostGIS PROJ explicit pipelines (`4326 <-> 3857`, `4326 <-> 4756`, `4756 <-> 5899`, `4326 <-> 5899` within verified area of use); unknown/generic VN-2000 or out-of-area geometries fail explicitly
- Geometry validity: PostGIS `ST_IsValid` + finite coordinates + non-empty + single declared family

## Durable Jobs, Staging & Atomic Publication

1. **Immutable Object Staging (`LocalObjectStore`):** Content-addressed / scoped write-temp-fsync-rename with SHA-256 verification under `OPENVIETGIS_ARTIFACT_STORE_DIR`. No internal filesystem paths ever appear in API responses or errors.
2. **Database Schema (`transfers.*`):** Forced RLS (`openvietgis.organization_id` + `openvietgis.project_id`) on `transfers.source_assets`, `transfers.jobs`, `transfers.job_attempts`, `transfers.derived_artifacts`. `source_assets` and `job_attempts` are append-only for `openvietgis_runtime`.
3. **Atomic Import Publication:** Single PostgreSQL transaction re-verifies current `project.edit` authority + cancel boundary, inserts `spatial.data_sources` (`kind='imported_file'`, `source_asset_id`), `spatial.source_fields`, `spatial.reference_features`, `spatial.layers`, `spatial.catalog_changes`, `audit.audit_events`, and transitions `transfers.jobs` to `succeeded`. Any error/denial/cancel rolls back completely.
4. **Fixed-Revision Export & Revocable Download:** Export pins exact `content_revision` + `schema_revision` (returns `409 STALE_READ_PIN` if changed), writes immutable verified `DerivedArtifact` + `comparison_report`, and every `GET /artifacts/{artifact_id}/download` re-checks current `project.read` authority, scope, expiry, and SHA-256 integrity.
