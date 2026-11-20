# Tasks: Import and Export (R005)

- [x] T001 Freeze format matrix, OpenAPI 3.1 contract (`specs/005-import-export/contracts/import-export-api.yaml`), and generated client SDK types.
- [x] T002 Add migration `0008_import_export` (`transfers` schema, forced RLS, append-only `source_assets`/`job_attempts`, `spatial.data_sources` imported_file link, `export` capability).
- [x] T003 Implement `domains/transfers` (`domain.py`, `ports.py`, `service.py`) with zero adapter imports.
- [x] T004 Implement immutable `LocalObjectStore` and real format codecs (`geopackage`, `geojson`, `shapefile_zip`) with archive hostility/CRS/encoding/loss validation.
- [x] T005 Implement RLS-enforced `SqlTransferRepository` with PostGIS `ST_IsValid`, R003 `spatial_transform` pipelines, and atomic import/export publication.
- [x] T006 Wire FastAPI HTTP adapter (`adapters/http/transfers.py`), error handlers, and `main.py` routes.
- [x] T007 Implement typed `@openvietgis/client-sdk` transfer methods and unit tests.
- [x] T008 Implement protected Web UI (`apps/web/src/features/transfers/`) for upload/inspect/confirm import, fixed-revision export preview/confirm/download, and durable jobs tracking.
- [x] T009 Verify unit, contract, migration/RLS, GDAL independent interoperability, CRS control-point transforms, revocation/cancel/replay/recovery, SC-007 benchmark, and M1 Playwright E2E journey.
- [ ] T010 SC-008 human observation (5 first-time GIS-capable users) — remains explicitly open until real humans are observed.
