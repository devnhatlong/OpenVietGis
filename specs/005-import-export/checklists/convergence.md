# R005 Convergence Checklist

- Code SHA: `f0e19f78f5dc76457aac25aa8e4aec05e8d2deac`
- Environment: Debian 13 (trixie), Node `v26.13.1`, Python `3.13.18`, PostGIS `18-3.7`, GDAL `3.10.3`, Keycloak `26.8.2`

## Verification Matrix

- [x] **OpenAPI 3.1 Contract & SDK:** `import-export-api.yaml` validated by `check_contracts.py` and compiled into `packages/client-sdk/src/generated/import-export.ts`
- [x] **Migration, RLS & Append-Only Evidence:** `0008_import_export` verified with forced RLS and non-owner `openvietgis_runtime` privileges
- [x] **Format Matrix & Hostile Input Protection:** GeoPackage, RFC 7946 GeoJSON, ZIP Shapefile codecs + archive traversal/bomb/encoding/CRS checks verified in unit & integration tests
- [x] **Independent Interoperability (SC-001):** Exported GeoPackage & ZIP Shapefile verified independently by GDAL 3.10.3 `ogrinfo`
- [x] **CRS Transformations (SC-003):** Explicit PostGIS PROJ pipelines (`ST_TransformPipeline` / `ST_InverseTransformPipeline`) verified for `4756 -> 4326` and `4326 -> 3857`
- [x] **Security, Idempotency & Revocation (SC-004/005/006):** Verified idempotent replay, `409 OPERATION_INTENT_CONFLICT`, `409 STALE_READ_PIN`, viewer import denial, and post-revocation `403` download block
- [x] **10,000-Feature Performance (SC-007):** Import `2.38 s <= 60 s`, Export `0.94 s <= 30 s`
- [x] **M1 Browser Journey (SC-009):** `tests/e2e/import-export-m1.spec.ts` passed end-to-end
- [ ] **SC-008 Human Usability (T010):** Pending observation of 5 real first-time GIS-capable users (kept explicitly open)
