---
description: "Dependency-ordered implementation tasks for R003"
---

# Tasks: Spatial Catalog & CRS (R003)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts](contracts/catalog-semantics.md), [quickstart.md](quickstart.md).

**Baseline**: verified main 64f00e6 (R002 integrated for internal scope). All runtime tasks are initially unchecked; research observations are not runtime acceptance. Do not start runtime before independent design review. Tests first, prove red before implementing (unless static verification), then prove green using isolated test DB. All paths repository-root relative except named feature documents (under specs/003-spatial-catalog-crs).

**Format**: T### sequential; [P] tasks may run in parallel within their phase after prerequisites, on different files/worktrees; [US#] follows spec story. Shared files must have a single owner at a time.

## Phase 1: Setup

**Goal / independent test**: Confirm baseline, tools, reproducible environment.

- [X] T001 Verify clean baseline, Graphify graph and dependency versions, record isolated DB config in specs/003-spatial-catalog-crs/quickstart.md; no runtime coding until exact design review passes.
- [X] T002 Verify the approved explicit PostGIS pipelines and all published controls against pinned image digest, verify actual library APIs with Context7; record evidence in specs/003-spatial-catalog-crs/research.md.
- [X] T003 [P] Extend OpenAPI validation and generation in tools/check_contracts.py and packages/client-sdk/package.json for contracts/spatial-catalog-api.yaml, retaining every R002 contract and output check.
- [X] T004 [P] Add domain package scaffold apps/api/openvietgis_api/domains/spatial/__init__.py and test file skeletons in apps/api/tests/{unit,contract,integration,performance}/spatial; maintain existing modular boundary.

---

## Phase 2: Foundational

**Goal / independent test**: Blocking: database, auth and domain invariants before feature endpoints.

- [X] T005 [P] Add prerequisite unit tests for stable IDs, revision/canonical manifest and typed values in apps/api/tests/unit/spatial/test_domain.py.
- [X] T006 [P] Add migration/RLS tests with restricted role, missing/wrong project context and pooled connection checkout in apps/api/tests/integration/spatial/test_migration_rls.py.
- [X] T007 Implement DataSource identity, lifecycle, explicit state, provenance and catalog/content/schema revision types in apps/api/openvietgis_api/domains/spatial/domain.py; cite data-model.md DataSource.id, DataSource.organization_id, DataSource.project_id, DataSource.name, DataSource.kind, DataSource.reference_key, DataSource.fixture_version, DataSource.manifest_digest, DataSource.source_asset_id, DataSource.lifecycle, DataSource.validation_state, DataSource.validation_reason, DataSource.catalog_revision, DataSource.content_revision, DataSource.schema_revision, DataSource.created_at, DataSource.updated_at, DataSource.retired_at.
- [X] T008 Implement typed SourceField, ReferenceFeature and geometry/extent validation primitives in apps/api/openvietgis_api/domains/spatial/domain.py per data-model.md SourceField.organization_id, SourceField.project_id, SourceField.source_id, SourceField.field_id, SourceField.name, SourceField.ordinal, SourceField.type, SourceField.nullable, SourceField.schema_revision; ReferenceFeature.organization_id, ReferenceFeature.project_id, ReferenceFeature.source_id, ReferenceFeature.feature_id, ReferenceFeature.attributes, ReferenceFeature.geometry, ReferenceFeature.geometry_state, ReferenceFeature.content_revision, ReferenceFeature.schema_revision; DataSource.schema_state, DataSource.source_crs, DataSource.stored_crs, DataSource.geometry_family, DataSource.dimensions, DataSource.feature_count_state, DataSource.feature_count, DataSource.extent_state, DataSource.extent.
- [X] T009 Implement Layer and CatalogChange invariant types in apps/api/openvietgis_api/domains/spatial/domain.py per data-model.md Layer.id, Layer.organization_id, Layer.project_id, Layer.source_id, Layer.name, Layer.lifecycle, Layer.layer_revision, Layer.created_at, Layer.updated_at, Layer.retired_at; CatalogChange.id, CatalogChange.organization_id, CatalogChange.project_id, CatalogChange.resource_type, CatalogChange.resource_id, CatalogChange.source_id, CatalogChange.layer_id, CatalogChange.actor_type, CatalogChange.actor_id, CatalogChange.operation, CatalogChange.created_at, CatalogChange.prior_revision, CatalogChange.new_revision, CatalogChange.changes, CatalogChange.actor_display_snapshot, CatalogChange.audit_event_id.
- [X] T010 [P] Define immutable native CRS definitions/axis/unit/projection metadata and direct-edge registry interfaces in apps/api/openvietgis_api/domains/spatial/crs.py per data-model.md CRS Definition / Transformation Profile, needed by US1 validation; do not advertise any runtime transform as operational before US5 controls pass.
- [X] T011 Define query/command ports with verified scoped actor context, lifecycle, revision and transactional audit requirements in apps/api/openvietgis_api/domains/spatial/ports.py.
- [X] T012 Create 0006 migration apps/api/migrations/versions/0006_spatial_catalog.py with composite FKs for all five entities, check/unique constraints and deterministic C-collation feature ordering; implement all data-model.md cited field constraints from T007–T009; RLS ENABLE/FORCE and non-owner runtime grants including append-only changes; add UNIQUE(organization_id,id) to audit.audit_events and same-org composite CatalogChange.audit_event_id FK, preserving R002 policies; verify downgrade/upgrade.
- [X] T013 Implement project-bound transaction-local RLS context helper in apps/api/openvietgis_api/adapters/persistence/rls.py after verified tenant/project authorization; no R002 policy rewrite; test fail closed and reset.
- [X] T014 Implement shared spatial repository transaction and scope guard in apps/api/openvietgis_api/adapters/persistence/spatial_repository.py; lock org→project→source→layer; all queries scoped, no raw public storage references.
- [X] T015 Implement canonical manifest revision hashing, CAS and safe changes/audit persistence routines in apps/api/openvietgis_api/domains/spatial/service.py and apps/api/openvietgis_api/adapters/persistence/spatial_repository.py per data-model.md DataSource.catalog_revision, DataSource.content_revision, DataSource.schema_revision, Layer.layer_revision, CatalogChange.prior_revision, CatalogChange.new_revision, CatalogChange.changes; integrate R002 audit event atomically.
- [ ] T016 Implement internal trusted fixture registry and deterministically generated scope rows in apps/api/openvietgis_api/adapters/persistence/spatial_fixtures.py per data-model.md DataSource.reference_key, DataSource.fixture_version, DataSource.manifest_digest, ReferenceFeature.feature_id, ReferenceFeature.attributes, ReferenceFeature.geometry; separate definition registry from project materialization; include positive native 3857/4756/5899 plus independent negative fixtures from the frozen controls/profile before US1 registration validation; ensure narrow HVS-only 4756/4326 controls are separate from wider controls for successful 5899 page operations.
- [ ] T017 Run foundational domain and real restricted-role migration/RLS tests via tools.run_with_test_database; record in specs/003-spatial-catalog-crs/quickstart.md.

---

## Phase 3: US1 — Discover a trusted spatial source (P1)

**Goal / independent test**: Independent test: authorized register and inspect all fixtures, expected states and source metadata (SC-001).

- [ ] T018 [P] [US1] Contract tests for source registration, list/detail, rename/correction/retire and errors in apps/api/tests/contract/test_spatial_catalog.py using contracts/spatial-catalog-api.yaml.
- [ ] T019 [P] [US1] Integration tests for complete expected fixture metadata including positive native 3857/4756/5899 and empty source/unknown/conflicting/Z/M/mixed/unsupported family/null/empty geometry/invalid/axis and out-of-domain fixtures, bad key, duplicate key, independent correction, rollback in apps/api/tests/integration/spatial/test_sources.py.
- [ ] T020 [US1] Implement full reference validation and native metadata calculation in apps/api/openvietgis_api/adapters/persistence/spatial_fixtures.py per data-model.md DataSource.schema_state, DataSource.source_crs, DataSource.stored_crs, DataSource.geometry_family, DataSource.dimensions, DataSource.feature_count_state, DataSource.feature_count, DataSource.extent_state, DataSource.extent, DataSource.validation_state, DataSource.validation_reason and SourceField/ReferenceFeature invariants; reject silent coercion.
- [ ] T021 [US1] Implement registration and source list/detail repository methods in apps/api/openvietgis_api/adapters/persistence/spatial_repository.py; scoped keyset list, exact metadata and atomic binding once per reference_key.
- [ ] T022 [US1] Implement source command service register, rename, correct declared CRS by independent evidence, retirement guard and CAS in apps/api/openvietgis_api/domains/spatial/service.py; data-model.md DataSource.lifecycle, DataSource.catalog_revision, DataSource.content_revision, DataSource.schema_revision, DataSource.retired_at and CatalogChange.operation.
- [ ] T023 [US1] Implement source endpoints in apps/api/openvietgis_api/adapters/http/spatial.py; current project.read/edit/manage, R002 error semantics and explicit validation; wire router into apps/api/openvietgis_api/main.py.
- [ ] T024 [US1] Implement SDK methods and scoped typed request handling in packages/client-sdk/src/spatial.ts, export from packages/client-sdk/src/index.ts and regenerate packages/client-sdk/src/generated/spatial-catalog.ts.
- [ ] T025 [US1] Implement source catalog inspection and registration/metadata controls in apps/web/src/features/spatial/SpatialCatalogPage.tsx and existing apps/web/src/app/router.tsx; no map, source connections or file upload.
- [ ] T026 [US1] Verify US1 fixture provenance/count/extent/schema/CRS and rollback tests in apps/api/tests/integration/spatial/test_sources.py; record SC-001 evidence location.

---

## Phase 4: US2 — Create and inspect a Layer (P1)

**Goal / independent test**: Independent test: two Layers share one source and retiring a Layer preserves others (SC-002). Depends US1.

- [ ] T027 [P] [US2] Contract tests for Layer create/list/detail, rename, retire and explicit capabilities in apps/api/tests/contract/test_spatial_layers.py.
- [ ] T028 [P] [US2] Real PostgreSQL integration tests for two-layer shared rows, duplicate names, cross-project link even dual-authorized, stale and concurrent source retire/create in apps/api/tests/integration/spatial/test_layers.py.
- [ ] T029 [US2] Implement same-scope Layer persistence and source dependency check under source lock in apps/api/openvietgis_api/adapters/persistence/spatial_repository.py per data-model.md Layer.source_id, Layer.lifecycle, Layer.layer_revision.
- [ ] T030 [US2] Implement lifecycle/CAS and capability support/availability/authorization distinction in apps/api/openvietgis_api/domains/spatial/service.py per data-model.md Layer.name, Layer.lifecycle, Layer.layer_revision, Layer.retired_at and CatalogChange.operation.
- [ ] T031 [US2] Implement Layer HTTP routes and nested bounded source metadata in apps/api/openvietgis_api/adapters/http/spatial.py and SDK in packages/client-sdk/src/spatial.ts.
- [ ] T032 [US2] Implement Layer listing/detail and create/rename/retire controls in apps/web/src/features/spatial/SpatialCatalogPage.tsx; unsupported operations not actionable.
- [ ] T033 [US2] Verify US2 multi-Layer storage, capability, source retirement and no cross-link tests in apps/api/tests/integration/spatial/test_layers.py; record SC-002.

---

## Phase 5: US3 — Read a spatial reference dataset correctly (P1)

**Goal / independent test**: Independent test: complete pinned pagination, typed detail, stale conflicts (SC-003, SC-008). Depends US1/US2.

- [ ] T034 [P] [US3] Contract tests for page/detail shapes, limit, pins, optional geometry, native response and unsupported requests in apps/api/tests/contract/test_spatial_features.py.
- [ ] T035 [P] [US3] Integration tests for complete 10k deterministic IDs and independently expected values, null/empty/decimal/timestamp, no duplicates, detail equality, empty page and unavailable reads in apps/api/tests/integration/spatial/test_features.py.
- [ ] T036 [P] [US3] Controlled fixture refresh/stale-pin and concurrent read/mutation tests in apps/api/tests/integration/spatial/test_pinned_reads.py.
- [ ] T037 [US3] Implement stable typed serialization/geometry envelope in apps/api/openvietgis_api/domains/spatial/service.py per data-model.md ReferenceFeature.attributes, ReferenceFeature.geometry, ReferenceFeature.geometry_state, ReferenceFeature.feature_id and SourceField.field_id, SourceField.type, SourceField.nullable.
- [ ] T038 [US3] Implement consistent scoped feature page/detail reads via C-collation keyset limit+1, reject nonexisting scoped continuation ID, exact pins and source/layer availability under consistent snapshot in apps/api/openvietgis_api/adapters/persistence/spatial_repository.py per data-model.md ReferenceFeature.content_revision, ReferenceFeature.schema_revision and DataSource.content_revision, DataSource.schema_revision.
- [ ] T039 [US3] Implement test-only fixture refresh with atomic revision update and metadata rename unaffected pins in apps/api/openvietgis_api/adapters/persistence/spatial_fixtures.py and service; data-model.md DataSource.catalog_revision, DataSource.content_revision, DataSource.schema_revision, SourceField.schema_revision, ReferenceFeature.content_revision, ReferenceFeature.schema_revision.
- [ ] T040 [US3] Wire native read API and SDK in apps/api/openvietgis_api/adapters/http/spatial.py and packages/client-sdk/src/spatial.ts with explicit 409 stale and distinct unavailable/missing errors.
- [ ] T041 [US3] Implement paged attribute and stable-ID detail inspector in apps/web/src/features/spatial/SpatialCatalogPage.tsx with protected query scope and stale retry without silently replacing feature selection.
- [ ] T042 [US3] Implement independent API-only consumer in apps/api/tests/contract/test_spatial_consumer.py and verify SC-003/SC-008 with no physical details or R004 runtime.

---

## Phase 6: US4 — Preserve tenant boundaries and trace changes (P1)

**Goal / independent test**: Independent test: no protected data/mutations, complete attributable evidence (SC-005/006). Security foundations already mandatory; depends US1–3 endpoints.

- [ ] T043 [P] [US4] Test direct ID substitutions and wrong Project across each API path, current grants and membership/credential ceiling/revocation as human and applicable machine actor in apps/api/tests/integration/spatial/test_authorization.py.
- [ ] T044 [P] [US4] Test archived/deleted Project, suspended Org, workspace move, stale grants and credential race in apps/api/tests/integration/spatial/test_lifecycle_security.py.
- [ ] T045 [P] [US4] Test atomic actor/revision/diff audit, mutation failure injection and rollback, concurrent CAS and append-only runtime grants in apps/api/tests/integration/spatial/test_change_evidence.py.
- [ ] T046 [US4] Implement project-scoped history list/continuation and safe immutable evidence serialization in apps/api/openvietgis_api/adapters/persistence/spatial_repository.py and apps/api/openvietgis_api/adapters/http/spatial.py per data-model.md CatalogChange.id, CatalogChange.resource_type, CatalogChange.resource_id, CatalogChange.source_id, CatalogChange.layer_id, CatalogChange.actor_type, CatalogChange.actor_id, CatalogChange.actor_display_snapshot, CatalogChange.audit_event_id, CatalogChange.operation, CatalogChange.created_at, CatalogChange.prior_revision, CatalogChange.new_revision, CatalogChange.changes; no raw secrets/physical details.
- [ ] T047 [US4] Review and enforce all entry point permission mappings, lifecycle and human CSRF/service current credential checks in apps/api/openvietgis_api/adapters/http/spatial.py and R002 tenant_access integration; do not alter granted role vocabulary.
- [ ] T048 [US4] Verify migration and runtime RLS composite ownership, project-GUC fail-closed, pooled GUC reset, no access from other org/project, no cross-project source reference in apps/api/tests/integration/spatial/test_migration_rls.py.
- [ ] T049 [US4] Implement change history SDK/UI view in packages/client-sdk/src/spatial.ts and apps/web/src/features/spatial/SpatialCatalogPage.tsx; safe old/new, actor, time, scoped access.
- [ ] T050 [US4] Execute negative matrix and atomic evidence tests in apps/api/tests/integration/spatial; record SC-005 and SC-006 evidence in quickstart.md.

---

## Phase 7: US5 — Inspect Vietnam-first coordinate reference support (P2)

**Goal / independent test**: Independent test: explicit profile discovery and every supported edge vs independent control; reject all unsupported (SC-004). Depends US1–3.

- [ ] T051 [P] [US5] Freeze independent DMS/projected numbers and analytic formula fixtures from vn2000-control-evidence.md and research.md in apps/api/tests/fixtures/spatial_controls.py (no transform-derived targets).
- [ ] T052 [P] [US5] Unit tests for registry profiles, eight exact directed edges, definition-only UTM, XY conventions, finite/bounds/zone/provenance/geometry validation in apps/api/tests/unit/spatial/test_crs.py.
- [ ] T053 [P] [US5] Integration tests for explicit pipeline operation identity and forward/inverse independent control tolerances, domain boundary/WGS out-of-region, mixed/unsupported family, Z/M/empty geometry and unsupported requests, native storage unchanged in apps/api/tests/integration/spatial/test_crs_controls.py.
- [ ] T054 [US5] Implement immutable CRS Definition/Transformation Profile registry in apps/api/openvietgis_api/domains/spatial/crs.py according to data-model.md CRS Definition / Transformation Profile; authority/code, native/application axes, units, parameters, applicability, disposition, direct source/target, operation/tolerance/evidence; no arbitrary/custom CRS.
- [ ] T055 [US5] Implement approved PostGIS pipelines only with explicit output SRID in apps/api/openvietgis_api/adapters/persistence/spatial_repository.py per research.md; validate domain and all vertices before/after, reject unsupported requests, no fallback; native geometry unchanged.
- [ ] T056 [US5] Reuse positive native 3857/4756/5899 and independent axis/domain fixtures from T016 in apps/api/tests/integration/spatial/test_crs_controls.py; verify ready/stored/source CRS and optional transformed geometry response, including rejected direct edges/out-of-area.
- [ ] T057 [US5] Implement CRS registry endpoint, supported response_crs on page/detail, transformation evidence and error semantics in apps/api/openvietgis_api/adapters/http/spatial.py; SDK and inspector display in packages/client-sdk/src/spatial.ts and apps/web/src/features/spatial/SpatialCatalogPage.tsx.
- [ ] T058 [US5] Execute all eight directed control tests and explicit unsupported matrix, record runtime versions/digest and tolerances with measured errors in specs/003-spatial-catalog-crs/quickstart.md; no survey-grade accuracy claim.

---

## Phase 8: Polish & convergence

**Goal / independent test**: Cross-cutting acceptance, independently reviewed exact CI.

- [ ] T059 [P] Implement restart/interrupted registration atomic retry integration tests in apps/api/tests/integration/spatial/test_restart.py (SC-009).
- [ ] T060 [P] Implement restricted-role warmed ≥100-sample benchmark list/detail/page100 (native and supported transformed), 10k rows and recorded p50/p95/max/runtime/image/revisions in apps/api/tests/performance/test_spatial_benchmark.py (SC-007).
- [ ] T061 [P] Add Playwright catalog workflow/permission/stale and safe surfaces tests in tests/e2e/spatial-catalog.spec.ts; extend protected query and security-surface checks without weakening R002.
- [ ] T062 Validate API SDK generated contract exactness, all unit/contract/integration/E2E/benchmarks, migration cycle, architecture/docs/scope, secret scanning via package.json pnpm validate; update Graphify for actual code changes.
- [ ] T063 Record per-FR/SC evidence and measured thresholds in specs/003-spatial-catalog-crs/quickstart.md and ROADMAP.md; independent reviewer inspects security, CRS, lifecycle, contracts and exact candidate; fix findings before approval.
- [ ] T064 Run exact final-commit CI and full Spec Kit convergence; document all tasks and gate verdict in specs/003-spatial-catalog-crs/tasks.md and ROADMAP.md; promote verified main only with independent review and full green CI. Do not assert R002 SC-013 measured or ship externally.

---

## Dependencies and execution order

- Phase 1 → Phase 2 (blocking all stories). Keep existing R002 runtime permissions and behavior green. Phase 2 security, transaction/audit foundations cannot be deferred until US4.
- US1 → US2 → US3; US4 tests/evidence extend all delivered routes, US5 extends feature reads and native profiles. US4 and US5 independent test preparation may run in parallel after US3; coordinate implementation on shared API/service/repository files.
- Phase 8 depends on all five stories. No scope expansion or promotion with failing SC. R004 depends on R003 convergence.

### Parallel execution examples

- Setup: contract-tool generation checks and domain scaffold on separate files.
- Foundation: unit primitive tests and migration/RLS tests independently; CRS definition metadata owned separately from domain types; migration and RLS helper after model finalized.
- US1: source contract and database fixture test drafting on separate files; one writer for source service/repo.
- US2: Layer contract and dependency-race tests in parallel.
- US3: feature contract, complete pagination, pinned read race tests in parallel; integrate sequentially.
- US4: negative authorization matrix, lifecycle and immutable evidence test suites in parallel.
- US5: independent numeric fixtures, registry tests, PostGIS control tests in parallel; do not derive expected values from transformed results.
- Polish: restart, performance, browser suites prepared in separate worktrees; integrate and run all together.

## Implementation strategy

MVP is US1 after all foundations: source registration, trusted metadata and explicit invalid states. Validate US1 independently. Deliver shared Layer lifecycle next, pinned stable reads next, then full security/evidence and approved CRS operations. Each increment preserves R002 gates. No production release and no renderer, importer, external connector, editor or exporting feature. Exact final commit requires independent review, full CI and all nine measured acceptance criteria; retain R002 deferred external human timing gate.

## Acceptance trace

| SC | Task phase evidence |
| --- | --- |
| SC-001 | US1 registration/metadata/fixture tests |
| SC-002 | US2 shared Layer/source dependency tests |
| SC-003 | US3 full pagination/pin/detail tests |
| SC-004 | US5 independent directed transformation and negative matrix |
| SC-005 | Foundation RLS + US4 cross-org/project/actor matrix |
| SC-006 | Foundation audit + US4 transactional evidence tests |
| SC-007 | Phase 8 restricted-role HTTP benchmark |
| SC-008 | US3 independent consumer |
| SC-009 | Phase 8 restart/failure/retry suite |

FR-001–038 trace: US1 (001–008, 012–013, 017, 019–020), US2 (009–011, 021–023, 038), US3 (024–028), US4 + Foundation (029–037, 001–002), US5 (012–018, 020). See validation scenarios in quickstart.md.
