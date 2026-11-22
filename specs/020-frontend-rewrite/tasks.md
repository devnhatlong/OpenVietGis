# Tasks: 020 Frontend Rewrite
All tasks open. Paths are planned implementation paths. No code changes in kit initialization.

## Phase 1 — Setup and baseline
- [ ] T001 Inventory every 001–019 requirement, route, API and capability with evidence in specs/020-frontend-rewrite/coverage.md.
- [ ] T002 Capture current browser screenshots, baseline performance, build ID and UX findings in specs/020-frontend-rewrite/baseline.md.
- [ ] T003 Compare GIS/CAD and Mobbin patterns (when available), run Product Design audit and create screen map/prototype Figma; record IDs in specs/020-frontend-rewrite/design.md.
- [ ] T004 Review side-by-side deployment and route/cutover ADR in docs/adr/ADR-015-frontend-rewrite.md.
- [ ] T005 Create isolated apps/web-next/package.json and CI scripts, define real test commands in specs/020-frontend-rewrite/quickstart.md.
## Phase 2 — Foundations
- [ ] T006 Implement one token/primitives/icon system and state matrix in apps/web-next/src/ui/.
- [ ] T007 Implement typed SDK, error boundary, protected query/cache isolation and Session.accountId/Session.status per data-model.md in apps/web-next/src/app/.
- [ ] T008 Establish hub/studio/field shell routes and ProjectContext.organizationId/ProjectContext.projectId per data-model.md in apps/web-next/src/shells/.
- [ ] T009 Define real fixtures and Playwright baseline harness in tests/e2e/frontend-next/.
## Phase 3 — US1 Authentication
- [ ] T010 [US1] Test login/register/verify/reset/return/logout/expiry/403 in tests/e2e/frontend-next/auth.spec.ts.
- [ ] T011 [US1] Review provider registration/reset/verification capability and secure configuration in apps/api/openvietgis_api/adapters/http/auth.py and stage realm configuration; contract gap only.
- [ ] T012 [US1] Implement branded auth entry, session transitions and account menu in apps/web-next/src/features/auth/.
## Phase 4 — US2 Project/team
- [ ] T013 [US2] Test two-team isolation, create project and invitation lifecycle in tests/e2e/frontend-next/team.spec.ts.
- [ ] T014 [US2] Implement project hub/team switching/create screens in apps/web-next/src/features/project/.
- [ ] T015 [US2] Review and implement server invitation email/list/resend as needed; Invitation.email, Invitation.role, Invitation.status and MailDelivery.status, MailDelivery.dedupeKey per data-model.md in apps/api/openvietgis_api/adapters/http/invitations.py and mail adapter.
- [ ] T016 [US2] Implement team member/invite state UI and safe link resume in apps/web-next/src/features/team/.
- [ ] T017 [US2] Test mail sink, dedupe, revoke, identity binding and audit in tests/integration/ and tests/e2e/frontend-next/team.spec.ts; configure verified sender only in stage secret store.
## Phase 5 — US3 Workstation
- [ ] T018 [US3] Build desktop dock, command registry, map engine bridge in apps/web-next/src/shells/studio/ and apps/web-next/src/integrations/.
- [ ] T019 [US3] Implement layer and selected feature state; WorkspaceSession.selection and WorkspaceSession.saveState per data-model.md in apps/web-next/src/features/layers/ and apps/web-next/src/features/inspect/.
- [ ] T020 [US3] Implement edit/save/undo/conflict and CAD precision flows with Command.capability per data-model.md in apps/web-next/src/features/editing/ and apps/web-next/src/features/cad/.
- [ ] T021 [US3] Test add/toggle/reorder/select/edit/save/reopen and CAD precision against real fixtures in tests/e2e/frontend-next/studio.spec.ts.
## Phase 6 — US4 GIS tools and data
- [ ] T022 [US4] Implement catalog/CRS/import/export and external sources in apps/web-next/src/features/data/.
- [ ] T023 [US4] Implement query/processing/cartography job flows using existing contracts in apps/web-next/src/features/jobs/.
- [ ] T024 [US4] Implement collaboration/review/history in apps/web-next/src/features/collaboration/.
- [ ] T025 [US4] Verify result records, formats, CRS, job failure and permission in tests/e2e/frontend-next/gis-tools.spec.ts.
## Phase 7 — US5 Plugin/field
- [ ] T026 [US5] Implement ModuleManifest.slot per data-model.md via generic module host in apps/web-next/src/features/plugin/.
- [ ] T027 [US5] Port 019 UI with module isolation in modules/house_numbering/frontend/ and validate roadmap acceptance in tests/e2e/frontend-next/house-numbering.spec.ts.
- [ ] T028 [US5] Implement field shell/offline with isolated actor scope in apps/web-next/src/shells/field/; test reconnect in tests/e2e/frontend-next/field.spec.ts.
## Phase 8 — US6 Quality
- [ ] T029 [US6] Implement UIPreference.scope per data-model.md, theme and keyboard behavior in apps/web-next/src/ui/ and apps/web-next/src/app/.
- [ ] T030 [US6] Review all key screens against approved design; snapshot desktop/tablet/mobile and all state variants in tests/e2e/frontend-next/visual.spec.ts.
- [ ] T031 [US6] Test contrast, keyboard/navigation, accessibility and interaction/performance budgets in tests/e2e/frontend-next/quality.spec.ts.
## Phase 9 — US7 Migration/acceptance
- [ ] T032 [US7] Preserve legacy routes and test safe redirects, permissions and unsaved guard in tests/e2e/frontend-next/migration.spec.ts.
- [ ] T033 [US7] Build and compare staging legacy/v2 artifacts using real API; record rollback rehearsal in specs/020-frontend-rewrite/release-evidence.md.
- [ ] T034 [US7] Complete coverage rows and reconcile all blockers with prior specs in specs/020-frontend-rewrite/coverage.md.
## Phase 10 — Convergence
- [ ] T035 Run root CI, new package tests, security/secret scans and browser evidence; update specs/020-frontend-rewrite/checklists/requirements.md.
- [ ] T036 Obtain owner visual/functional review and cutover approval; record release/rollback plan in specs/020-frontend-rewrite/release-evidence.md.
- [ ] T037 Only after approval perform versioned rollout and monitor in infra/; rollback if failed. Keep legacy until acceptance.

## Dependencies and execution
T001–T005 → T006–T009 → US1 → US2 → US3. US4 and US5 can proceed against finalized SDK/command contracts without editing same files; US6 runs from foundation onward; US7 and convergence after all. MVP: real identity + team + project hub + map read/selection. Release: all mandatory prior capabilities, not MVP alone. No production mail/cutover as part of docs.
