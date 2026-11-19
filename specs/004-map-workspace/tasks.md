# Tasks: Map Workspace

Input: [spec](spec.md), [plan](plan.md), [research](research.md), [model](data-model.md), [contract](contracts/map-workspace.md).
Design prerequisite independently reviewed 2026-11-19; implementation evidence is recorded only when actually verified. Full feature acceptance includes SC009 human exercise.

## Phase 1: Setup
- [ ] T001 Record dependency acceptance/design review and current ownership in specs/004-map-workspace/upstream-contract-reconciliation.md.
- [ ] T002 Pin eligible MapLibre dependency and frozen lockfile in apps/web/package.json and pnpm-lock.yaml without policy bypass.
- [ ] T003 Freeze exact API/schema generation and field constraints in specs/004-map-workspace/contracts/map-workspace.md; trace every model field through tasks below.

## Phase 2: Foundation
- [ ] T004 Implement validated configuration/domain values in apps/api/openvietgis_api/domains/maps/domain.py covering [ProjectMap.id/organization_id/project_id/configuration_revision/configuration/updated_at; Configuration.layers/basemap/default_viewpoint; LayerReference.layer_id/visible/style; Viewpoint.longitude/latitude/zoom/bearing/pitch/crs](data-model.md#configuration), numeric/type/size/uniqueness bounds and deterministic identity.
- [ ] T005 Define transaction-bound map port and save service in apps/api/openvietgis_api/domains/maps/ports.py and service.py covering [SaveOperation.operation_id/actor_type/actor_id/request_hash/committed_revision/map_id/created_at and MapRevision fields](data-model.md#saveoperation), fresh permissions,actor receipt,CAS and no-op/replay ordering.
- [ ] T006 Add map schema/migration in apps/api/migrations/versions/ with BIGINT revision,composite ownership FK,unique map/op/revision,RLS proof and append-only grants per [ProjectMap and MapRevision](data-model.md#projectmap).
- [ ] T007 Implement repository in apps/api/openvietgis_api/adapters/persistence/map_repository.py with atomic configuration+receipt+revision+audit,Org→Project→map locking and rollback/restart.
- [ ] T008 Test domain/replay and strict HTTP contracts first in apps/api/tests/unit/maps/ and apps/api/tests/contract/test_maps.py.
- [ ] T009 Wire map HTTP/error adapters and registered schemas in apps/api/openvietgis_api/adapters/http/maps.py,errors.py,main.py and tools/check_contracts.py.
- [ ] T010 Verify migration upgrade/downgrade,RLS/runtime non-owner,history immutability and FK scope in apps/api/tests/integration/maps/test_migrations.py.

## Phase 3: US1 Open and navigate (P1)
Goal: actual bounded geometry and usable Core grid workspace.
Independent test: fresh empty and saved point/line/polygon Project,pan/zoom/fit,no external network; FR001–008/013–016,SC001/006/010.
- [ ] T011 [US1] Test exact viewport/pins/transform/extent/output/work budgets in apps/api/tests/integration/maps/test_viewport.py for [ViewportSnapshot request/response fields](data-model.md#viewportsnapshot).
- [ ] T012 [US1] Implement bounded viewport/display-extent domain+repository in apps/api/openvietgis_api/domains/maps/viewport.py and adapters/persistence/map_viewport.py; correct display-space intersection and approved CRS provenance.
- [ ] T013 [US1] Add scoped viewport/extent HTTP contracts in apps/api/openvietgis_api/adapters/http/maps.py with strict finite bbox,1000feature/20000position/2MiB/2s budgets and truthful limits.
- [ ] T014 [US1] Extend exact render/style capability semantics and regressions in apps/api/openvietgis_api/domains/spatial/service.py and specs/003-spatial-catalog-crs/contracts/catalog-semantics.md only for implemented supported profile.
- [ ] T015 [P] [US1] Add typed scoped SDK map/viewport/extent calls and tests in packages/client-sdk/src/maps.ts and tests/maps.test.ts; mandatory generated schema integration.
- [ ] T016 [US1] Define MapEngine and MapLibre adapter in apps/web/src/features/map/engine.ts and maplibre-engine.ts; logical IDs,4326-only boundary,grid,clear/destroy/error and deterministic hits.
- [ ] T017 [US1] Add protected desktop workspace route/surfaces and explicit loading/empty/partial/unavailable/CRS states in apps/web/src/features/map/MapWorkspace.tsx and app/router.tsx.
- [ ] T018 [US1] Implement pan/zoom/fit-layer/fit-all with approved full extents in apps/web/src/features/map/workspace.ts.
- [ ] T019 [US1] Run real browser grid/no-network/open/navigation/CRS checks in tests/e2e/map-workspace.spec.ts and record actual results in quickstart.md.

## Phase 4: US2 Arrange Layers (P1)
Goal: local arrangement preserves source data; FR009–016,SC002.
Independent test: two Layers sharing source,add/remove/reorder/hide/style without data mutation.
- [ ] T020 [US2] Test local order/visibility/style/active/unavailable behavior in apps/web/src/features/map/workspace.test.ts.
- [ ] T021 [US2] Implement layer tree/add/remove/order/visibility/style controls in apps/web/src/features/map/LayerTree.tsx and workspace.ts using [Configuration and WorkspaceSession](data-model.md#configuration).
- [ ] T022 [US2] Apply deterministic render order/styles and hidden-layer hit exclusion in apps/web/src/features/map/maplibre-engine.ts.
- [ ] T023 [US2] Verify retired/missing reference isolation and unchanged source identities/schema/count/coordinates in apps/api/tests/integration/maps/test_reference_invariants.py.
- [ ] T024 [US2] Exercise layer arrangement/style visually in tests/e2e/map-workspace.spec.ts.

## Phase 5: US3 Select and inspect (P1)
Goal: same pinned stable selection in map/table/inspector; FR017–024/032–033,SC003/005.
Independent test: overlap,modifier,pages,out-of-view detail,typed null/empty/zero,context/pin invalidation.
- [ ] T025 [US3] Test selection key/generation/stale/denial/page invariants in apps/web/src/features/map/selection.test.ts covering [WorkspaceSession/Selection fields](data-model.md#workspacesession--selection).
- [ ] T026 [US3] Implement bounded session selection reducer in apps/web/src/features/map/selection.ts with full actor/tenant/Layer/source/pin key and focused stable ID.
- [ ] T027 [US3] Implement paged typed attributes and stable-ID inspector in apps/web/src/features/map/AttributeTable.tsx and FeatureInspector.tsx reusing accepted R003 reads.
- [ ] T028 [US3] Connect deterministic map click/modifier/table highlight and fit-selection through authorized detail geometry in apps/web/src/features/map/MapWorkspace.tsx.
- [ ] T029 [US3] Clear engine/table/inspector/pending results on denial/context/pin change and guard delayed responses in apps/web/src/features/map/workspace.ts.
- [ ] T030 [US3] Verify cross-tenant/current credential/revoke/archive/deleted scope for all new reads in apps/api/tests/integration/maps/test_authorization.py.
- [ ] T031 [US3] Run browser selection/pages/overlap/out-of-view/stale/revocation cases in tests/e2e/map-workspace.spec.ts.

## Phase 6: US4 Save and reopen (P1)
Goal: durable attributable state with reliable conflicts/recovery; FR025–034/038,SC004/005.
Independent test: two actors save/reopen,explicit viewpoint preservation,CAS,precommit rollback,lostack after later commit,restart,denials.
- [ ] T032 [US4] Test atomic save/replay/CAS/no-op/actor and service ceiling matrix in apps/api/tests/integration/maps/test_saves.py.
- [ ] T033 [US4] Test precommit failure/postcommit lostack/restart/concurrent save/revoke and receipt lookup in apps/api/tests/integration/maps/test_recovery.py.
- [ ] T034 [US4] Test minimal edit-only receipts,current read history and immutable before/after evidence in apps/api/tests/integration/maps/test_history.py.
- [ ] T035 [US4] Complete saved configuration+operation/history SDK and schema guards in packages/client-sdk/src/maps.ts.
- [ ] T036 [US4] Implement explicit Save and preserve/set/clear designated view in apps/web/src/features/map/save.ts and MapWorkspace.tsx.
- [ ] T037 [US4] Implement unresolved outcome/reconcile/same operation/conflict/reload states in apps/web/src/features/map/save.ts and save.test.ts per [WorkspaceSession save status](data-model.md#workspacesession--selection).
- [ ] T038 [US4] Exercise actual save/reopen/two-session/default-viewpoint/lostack/browser recovery in tests/e2e/map-workspace.spec.ts.

## Phase 7: US5 Commands (P2)
Goal: consistent Core capabilities across entry points; FR035–037,SC008.
Independent test: toolbar/context/search/shortcut use same availability/execution; unsupported and denied commands stay unavailable.
- [ ] T039 [US5] Test registry capability/permission/lifecycle/entrypoint parity in apps/web/src/features/map/commands.test.ts.
- [ ] T040 [US5] Implement stable registry in apps/web/src/features/map/commands.ts with separate permission/technical conditions and meaningful reasons.
- [ ] T041 [US5] Connect toolbar/context/search/keyboard to registry in apps/web/src/features/map/CommandBar.tsx and MapWorkspace.tsx.
- [ ] T042 [US5] Verify command parity/Core-only/no unsupported advertisements in tests/e2e/map-workspace.spec.ts.

## Phase 8: Verification and convergence
- [ ] T043 Measure100 open and100 select trials after5 warmups on10000feature reference profile in tests/e2e/map-performance.spec.ts; record raw exact-SHA SC007 environment/pins/p95 in specs/004-map-workspace/evidence/.
- [ ] T044 Run mandatory full root/static/real integration/migration/liveOIDC/browser checks and exact-SHA CI; record results in specs/004-map-workspace/quickstart.md.
- [ ] T045 Independently review runtime/security/contracts/recovery/FR001–038 and SC001–010 traceability in specs/004-map-workspace/checklists/convergence.md.
- [ ] T046 Observe five actual first-time GIS-capable users for SC009 and record outcomes in specs/004-map-workspace/evidence/usability.md; keep open until observed.
- [ ] T047 Refresh untracked Graphify and run Gitleaks/intended-source inventory before public branch push, recording sanitized results in specs/004-map-workspace/quickstart.md.
- [ ] T048 Promote only independently reviewed exact-green accepted source to verified main and update ROADMAP.md and private coordination ledger; distinguish outstanding human evidence explicitly.

## Dependencies and parallel execution
T001–010 establish shared contract/domain/schema. T011–014 viewport can run in separate worktree from map save backend after contract freeze; T015 SDK can run independently from renderer T016 with same frozen shapes. US1→US2→US3 establish protected actual map flow; backend US4 can be implemented concurrently after foundation while UI US4 waits prior UI state. US5 registry integrates existing operations. One owner controls shared wiring,contract,migration,roadmap and CI. Workers never mutate shared test DB. Root cherry-picks reviewed isolated commits only.

MVP is US1 usable Core grid workspace; it is not R004 acceptance. Full implementation requires US1–5 and T043–048, including genuine human observation. No task count is product completion percentage. SpecKit setup-plan/setup-tasks tracked resolvers ran with isolated feature context and no extension hooks.
