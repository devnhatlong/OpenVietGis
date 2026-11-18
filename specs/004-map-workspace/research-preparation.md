# R004 Map Workspace — Clarification and Research Preparation

**Date:** 2026-11-18

**Phase:** Spec Kit Specify only; non-normative preparation for later planning.

**Owner:** R004 isolated workstream.

**Base commit:** `98a65ebc6db7167bd8e6fbf07c1f7e94e375fb9d` (the committed R002 plan baseline; runtime is not accepted).

**Parent:** [R004 in ROADMAP.md](../../ROADMAP.md#r004)

**Spec:** [spec.md](spec.md)

## Clarification decisions

Owner accepted all four recommended options in the Grill. These choices define the draft scope, not a final plan or implementation.

| Topic | Accepted choice | Explicit deferral |
| --- | --- | --- |
| Map/workspace | One logical map per Project; desktop GIS layer tree, central map, toolbar/command search, inspector, attribute table | Multiple independent maps/tabs, print layouts, field/mobile workspace |
| Save semantics | Explicit Save of project-shared arrangement/order/visibility/basic style/approved basemap/intentionally selected default viewpoint; applicable Project edit authority, attributable revision and conflict detection; personal transient exploration separate | Per-user persistent preferences, continuous shared autosave, collaborative cursor/state synchronization |
| Basemap | Local blank/grid default; optional licensed, explicitly configured online provider with attribution, no tenant payload/credentials egress; notice of unavoidable viewport tile-coordinate disclosure, disabled on sensitive profiles | Arbitrary registered services, paid-provider assumptions, raster/OGC ecosystem |
| Selection | Active-layer click single/multi using clear modifier, selection through table, synchronized map/table/inspector; read-only attributes | Lasso/rectangle, spatial/attribute query builder and advanced filtering (R007), feature editing (R006) |

An explicit action such as `Set default viewpoint` distinguishes a deliberately chosen saved startup view from the current incidental camera. Saving layer order or visibility must not accidentally rewrite the saved startup camera. A viewer can locally preview presentation within authorized data but cannot save the shared configuration. Changes to shared AND personal state must never be conflated.

Online basemaps cause geographically indexed requests even if tenant source data is never transmitted; those coordinates can reveal areas being viewed. No URLs, request parameters, headers or body may include protected tenant/project/layer identifiers, private features, their attributes or internal credentials. Profiles where viewed geography is protected must keep the local background enabled and external basemap disabled. The optional mode is not a promise of absolute viewport secrecy.

## Existing accepted constraints

- [Constitution](../../.specify/memory/constitution.md): explicit tenant ownership and server enforcement; no silent CRS inference; attributable material changes; capability-driven commands and engine-agnostic boundaries; workflow before parity.
- [ADR-003](../../docs/adr/ADR-003-react-spa.md): React/TypeScript desktop SPA; separate server state from local workspace state; mobile/field is a distinct shell.
- [ADR-005](../../docs/adr/ADR-005-postgis.md): PostGIS spatial source of truth, explicit ownership; no browser-direct physical storage access.
- [ADR-006](../../docs/adr/ADR-006-layer-capabilities.md): MapEngine boundary, first renderer MapLibre, optional deck.gl augmentation only if justified; commands use explicit capability, not source-specific switch statements. **Engine choice is already accepted, not a new Grill question.**
- [ADR-007](../../docs/adr/ADR-007-changeset.md): short transactions and attributable revision semantics; shared configuration history remains distinct from editing feature geometry/attributes.
- [ADR-008](../../docs/adr/ADR-008-module-architecture.md): internal module framework later; Core must work without modules; do not commit premature public SDK.
- [ADR-014](../../docs/adr/ADR-014-explicit-tenant-context-rls.md): explicit Organization, current actor/permission context, transaction-local tenant isolation and non-bypass runtime authorization.

No runtime implementation, new engine choice, new permission-role bundle, physical database representation or API schema is selected here.

## Dependencies and evidence status

R002 is only a committed planning baseline in this branch. Its planned API, Organization/Workspace/Project model, roles, permission registry, lifecycle and error conventions are relevant, but not treated as accepted runtime. Archived Projects remain inspectable subject to current authorized access; ordinary shared mutation is denied. Project scope is evaluated under the explicit Organization and applicable inherited/direct grant model. R004 must reconcile against the actual converged R002 behavior.

R003 is a parallel research/specify workstream. Its draft, observed via the separate local worktree `C:\code\openvietgis-r003` and branch `003-spatial-catalog-crs` (at `04c9ad7` during R004 setup), proposes:

- distinct DataSource, Layer and optional SourceAsset identities, explicit revision and capabilities;
- reference data with typed attributes, geometry family, schema, count, extent and unambiguous CRS;
- bounded stable pagination of a reference source, with explicit stale revision behavior and tenant-scoped access;
- no prematurely advertised render/edit/export/offline capability;
- WGS84/Web Mercator plus specifically validated Vietnam-first coordinate profiles as the initial approach.

This is a draft dependency annotation only. R004 has **not** merged R003 or invented its accepted contracts. R004 can establish user-level behavior before that contract stabilizes, but must not independently create an alternate catalog, Layer identity model, CRS registry, feature identity or data-ownership definition.

## Contract questions to reconcile after R003 convergence

| Boundary | Required information for R004 | Planning action (not performed yet) |
| --- | --- | --- |
| Tenant/Project | Explicit current actor, owner Organization, Project scope, lifecycle/permissions and non-leaking errors | Reuse accepted R002 authority outcome rather than hard-coding role names. Confirm exact scope/permission action for shared map saving. |
| Catalog & capability | Stable Layer and DataSource references, distinct catalog/Layer vs source content/schema revisions; metadata, extent state and geometry/CRS/profile; technical capability vs lifecycle vs current actor authority | Confirm which supported reference sources may actually be rendered; R004 extends render capability only once complete. |
| Bounded rendering | Explicit current tenant/Project + Layer/source + content/schema revision, bounded viewport/CRS, maximum feature or response budget, deterministic handling of out-of-order or partial results, status of generalized/limited output | Implement the R004 responsibility to extend accepted R003 basic reads with a bounded viewport contract. Do not force unbounded loading; advanced query remains R007. Exact viewport normalization/wrap/error and output format are plan decisions. |
| Feature detail & selection | Scoped stable Layer/source/feature identity, stable field IDs, distinct content/schema revisions, typed attributes, optional geometry and detail CRS, page/selection consistency | Reuse R003 authorized stable-ID detail reads for out-of-view/non-renderable features; selected render geometry is not authoritative feature storage. Confirm overlap hit-selection/tolerance and stale-revision invalidation, never silently substitute another feature/field. |
| Shared configuration | One Project Map, ordered Layer references, visible/basic style, approved basemap, explicit default viewpoint, independent shared config revision, attributable changed-value evidence and a save operation identity | Agree representation, expected revision conflict, atomic commit, access rechecked on reconcile, retry identity/idempotent outcome recovery, invalid reference handling before FE/BE proceed. A pre-commit failure preserves prior revision; lost acknowledgement after commit reconciles authoritative saved state without duplicate commit. |
| MapEngine | Logical layer IDs and renderer-neutral view/selection/presentation and failure semantics | Use an adapter around the Accepted first engine; store logical state separately from renderer-native handles. Avoid speculative abstractions. |
| Personal state | Session-local camera, selection, active Layer, inspector/table focus and unsaved changes | Clear or safely isolate on tenant/Project switch, permission denial and source-revision invalidation. Do not persist tenant data offline. |
| Commands | Stable registered command ID, context, named technical capability, lifecycle and explicit required permission action, non-sensitive unavailable reason | First operations: zoom/fit, reorder/visibility, inspect/select/clear, Save and set startup viewpoint. Reconcile accepted R002 action mapping and R003 eligibility; keep UI entry points consistent; never treat capability as authority or role names as authorization. No module SDK promise. |

## Reference benchmark preparation

Proposed initial user-facing tests (not measured results):

- Align with the accepted R003 dataset: licensed/provenanced reference, point/line/polygon coverage as supported, independently verified extent and CRS/control points, deterministic IDs and attribute/null fixtures. Draft target 10,000 total features across geometry families, not an unsupported promise of all 10,000 features visible at once.
- Record local environment (CPU/RAM, browser/version, viewport pixel dimensions, renderer-support availability, deployment/network profile), feature distribution and layer count, warm-up procedure, camera positions and reference outputs. Identify normal and budget-limited viewports separately.
- Minimum 100 trials for map-open and select-to-inspector flows, target 95% within 3 seconds and 1 second respectively in their agreed normal fixtures. Budget-limited cases must visibly report limitation; no optimization that silently misrepresents data or weakens authorization.
- Obtain independent geometry/extent/control-point evidence from accepted R003 fixture. Confirm selection identity when two Layers reference the same source, overlap geometry, invalid or empty geometry, pagination beyond first page and source revision invalidation.
- Real browser and runtime test against explicit authorized and denied contexts. Check default no external requests, approved optional basemap request metadata/attribution, network failure to fallback, and disabled online service for protected viewport profiles.
- Include shared state checks: two actors, two tenant contexts, viewer vs editor, explicit default viewpoint vs transient camera (saving order/visibility after pan/zoom must not replace designated viewpoint), conflict, archived Project, restart and denied direct access. Inject failures before commit and after commit/before acknowledgement; reconcile authoritative revision and repeat the same save intent without duplication, reject differing intent under the same identity, recheck current authority. Verify prior/new revision and safe changed-value evidence. Prevent stale delayed results and stale caches crossing current context.
- Usability target: four of five GIS-capable first-time participants independently open, inspect and reopen in five minutes with known fixture/credentials. Do not count agents completing scripted UI tests as actual first-time-user evidence.

## Scope guard

In scope: R004 only; local desktop map, catalog reference arrangement, supported basic styling/rendering, explicit CRS status, feature read/selection/table/inspector, durable shared configuration, minimal capability-aware commands, permission/recovery boundaries. Out: file ingest/export R005, changeset editing R006, advanced query R007, processing R008, cartography output R009, broad external-source R010, collaborative workflows R011, CAD R012, field/offline R013, module framework R014, production/commercial R015.

## Gates and next action

Prerequisite acceptance is intentionally open. Do not create R004 `plan.md`, `tasks.md`, final implementation contracts, runtime changes or convergence claims until R003 is accepted and reconciled with the converged R002 contracts. At that point, compare this draft against the actual upstream diff, finalize prerequisite reference profile and contract semantics, obtain review, update the roadmap stage and proceed through Spec Kit Plan. The integrating owner must transplant only this feature's `specs/004-*` documents onto current verified main after R002/R003 promotion; the historical branch includes R002/shared ROADMAP history and must not be merged wholesale. Reconcile shared roadmap traceability separately. No shared branch or other feature's active state is changed by this research.
