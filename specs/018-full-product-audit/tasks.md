# Tasks: Full Product Audit R001–R015
**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [evidence contract](contracts/evidence-contract.md), [quickstart.md](quickstart.md).
Audit tasks only; implementation fixes require separately scoped child specs. All evidence must be pinned to exact candidate and isolated fixtures.

## Phase 1: Setup
- [x] T001 Resolve Spec Kit templates and create artifacts under specs/018-full-product-audit/ (FR-001).
- [x] T002 Pin candidate and prior main in specs/018-full-product-audit/research.md; record Candidate.commit and Candidate.branch per data-model.md (FR-001).
- [x] T003 Record preliminary source-only status and eight hypotheses in specs/018-full-product-audit/status-matrix.md and gaps.md (FR-003, FR-012); do not treat as runtime acceptance.
- [x] T004 Verify isolated VPS worktree and actual owner/active frontend state; record Candidate.environment per data-model.md in specs/018-full-product-audit/evidence/baseline.md (FR-001, FR-015).

## Phase 2: Foundational
- [x] T005 Inspect original specs and approved draft decision register, recover canonical R006–R015 requirements into specs/018-full-product-audit/evidence/requirements.md; record requirement provenance and approval state (FR-002).
- [x] T006 Create requirement-level register per data-model.md RequirementEvidence.requirement_id, RequirementEvidence.status, RequirementEvidence.artifacts, RequirementEvidence.candidate in specs/018-full-product-audit/evidence/requirements.md; map 15/15 groups (FR-002, FR-003, SC-001).
- [ ] T007 Verify version pins, frozen dependency policy and disposable DB/test realm/artifact guard; record commands and environment in specs/018-full-product-audit/evidence/baseline.md (FR-011).
- [ ] T008 Prepare synthetic GIS fixtures and independent oracle; record format/CRS control/checksum, expected results and source in specs/018-full-product-audit/evidence/fixtures.md (FR-004, FR-011).
- [ ] T009 Check redaction and production isolation before any test, record gate in specs/018-full-product-audit/evidence/baseline.md (FR-011, SC-006).

## Phase 3: US1 — Establish actual baseline (P1)
- [ ] T010 [US1] Review main/candidate/UX branch ancestry and integration ownership in specs/018-full-product-audit/evidence/baseline.md (FR-001, FR-015).
- [ ] T011 [US1] Enumerate actual routes, UI commands, storage effects and existing evidence by requirement in specs/018-full-product-audit/evidence/requirements.md; mark missing or draft scope, never infer acceptance (FR-002, FR-003, FR-013).
- [ ] T012 [US1] Check static capability assertions against independent evidence, update specs/018-full-product-audit/status-matrix.md (FR-013, SC-002).

## Phase 4: US2 — M1 Core verification (P1)
- [ ] T013 [US2] Run exact baseline foundation, migration, restart and health validation; save results under specs/018-full-product-audit/evidence/r001.md (FR-004).
- [ ] T014 [US2] Exercise real OIDC session, project hierarchy, two-tenant deny, revocation in apps/api/tests/integration/identity and tenancy; record specs/018-full-product-audit/evidence/r002.md and pending SC-013 human gate (FR-004).
- [ ] T015 [US2] Verify R003 CRS controls, catalog pins, scope and benchmark from specs/003-spatial-catalog-crs; record specs/018-full-product-audit/evidence/r003.md (FR-004).
- [ ] T016 [US2] Verify layer tree, map pan/select/table/extent/save/reopen and stale/revoked behavior via tests/e2e/map-workspace.spec.ts; record specs/018-full-product-audit/evidence/r004.md and pending SC-009 human gate (FR-004).
- [ ] T017 [US2] Import and export supported GeoPackage, GeoJSON, zipped Shapefile profiles, independently compare count/schema/CRS/geometry and failure/retry; record specs/018-full-product-audit/evidence/r005.md plus SC-008 manual gate (FR-004).
- [ ] T018 [US2] Execute complete M1 browser scenario and collect independent artifact proof in specs/018-full-product-audit/evidence/m1.md (FR-004, SC-003).

## Phase 5: US3 — M2 Workbench verification (P1)
- [ ] T019 [US3] Reproduce edit, snapping, validation, conflict, revert and persisted attribution through apps/api/tests/integration/m2/test_r006_r009_real.py; independently test graphical UI availability; record specs/018-full-product-audit/evidence/r006.md (FR-005).
- [ ] T020 [US3] Compare R007 attribute/spatial filter results and saved query against known geometry/selection; test scope and error cases; record specs/018-full-product-audit/evidence/r007.md (FR-005).
- [ ] T021 [US3] Compare Buffer/Clip/Dissolve output geometry and CRS against independent oracle, verify durable job lifecycle, cancellation/retry; record specs/018-full-product-audit/evidence/r008.md (FR-005).
- [ ] T022 [US3] Download real PNG/PDF, inspect map/legend/scale/layout and independent dimensions/content; record specs/018-full-product-audit/evidence/r009.md (FR-005).
- [ ] T023 [US3] Run browser workbench workflow in tests/e2e/platform-m2-m3.spec.ts plus missing edit/UI cases, record specs/018-full-product-audit/evidence/m2.md (FR-005, SC-003).
- [ ] T024 [US3] Compare frozen UI with R016/R017 current candidate, identify integration retest without touching active UX work; record specs/018-full-product-audit/gaps.md (FR-015).

## Phase 6: US4 — Advanced and team verification (P2)
- [ ] T025 [US4] Probe controlled WMS/WFS/other approved provider fixtures; require real fetch/render/query, deny SSRF, report absent operations explicitly in specs/018-full-product-audit/evidence/r010.md (FR-006).
- [ ] T026 [US4] Exercise independent user contexts review/comment/history and concurrent stale changes or rebase; record specs/018-full-product-audit/evidence/r011.md (FR-009).
- [ ] T027 [US4] Validate DXF round-trip in independent reader, supported entity mapping/loss and COGO controls; reject unsupported DWG explicitly, record specs/018-full-product-audit/evidence/r012.md (FR-007).
- [ ] T028 [US4] Verify real offline dataset, network loss/local edit or missing UI, restart, sync and conflict/revocation; record specs/018-full-product-audit/evidence/r013.md (FR-008).
- [ ] T029 [US4] Test two independent modules and lifecycle, disabled-module Core usability and tenant/permission boundaries via tests/modules/test_reference_modules.py; record specs/018-full-product-audit/evidence/r014.md (FR-010).
- [ ] T030 [US4] Test health, actual effective entitlements/capabilities, isolated backup/restore through tools/backup_restore.py, deployment profile and recovery; record specs/018-full-product-audit/evidence/r015.md, separate static flags (FR-010, FR-013).
- [ ] T031 [US4] Execute M3 selected team workflow and record results with negatives and scope limits in specs/018-full-product-audit/evidence/m3.md (FR-009, FR-010, SC-003).

## Phase 7: US5 — Gaps and release gate (P1)
- [ ] T032 [US5] Convert observations to reproducible findings and rank using data-model.md Gap.id, Gap.requirement_id, Gap.severity, Gap.reproduction, Gap.retest, Gap.owner_scope, Gap.status in specs/018-full-product-audit/gaps.md (FR-012, SC-004).
- [ ] T033 [US5] Create/adjust scoped child Spec Kit artifacts for accepted blockers, coordinate dependencies and ownership in specs/018-full-product-audit/gaps.md; do not invent new approved scope (FR-012, FR-015).
- [ ] T034 [US5] Reconcile all requirement evidence/status and roadmap stage in specs/018-full-product-audit/status-matrix.md, preserving raw failures and blocked human gates (FR-003, FR-013, SC-002).
- [ ] T035 [US5] Obtain required R002/R004/R005 human observations and release-scope decision; if unavailable mark external release blocked in specs/018-full-product-audit/evidence/acceptance.md (FR-014, SC-005).
- [ ] T036 [US5] Run independent code/security/requirements review, full exact candidate validation and convergence; record data-model.md AcceptanceDecision.candidate, AcceptanceDecision.scope, AcceptanceDecision.review, AcceptanceDecision.result, AcceptanceDecision.manual_gate in specs/018-full-product-audit/evidence/acceptance.md (FR-014, SC-005).
- [ ] T037 [US5] Verify all release blockers closed or scope explicitly deferred, no false static acceptance; advise promotion separately, no deployment under audit in specs/018-full-product-audit/evidence/acceptance.md (FR-013, FR-014, SC-004).

## Phase 8: Polish
- [ ] T038 Verify FR/SC traceability, all evidence revision pins, no secret or production data, and exact artifact checks; record audit conclusion in specs/018-full-product-audit/evidence/acceptance.md (FR-011, SC-006).

## Dependencies and execution order
Setup -> T004 and foundational T005–T009 -> US1 baseline -> M1 -> M2 -> M3 -> US5 and closure. Independent tests may be parallelized only with distinct isolated fixtures and evidence files (no duplicate coordinator). US5 gap logging can start with each verified finding, but acceptance waits for retests and all required gates. MVP = evidence-backed inventory and repeatable M1, not a new runtime deployment.
