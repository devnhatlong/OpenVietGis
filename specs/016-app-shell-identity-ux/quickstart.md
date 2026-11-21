# Quickstart Validation: App Shell & Identity UX

## Prerequisites

- Exact feature branch rebased onto the current verified main before implementation.
- Supported Node 26 runtime and frozen dependency install.
- Existing API, PostgreSQL test database and configured synthetic/reference OIDC provider.
- Existing R002 integration/security tests green before frontend acceptance.

## Validation scenarios

### 1. Public landing remains public

1. Start with a browser context without an application session.
2. Open `/`.
3. Confirm Landing renders directly and exposes a clear Đăng nhập action.
4. Open `/login`; confirm configured providers are listed.
5. Navigate back to `/`.

**Expected**: No protected organization data is requested/rendered as public content; landing and login are distinct surfaces.

### 2. Deep-link login and return

1. Open a protected canonical project URL while signed out.
2. Complete provider login.
3. Verify the browser returns to the same valid canonical destination.
4. Repeat with an invalid/external return target.

**Expected**: Valid relative deep link is restored; invalid/external target falls back to `/app`.

### 3. No auth flicker

1. Sign in and open `/app`.
2. Trigger window blur/focus, reconnect and background account revalidation.
3. Record DOM/screenshot sequence.

**Expected**: Authenticated shell remains mounted. It does not flash Landing or a full-page “checking” screen. Protected tenant content still follows its own strict current-read state.

### 4. Dashboard and navigation

1. Use a user with at least one organization and project.
2. Open `/app`.
3. Navigate Overview → Projects → Members/Access → Account.
4. Repeat with a user having no projects.

**Expected**: Human-readable names and empty states are clear; no primary UUID/roadmap-code labels.

### 5. Logout everywhere

1. Open Dashboard, a Project route and another authenticated surface.
2. Open the account menu and sign out.
3. Attempt to revisit a protected route.

**Expected**: Server session is invalidated; protected route returns to login and no stale protected data remains visible.

### 6. Legacy route migration

Exercise the agreed legacy URL matrix from [routes-and-redirects.md](contracts/routes-and-redirects.md).

**Expected**: Each supported old path reaches its canonical equivalent without context loss or authorization bypass.

### 7. Accessibility/responsive

- Keyboard-only pass through Landing, Login, shell navigation and account menu.
- Check visible focus, skip-to-content, accessible names and announced errors.
- Check widths 768, 1024 and 1440 px.
- Respect reduced motion.

### 8. Deterministic visual regression

Capture Landing, Login, Dashboard and Account Menu using stable fixture data.

**Expected**: No unexplained screenshot diff; remote/non-deterministic external content is excluded.

## Required commands

Use repository-standard commands from the exact supported runtime:

- `pnpm --filter @openvietgis/web test`
- `pnpm --filter @openvietgis/web lint`
- `pnpm --filter @openvietgis/web typecheck`
- `pnpm --filter @openvietgis/web build`
- targeted Playwright scenarios
- full root validation before convergence

Record exact commit, runtime versions and browser fixture for acceptance evidence.


## Convergence Evidence — 2026-11-21

### Exact implementation lineage

- Integration base before frontend UX work: `c6d449f` (`integration/r006-r015-complete`).
- Preserved current DEV frontend baseline: `3b4dc32`.
- Spec Kit child slices added: `b47c339`.
- Public/auth shell checkpoints: `d2717ac`, `613052e`, `a11ff03`, `3bea759`.
- Final implementation + regression stabilization snapshot: `dbaad69`.
- Production and the original `:8443/dev/` workspace were not replaced during this convergence.

### Runtime and browser profile

- Node: `v26.13.1`
- pnpm: `12.21.0`
- Playwright: `1.65.1`
- Chromium reported by measured Map evidence: `159.0.8154.6`
- Linux kernel: `6.12.41+deb13-amd64`
- Reference runner: 2 vCPU, ~4 GiB RAM

### Bundle comparison

Baseline `3b4dc32`:

- JS: 1,588.15 kB raw / 440.56 kB gzip
- CSS: 96.81 kB raw / 16.67 kB gzip
- MapLibre worker: 519.54 kB

Final implementation:

- JS: 1,610.22 kB raw / 447.17 kB gzip
- CSS: 126.88 kB raw / 22.64 kB gzip
- MapLibre worker: 519.54 kB unchanged

Delta:

- JS raw: +22.07 kB, approximately +1.39%
- JS gzip: +6.61 kB, approximately +1.50%
- CSS grows by ~30 kB raw because the shared AppShell, auth, dashboard, responsive and accessibility layers are now included.
- Vite still reports a >500 kB chunk warning. This is a non-blocking optimization item for later route/code splitting; no acceptance budget in this child slice is exceeded.

### Validation results

All results below were obtained on the isolated E2E ports Keycloak `18081`, API `8010`, Web `5178`, without replacing DEV/production.

- TypeScript/lint/build:
  - Client SDK: 62/62 tests PASS
  - Web: 60/60 unit tests PASS
  - ESLint PASS
  - TypeScript PASS
  - Vite production build PASS
- Python/static:
  - 538 Python unit/contract/architecture tests PASS
  - contracts generation/check PASS
  - scope check PASS
  - architecture check PASS
  - docs check PASS
- Integration/performance:
  - 273 PASS, 1 SKIP
- Browser E2E:
  - full non-bootstrap suite: 31/31 PASS in one detached clean run
  - bootstrap suite: 1/1 PASS
  - deterministic visual baselines: Landing, Login, Dashboard, Account Menu PASS
- Security evidence:
  - selected secret-surface artifacts: clean
  - invitation acceptance timing: 2,408 ms
  - organization switch timings: 662 ms / 547 ms / 564 ms
  - bootstrap timing: 6,608 ms
- Parent R004 regression benchmark:
  - 10,000 reference features
  - 100 measured map-open trials: p50 ~2,174 ms; p95 ~2,700 ms; budget <=3,000 ms
  - 100 measured select-to-inspector trials: p50 ~274 ms; p95 ~346 ms; budget <=1,000 ms
  - external network requests during deterministic benchmark: 0
  - a full benchmark immediately followed by the Map Workspace mutation/selection/save scenario also PASS after the Fit-All metadata/race fix.

### Scenario acceptance

1. Public Landing vs Login: PASS. `/` and `/login` are distinct and signed-out protected routes preserve a safe relative `return_to`.
2. Deep-link login: PASS. Valid application-relative destinations restore; external/protocol-relative values fall back to `/app`.
3. Auth flicker: PASS. Background `/me` revalidation keeps the authenticated shell mounted; confirmed 401 clears it and redirects.
4. Dashboard/navigation: PASS. `/app` uses authorized organization/project reads, human-readable names, empty states and canonical links.
5. Account/logout: PASS. Account menu is reachable from the shared shell; deep-route logout invalidates the server session.
6. Legacy migration: PASS for the supported route matrix; legacy organization/project/account/invitation paths redirect to canonical `/app/...` destinations.
7. Accessibility/responsive: PASS at reference widths with skip navigation, visible focus, minimum primary control targets and reduced-motion handling.
8. Visual regression: PASS with deterministic Dashboard fixture reads so prior E2E data creation cannot change screenshot height/content.
9. Map regression safety: PASS, including the post-benchmark Fit-All race that previously left map state at `empty`; Fit All now waits for visible-layer metadata to settle and synchronously publishes the fitted viewport.

### Review / convergence notes

A separate post-test diff review checked route migration, session/auth-loss behavior, tenant-data freshness, user-facing localization, technical-ID exposure, Map renderer lifetime and E2E fixture isolation. No unresolved blocking findings remain.

Known non-blocking follow-ups:

- split the large web bundle by route/workbench;
- keep direct Google raster URLs dev-preview only until an approved Maps Platform/licensing path is selected;
- R002 SC-013 still requires its separately defined uncoached human evidence and is not claimed by this frontend child slice.

**Spec 016 convergence result: PASS for implementation and automated acceptance evidence.**
