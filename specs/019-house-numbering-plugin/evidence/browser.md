# HN019 browser evidence — 2026-11-22

Status: **PASS on isolated browser/API/test-DB candidate.**

Playwright suite: `tests/e2e/house-numbering.spec.ts`.

The normal E2E API port 8000 was already occupied by the running OpenVietGIS API, so that live service was deliberately left untouched. The final isolated setup used API port **8018**, web preview port **5178**, Keycloak port **18082**, and a dedicated PostGIS test container on port **54337**.

Verified in one lifecycle/journey test:

- official module discovery, registration, activation, open and disable;
- all seven House Numbering UI journeys;
- Core migrations followed by official-module migrations before browser startup;
- area creation and rule creation;
- proposal workflow surface;
- real CSV import and `certificate_unmatched` reconciliation;
- browser offline/online state;
- document issuance gate surface;
- public export surface;
- viewer read access with private-data warning;
- disabled module hides runtime without deleting project state;
- mobile viewport **390×844** opens the active module, navigates to Numbering and has no page-level horizontal overflow.

A real defect was found first: the generic test runner migrated Core only, so an activated module could open while `house_numbering.*` tables were absent. `tools/run_with_test_database.py` now applies Core migrations and then `migrate_official_modules()` before launching the child process, matching the real `db:migrate` order. A unit test locks this behavior.

Final isolated run after the fix: **1 passed in 19.0 s** (journey body 10.5 s).

## Public VPS preview verification

Exact module candidate commit: `7a3a2f0`.

A persistent preview was deployed without changing the existing 8443 runtime:

- public URL: `https://vps1.gpcds.site:2087`;
- API: dedicated systemd service on loopback port 8019;
- database: dedicated persistent PostGIS container on loopback port 54340;
- artifacts: dedicated `/var/lib/openvietgis-hn019-preview/artifacts` store;
- authentication: existing development Keycloak, with only the 2087 callback/origin added;
- web build: copied to a dedicated Nginx-readable `/var/www/openvietgis-hn019` directory, leaving the source worktree private.

Public smoke checks returned HTTP 200 for both the SPA root and `/api/v1/health/ready`. The same House Numbering Playwright journey was then executed through the public HTTPS endpoint (including Keycloak redirect/callback, secure cookie path, module registration/activation, US1–US7 workflows, mobile checks and disable): **1 passed in 40.0 s**.

This is an isolated development preview only. The existing 8443 runtime was not replaced or promoted, and T007 remains blocked by the wider Core convergence gates.
