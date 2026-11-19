# R004 validation guide

Status: automated verification green on VPS Debian 13 (`integration/004-on-verified-main`, code SHA `a993542cefa91ea499f4ba8f19ced3e8dcd31513`, baseline `c5cc5a9`). Human usability observation (**SC009 / T046**) remains open until five first-time GIS-capable users are observed.

## Verified Commands & Actual Results (2026-11-20, VPS `103.77.243.154`)

- **Runtime:** `pnpm validate:runtime` → Node `v26.13.1` (accepted baseline)
- **TypeScript / Web / SDK:** `pnpm validate:ts` → ESLint 0 warnings, `tsc --noEmit` clean, `@openvietgis/client-sdk` 58/58 passed, `@openvietgis/web` 44/44 passed, Vite production build clean
- **Python static & unit/contract/arch:** `pnpm validate:py` → `ruff` clean, `mypy --strict` clean (79 files), `pytest` 533/533 passed
- **Contracts, scope, architecture, docs:** `pnpm validate:contracts`, `pnpm validate:scope`, `pnpm validate:arch`, `pnpm validate:docs` → all OK
- **Restricted-runtime PostGIS integration & performance:** `pnpm validate:integration` → 263 passed (including `test_map_migrations.py`, `test_map_viewport_real.py`, `test_saves.py`, `test_authorization_matrix.py`, `test_wire_contract.py`)
- **Live Keycloak OIDC:** `OPENVIETGIS_LIVE_OIDC=1 pytest apps/api/tests/integration/identity/test_live_keycloak_oidc.py` → 2/2 passed
- **Playwright E2E:** `pnpm validate:e2e` → 16/16 passed (4/4 `map-workspace.spec.ts`, 1/1 `map-performance.spec.ts`, 11/11 R001–R003 E2E); `pnpm validate:e2e:bootstrap` → 1/1 passed
- **Security & tenant timing evidence:** `check_secret_surfaces.py` → 3/3 clean; `check_tenant_timing.py` → `sc-004: 1970 ms`, `sc-001: 297–322 ms`, `sc-011: 1957 ms`
- **SC007 measured benchmark (100 trials after 5 warmups, 10,000-feature Core profile, external network blocked, `specs/004-map-workspace/evidence/sc007.json`):**
  - Map open: `p50 = 1922.8 ms`, `p95 = 2254.5 ms` (budget `<= 3000 ms`), `max = 2790.4 ms`
  - Select → authorized inspector: `p50 = 298.5 ms`, `p95 = 384.2 ms` (budget `<= 1000 ms`), `max = 468.9 ms`
  - External requests: `0`

## Outstanding Human Acceptance Gates

- **R004 SC009 (T046):** Observe five actual first-time GIS-capable users completing the one-sentence task (4/5 independently open/inspect/reopen within 5 min) and record in `specs/004-map-workspace/evidence/usability.md`.
- **R002 SC013:** Separate uncoached human evidence remains an external-release gate.
