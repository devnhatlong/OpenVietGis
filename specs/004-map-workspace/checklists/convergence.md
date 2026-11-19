# R004 Convergence Checklist

- Code SHA: `a993542cefa91ea499f4ba8f19ced3e8dcd31513`
- Environment: Debian 13 (trixie), Node `v26.13.1`, Python `3.13.18`, PostGIS `18-3.7`, Keycloak `26.8.2`

## Verification Matrix

- [x] **Contracts & SDK:** `check_contracts.py` + `openapi-typescript` generated SDK exact match (`packages/client-sdk/src/generated`)
- [x] **Scope & MapEngine boundary:** `check_scope.py` verifies `maplibre-gl` is strictly isolated to `apps/web/src/features/map/maplibre-engine.ts`
- [x] **Persistence, Migrations & RLS:** `0007_map_workspace` BIGINT revision, composite FKs, append-only `map_operations`/`map_revisions`, forced RLS verified in `test_map_migrations.py`
- [x] **Viewport & CRS:** Pinned bounded EPSG:4326 display reads, 1000-feature/20000-position/2MiB/2s budgets, source data immutability verified in `test_map_viewport_real.py` and `map-workspace.spec.ts`
- [x] **Save, CAS, Recovery & History:** Optimistic concurrency, idempotent operation replay, lost-ack reconciliation, immutable before/after history verified in `test_saves.py` and `map-workspace.spec.ts`
- [x] **Authorization & Revocation:** Viewer local preview vs denied mutation, cross-tenant isolation, warm selection/inspector unmount on 403 revocation verified in `test_authorization_matrix.py` and `map-workspace.spec.ts`
- [x] **SC007 Performance:** 100-trial 10,000-feature benchmark passed (`open p95 = 2254.5 ms <= 3000 ms`, `select p95 = 384.2 ms <= 1000 ms`, `0` external requests)
- [ ] **SC009 Human Usability (T046):** Pending real 5-user observation (intentionally kept open)
- [ ] **Exact-SHA GitHub CI & Promotion (T047/T048):** Pending branch push / GitHub Actions confirmation
