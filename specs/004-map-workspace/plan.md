# Implementation Plan: Map Workspace

**Branch**: integration/004-on-verified-main | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)
Parent: [R004](../../ROADMAP.md#r004). Verified dependency c5cc5a9; design reconciliation [research.md](research.md).

## Summary
Deliver one Core desktop map per Project: bounded actual geometry, layer order/visibility/basic style, synchronized stable-ID selection/table/inspector, explicit shared Save/reopen, conflicts and lost-ack reconciliation. Accepted MapLibre engine sits behind MapEngine. Keep transient camera/active Layer/selection separate. Grid needs no external service. No import/edit/query/cartography/module expansion.

## Technical Context
**Language/Version**: Python3.14 baseline; TypeScript6; Node26.
**Primary Dependencies**: current FastAPI/Pydantic/SQLAlchemy, React19/TanStack Query/Vite; pinned MapLibre eligible under existing pnpm policy.
**Storage**: existing PostgreSQL/PostGIS, additive map configuration/revision/operation tables with current tenant RLS proof; no new datastore.
**Testing**: pytest real restricted-runtime integration/migrations/failure injection; Vitest/tsc/eslint; real Playwright+Keycloak; full exact-SHA CI and independent review.
**Target Platform**: local/self-host Linux API, desktop browser1280×900; Windows development toolchain.
**Project Type**: existing web platform.
**Performance Goals**: 10000 feature fixture,100 measured trials after5 warmups, p95 usable open≤3s and select-inspector≤1s. Profile in research/quickstart.
**Constraints**: max32 layers, finite geographic view,1000 features/20000positions/2MiB viewport,100 selected IDs and bounded detail concurrency4,2s SQL timeout; actual partial status; current authorization each operation; no implicit CRS.
**Scale/Scope**: trusted R003 reference source adapter, XY Point/LineString/Polygon, supported direct4326 edges, one map per Project.

## Constitution Check
Before and after design: PASS with no requested deviations.
- Platform/module isolation: Core-only workflow and renderer-neutral boundary.
- Open data: R003 documented logical read interfaces retained; export remains R005.
- Tenant: current R002 proof, permissions, service ceilings, CSRF, composite ownership/RLS and denial tests.
- Spatial: explicit source/response/display CRS, accepted direct operations, independent controls.
- Version/audit: separate immutable map revisions with prior/new safe configuration evidence, atomic audit, actor-bound operation receipt/CAS.
- Capabilities/commands: registry independent of UI; actual render/style support advertised only once implemented.
- Engine boundary: MapLibre only inside adapter; UI uses MapEngine.
- Complete workflow: save/reopen/restart/partial/revoke/recovery covered; human criterion remains honestly open.

## Project Structure
Documentation: plan/research/data-model/quickstart/contracts/tasks in specs/004-map-workspace/.
Backend: apps/api/openvietgis_api/domains/maps/; adapters/http/maps.py; adapters/persistence/map_repository.py; additive Alembic revision; scoped viewport in spatial adapter/domain. Root owns shared contracts/migrations/wiring.
SDK: packages/client-sdk/src/maps.ts and tests; mandatory generated map schema integration with existing generator and drift guards.
Web: apps/web/src/features/map/ (state, commands, engine, MapLibre adapter, workspace); Project route link.
Tests: apps/api/tests/{unit,contract,integration}/maps; tests/e2e/map-workspace.spec.ts; performance acceptance.
No wholesale stale branch merge.

## Delivery and integration
Freeze design after independent review, generate tasks via tracked resolver, validate traceability. Test-first backend configuration/viewport/renderer-state, then integrate isolated worker commits, real browser and benchmark. Run full mandatory CI on exact clean source commit; no duplicate dispatch. Independent review and convergence before verified main promotion. Preserve other worktrees and original R002 WIP. Human SC009 and R002 SC013 prevent external acceptance claims.

## Complexity Tracking
No Constitution violation. Additive map domain is required because shared map configuration is a different revision domain from catalog/content/schema.
