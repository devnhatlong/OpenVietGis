# R005 Validation Guide & Measured Evidence

Status: automated verification green on VPS Debian 13 (`integration/005-import-export`, code SHA `f0e19f78f5dc76457aac25aa8e4aec05e8d2deac`, built on verified R004 `990e735`). Human usability observation (**SC-008 / T010**) remains explicitly open until five first-time GIS-capable users are observed.

## Verified Results (2026-11-20, VPS `103.77.243.154`)

- **Runtime & Static Guards:** `pnpm validate:runtime` (Node `v26.13.1`), `pnpm validate:ts` (ESLint 0 warnings, `tsc` clean, 61 SDK tests + 44 Web tests + Vite build), `pnpm validate:py` (`ruff`, `mypy --strict` on 92 files, 538 unit/contract/arch tests), `pnpm validate:contracts` (Specs 002/003/004/005 + generated SDK exact match), `pnpm validate:scope`, `pnpm validate:arch`, `pnpm validate:docs` — all green.
- **Migration & RLS (`0008_import_export`):** Upgrade/downgrade cycle verified; forced RLS on `transfers.source_assets`, `transfers.jobs`, `transfers.job_attempts`, `transfers.derived_artifacts`; append-only privileges on `source_assets` & `job_attempts`.
- **Independent Interoperability (GDAL 3.10.3 `ogrinfo`):** Verified lossless GeoPackage (`EPSG:4326`), transformed ZIP Shapefile (`EPSG:3857` with explicit DBF loss approval), and RFC 7946 GeoJSON round-trips.
- **CRS & Security:** Verified VN-2000 `EPSG:4756 -> EPSG:4326` import preserving distinct `source_crs` / `stored_crs`, PostGIS `ST_IsValid` rejection of self-intersecting polygons, hostile ZIP path traversal & entry bomb rejection, idempotent replay + `409 OPERATION_INTENT_CONFLICT`, `409 STALE_READ_PIN` on stale export, and immediate `403` on artifact download after grant revocation.
- **SC-007 10,000-feature GeoPackage Benchmark:** Confirmed import `2.38 s` (budget `<= 60 s`), confirmed export `0.94 s` (budget `<= 30 s`).
- **SC-009 M1 Browser E2E (`import-export-m1.spec.ts`):** Real Keycloak OIDC → GeoJSON import → MapLibre render/select/inspect/save → fixed-revision GeoPackage export → protected download with verified SHA-256 & SQLite header — passed in `5.8 s`.
