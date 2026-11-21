# Research: GIS Workspace UX

## Decision 1 — Dense professional GIS workstation, not a generic dashboard

**Decision**: Use a desktop-first, information-dense workstation: Layer panel left, stable Map center, Inspector right, resizable/collapsible Attribute Table below, commands above. Keep primary controls visually quiet and map/data dominant.

**Rationale**: Grill approved a hybrid product direction: spacious public SaaS surfaces but professional desktop GIS density after authentication. UI UX Pro Max independently classified the product as “GIS / Web Map Dashboard” and recommended a dense, scannable layout.

## Decision 2 — Unified teal/slate visual system

**Decision**: Reuse the product-wide light tokens: teal `#0F766E` for product chrome/focus, slate neutrals, light background/card/border surfaces. Orange `#EA580C` may be used sparingly for selection/emphasis only after contrast checks. Data-layer thematic colors remain independent of UI chrome.

**Rationale**: UI UX Pro Max's GIS recommendation produced exactly this teal/slate palette and warned against rainbow ramps, glass panels over the map and color-only states. Reusing R002-FE tokens prevents a second design system.

## Decision 3 — Typography stays unified with App Shell

**Decision**: Use the shared product sans-serif stack for normal UI, with `ui-monospace` only for technical IDs/coordinates/CRS details. Do not introduce Fira Code/Fira Sans as a second product-wide font family solely because the GIS recommender suggested it.

**Rationale**: Consistency and loading/privacy costs outweigh a small thematic benefit. Technical surfaces can still use monospace locally.

## Decision 4 — Stable Map engine lifetime

**Decision**: Panel layout and table/inspector visibility are UI siblings around a stable Map canvas. Resizing/collapsing panels calls map resize/invalidation as needed but does not recreate the Map engine.

**Rationale**: Recreating the renderer would reset camera, selection/render state and degrade performance. This also satisfies the approved “no flicker/reset” interaction goal.

## Decision 5 — Add Data is one user entry point with capability-aware branches

**Decision**: “Thêm dữ liệu” first offers existing authorized catalog Layers not already on the Map. If an accepted import capability is present, it additionally offers an Import handoff. This child slice does not implement R005 validation/job/publication.

**Rationale**: Users should not need to understand Source vs Layer before completing a basic map task, but ownership of data-ingestion semantics must remain with R005.

## Decision 6 — Layer reorder and resize require non-drag alternatives

**Decision**: Drag may be offered for convenience, but Layer items also expose Move Up/Move Down commands. Resizable panel separators are keyboard-operable where custom resizing is implemented, and collapse presets remain available.

**Rationale**: UI UX Pro Max map/accessibility research flags Dragging Movements as a high-severity issue and recommends buttons/tap-to-move alternatives.

## Decision 7 — Map accessibility uses a region + synchronized textual data

**Decision**: Name the map canvas region, keep keyboard map navigation available, provide
oom controls, and make the synchronized Attribute Table/Inspector the text alternative for feature facts. Do not claim full screen-reader equivalence for spatial visual relationships in the first slice.

**Rationale**: UI UX Pro Max marks Map Text Alternative as critical and recommends a named map region plus text summary/list/table.

## Decision 8 — Table stays bounded before adding virtualization

**Decision**: Preserve parent R004 bounded paging. Do not add a virtualization dependency if only up to 100 rows are simultaneously rendered. If accepted later contracts raise that bound, measure and use windowing rather than rendering thousands of rows.

**Rationale**: UI UX Pro Max recommends virtualization over 100 items, but the parent contract already constrains page size. Avoid premature dependency/complexity.

## Decision 9 — Responsive modes follow the approved product split

**Decision**:
- Desktop ≥1280: full multi-panel workspace.
- Tablet 768–1279: panels collapse/switch while Map remains stable.
- Mobile <768: basic map viewer, Layer visibility and feature detail; advanced desktop parity is excluded.

**Rationale**: This is the exact Grill decision and avoids pretending a dense desktop GIS interface can simply shrink.

## Decision 10 — Technical metadata is secondary

**Decision**: UUIDs, source IDs, revisions, capability diagnostics and raw CRS metadata live in an explicit Technical Details drawer. Normal workspace shows names, user-facing status and only the CRS facts needed for the task.

**Rationale**: Product-owner feedback identified inline UUID/revision clutter as confusing. Support/debug capability remains available without dominating routine work.

## Decision 11 — Deterministic visual tests avoid live tiles

**Decision**: Screenshot tests use the local/grid background or normalize/mask the map-tile region. External Google/Esri imagery is not a visual-regression oracle.

**Rationale**: Third-party tiles are nondeterministic, license-dependent and network-dependent.

## Decision 12 — Parent R004 remains the semantic authority

**Decision**: No new client-owned map configuration, selection, permission, capability or revision semantics are introduced. UI state wraps accepted R004 contracts.

**Rationale**: This is a UX child slice; duplicating domain semantics would violate capability/revision boundaries.

## Dependency reconciliation — 2026-11-21

**Accepted parent checkpoint**: R004 convergence/documentation commit `990e73502889f976068c1c96f122a8a684c2b9b7`, which records verified R004 code SHA `a993542cefa91ea499f4ba8f19ced3e8dcd31513`.

**Current implementation ancestry**: this child worktree descends from `c6d449fc0ead93e259b79b87e63c1c894bd16c93` (`integration/r006-r015-complete`), and `git merge-base --is-ancestor 990e735 HEAD` is true. Therefore the child is not based on the historical `c5cc5a9` scaffold and does not require a destructive rebase onto an older R004-only branch.

**Parent contract reconciliation**:

- Map configuration, configuration revision/CAS, save operation identity, conflict and unresolved acknowledgement semantics remain parent-owned.
- Layer/source identity, content/schema revision pins, capability checks, authorization reads and stale-read behavior remain parent-owned.
- Selection continues to use stable feature IDs and the accepted selection scope key; panel/layout state must not create a second selection model.
- Viewport payloads remain bounded and authoritative; the UX layer must not infer full extents from a partial viewport.
- Existing command IDs remain the parent command surface. Spec 017 may add presentation commands for Add Data/reorder/panels, but may not redefine save/query permission semantics.
- R005 is present in the current integration baseline, so Add Data may expose the canonical Import/Export handoff instead of inventing ingestion behavior.

**Reconciliation adjustments**:

- Current R004 already includes a working `LayerTree`, `AttributeTable`, `FeatureInspector`, command registry and stable MapLibre engine boundary. Spec 017 extends these instead of replacing them.
- A post-R004 regression fix now gates “Fit All” until visible-layer metadata has settled and publishes the fitted viewport synchronously; this is treated as preserved parent behavior because it fixes a renderer timing race without changing domain semantics.
- R004 SC009 remains a separately recorded human usability gate. This child slice does not claim that evidence.

**Shared UI ownership**: Spec 016 is converged in this same worktree at commit `4d17350`, with shared tokens/primitives/AppShell already present under `apps/web/src/ui` and `apps/web/src/app/shell`. Spec 017 will reuse them and will not create a second design system.
