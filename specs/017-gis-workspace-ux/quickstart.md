# Quickstart Validation: GIS Workspace UX

## Prerequisites

- Parent R004 exact accepted integration baseline identified and this child slice reconciled onto it.
- R002-FE shared shell/tokens available or explicit ownership agreed.
- Supported Node 26 runtime and frozen dependencies.
- R004 reference Project/Map/Layer fixtures and real browser acceptance environment.
- Optional external basemap disabled for deterministic baseline.

## Validation scenarios

### 1. Desktop workspace structure

Open a prepared Project at 1440×900 and 1280×900.

**Expected**: Layer panel, Map, Inspector and Attribute Table are understandable in one workspace; no primary UUID/roadmap-code clutter; no page-level horizontal overflow.

### 2. Empty Project

Open a Project with no Map Layer references.

**Expected**: Clear empty state with Add Data guidance; no fake feature/extent.

### 3. Add existing Layer

Use Add Data with catalog Layers both absent and already on the Map.

**Expected**: Only valid add candidates are actionable; duplicate behavior is explained; adding/removing a Map reference does not mutate catalog source data.

### 4. Layer controls without drag

For two or more Layers:
- toggle visibility;
- set active;
- Move Up/Move Down;
- Zoom to Layer;
- remove Map reference.

**Expected**: All actions work through keyboard-accessible controls; Layer order/visibility matches parent R004 behavior.

### 5. Map ↔ Table ↔ Inspector synchronization

Select from map, then table; change page; collapse/reopen table; resize panels.

**Expected**: Current valid selection/focus agrees across surfaces and panel layout changes do not reset Map camera/valid selection.

### 6. Save state

Change a shared Map property, pan/zoom/select, save, then trigger stale/failed/unresolved fixtures.

**Expected**: Only shared changes set dirty state; success appears only after authoritative confirmation; conflicts/unresolved outcomes remain honest.

### 7. Technical Details

Use ordinary workspace with drawer closed, then open it.

**Expected**: UUIDs/revisions are absent from primary chrome but available, scoped and labeled in the drawer. Scope change clears stale technical content.

### 8. Responsive modes

Test 1440, 1280, 1024, 768, 414 and 375 px widths.

**Expected**:
- desktop full layout;
- tablet collapsible/switchable panels;
- mobile basic Map/Layer/feature inspection;
- no accidental page-wide horizontal overflow.

### 9. Accessibility

- Keyboard-only controls including non-drag Layer reorder.
- Named Map region.
- Visible focus.
- Attribute Table/Inspector text alternative.
- Reduced-motion behavior.
- Dialog/drawer focus return.

### 10. Visual regression

Capture deterministic Empty Workspace, Workspace with data, Layer panel, Table open/closed, Technical drawer open/closed, Dirty and Saved states using local/grid map background or masked map pixels.

### 11. Parent regression

Run all existing R004 unit/browser/performance suites before accepting this UX slice.

**Expected**: No parent authorization, CRS, bounded read, selection, save/conflict or performance regression.

## Required commands

From the exact supported runtime:

- `pnpm --filter @openvietgis/web test`
- `pnpm --filter @openvietgis/web lint`
- `pnpm --filter @openvietgis/web typecheck`
- `pnpm --filter @openvietgis/web build`
- targeted and existing R004 Playwright suites
- full root validation before convergence

Record exact parent R004 commit, child commit, browser/runtime and fixture profile.

## Dependency Gate Evidence — 2026-11-21

- Parent R004 convergence commit: `990e73502889f976068c1c96f122a8a684c2b9b7`
- Parent R004 verified code SHA recorded by that checkpoint: `a993542cefa91ea499f4ba8f19ced3e8dcd31513`
- Current integration base inherited by the child: `c6d449fc0ead93e259b79b87e63c1c894bd16c93`
- Current Spec 016 shared-shell convergence: `4d17350`
- Ancestry check: `990e735` is an ancestor of the current child worktree.
- Node: `v26.13.1`; pnpm: `12.21.0`; Playwright: `1.65.1`.

### Parent R004 accepted baseline

Original R004 automated evidence recorded at the accepted checkpoint:

- web/SDK validation: 44/44 web tests, 58/58 SDK tests;
- Python: 533/533;
- integration/performance: 263;
- browser E2E: 16/16 plus bootstrap 1/1;
- SC007 10,000-feature benchmark:
  - map open p95 2,254.5 ms (budget <=3,000 ms),
  - select-to-inspector p95 384.2 ms (budget <=1,000 ms),
  - external requests 0.

Current pre-017 regression baseline after Spec 016 convergence:

- web: 60/60 unit tests;
- SDK: 62/62;
- Python: 538;
- integration/performance: 273 PASS, 1 SKIP;
- browser E2E: 31/31 plus bootstrap 1/1;
- current production build:
  - JS 1,610.22 kB raw / 447.17 kB gzip,
  - CSS 126.88 kB raw / 22.64 kB gzip,
  - MapLibre worker 519.54 kB;
- measured 10,000-feature regression profile:
  - map open p95 ~2,700 ms,
  - select-to-inspector p95 ~346 ms,
  - external requests 0.

R004 SC009 (five first-time GIS-capable users) remains an external human acceptance obligation and is not claimed by this child implementation.

## US3 synchronization evidence — 2026-11-21

- Accessible Map summary is derived from the current authorized Project/Layer/selection state and is exposed as the textual companion to the named Map region.
- Browser acceptance keeps camera and selection stable across panel collapse and keyboard resize: PASS.
  - selected point-000001;
  - collapsed Layer, Inspector and Attribute Table panels;
  - reopened/resized the Layer panel with keyboard separator controls;
  - camera summary remained unchanged;
  - Inspector focus and selected checkbox remained synchronized after reopening.
- The current bounded Attribute Table renders exactly 100 body rows at the accepted page limit. This stays at the UI UX Pro Max virtualization threshold and is bounded by the parent R004 read contract, so no windowing dependency is introduced in this slice.

## US3 synchronization evidence — 2026-11-21

- Web typecheck PASS.
- Web unit tests: 75/75 PASS after adding AccessibleMapSummary.
- Browser scenario `keeps camera and selection stable across panel collapse and keyboard resize`: PASS.
- Camera summary remains identical while Layer, Inspector and Attribute Table panels collapse/reopen and while the Layer separator is resized by keyboard.
- Focused feature `point-000001`, checkbox selection and accessible map summary remain synchronized after layout-only changes.
- Attribute Table renders exactly 100 bounded records on the reference page, matching the accepted parent read limit. No virtualization dependency is introduced because the simultaneous DOM row count does not exceed 100.

## US4 save-state evidence — 2026-11-21

- Web typecheck PASS; web unit tests 84/84 PASS.
- Save indicator explicitly distinguishes clean, dirty, saving, saved, conflict, failed and unresolved outcomes.
- Browser save-state group: 3/3 PASS:
  - transient camera/selection/layout changes remain clean;
  - shared visibility change becomes dirty and blocks route navigation until the user stays or discards;
  - authoritative save clears dirty and navigation proceeds;
  - lost acknowledgement remains unresolved until operation reconciliation;
  - concurrent editor save produces an explicit CAS conflict and reload returns to the authoritative revision.
- Deterministic workspace visual baselines for dirty, saved and conflict states: 3/3 PASS and repeated without snapshot regeneration.

## US4 save-state evidence — 2026-11-21

- Save indicator maps shared configuration state to clean, dirty, saving, saved, conflict, failed and unresolved without changing parent CAS/revision semantics.
- Web unit suite passed with explicit save-indicator coverage; known 4xx validation failures map to failed, 409 to conflict, authorization loss to failed/denied presentation, and ambiguous transport/server outcomes remain unresolved.
- Targeted browser acceptance PASS:
  - transient camera zoom, feature selection and panel layout changes keep save state clean;
  - shared Layer visibility change becomes dirty;
  - dirty navigation opens the in-app leave warning and can be cancelled;
  - authoritative save becomes saved and navigation then proceeds without warning;
  - lost acknowledgement remains unresolved until reconciliation;
  - stale revision remains conflict until reload.
- Deterministic visual suite PASS both when snapshots were generated and on a subsequent no-update run.
- Save-state snapshots cover dirty, saved and conflict in addition to empty/populated workspace baselines.

## US5 technical-details evidence — 2026-11-21

- Technical metadata is removed from primary Map chrome, Layer rows and the normal Inspector surface.
- Unit coverage verifies scoped Organization/Project/Map IDs, active Layer/Source IDs, content/schema revisions, CRS facts and capability availability mapping without inventing data when there is no active Layer.
- Browser acceptance PASS:
  - primary context does not display Organization, Project or Map UUIDs;
  - Technical Details drawer shows only currently supplied authorized map/layer facts;
  - closing the drawer returns focus to the invoking control;
  - navigating to another Project while the drawer is open unmounts/closes the drawer and the old Project ID is absent from the new primary context.
- Deterministic visual suite covers Technical Details closed/open states. After removing a colliding duplicate snapshot name, visual generation and a subsequent no-update run both passed 4/4.

## US6 responsive/accessibility evidence — 2026-11-21

- Workspace responsive matrix browser acceptance PASS at 1440, 1280, 1024, 768, 414 and 375 px.
  - 1440/1280 resolve to desktop;
  - 1024/768 resolve to tablet;
  - 414/375 resolve to mobile basic-viewer mode;
  - no page-wide horizontal overflow was observed at any reference width;
  - Map remains visible when mobile sheets are collapsed.
- MapLibre adapter explicitly keeps keyboard navigation enabled and exposes visible NavigationControl zoom/compass controls.
- Accessibility browser acceptance PASS:
  - named Map region and synchronized textual summary are present;
  - MapLibre canvas is keyboard-focusable and Arrow-key movement changes the camera;
  - Layer reorder works through Move Up/Down keyboard controls without drag;
  - panel separators expose keyboard-adjustable separator semantics;
  - Attribute Table remains the textual feature alternative;
  - Technical Details close returns focus to the invoking control;
  - visible focus remains present;
  - reduced-motion media preference resolves workspace transition/animation duration to effectively zero.
