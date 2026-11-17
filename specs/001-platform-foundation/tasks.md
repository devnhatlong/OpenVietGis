# Tasks: Platform Foundation

**Input**: Design documents from `specs/001-platform-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Spec 001 explicitly requires automated unit, integration, architecture, migration, reset-safety,
and browser vertical-slice validation. Test tasks are therefore mandatory.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested as an
independent increment after the shared foundation is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks
- **[Story]**: Maps to a user story in spec.md
- Every task includes an exact target file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the minimal monorepo, runtime manifests, and local PostGIS service required by
all user stories. Do not create empty future GIS services/packages.

- [X] T001 Create the minimal monorepo directories from plan.md in `apps/web/`, `apps/api/`, `packages/client-sdk/`, `modules/`, `tools/`, `tests/e2e/`, and `infra/dev/`
- [X] T002 Initialize root pnpm workspace scripts and runtime constraints in `package.json` and `pnpm-workspace.yaml`
- [X] T003 [P] Initialize the React/TypeScript/Vite web package in `apps/web/package.json`, `apps/web/tsconfig.json`, and `apps/web/vite.config.ts`
- [X] T004 [P] Initialize the typed client package in `packages/client-sdk/package.json` and `packages/client-sdk/tsconfig.json`
- [X] T005 [P] Initialize the Python 3.13 API project and dev/test dependencies in `apps/api/pyproject.toml`
- [X] T006 [P] Configure repository-level TypeScript formatting/lint/typecheck rules in `eslint.config.js` and `tsconfig.base.json`
- [X] T007 [P] Configure Python lint/type/test defaults in `apps/api/pyproject.toml`
- [X] T008 Create the development PostGIS service with health check and development-only defaults in `infra/dev/compose.yaml`
- [X] T009 Create non-secret local configuration examples and ignore rules in `.env.example` and `.gitignore`
- [X] T010 Create root developer scripts for bootstrap, validation, migration, and reset orchestration in `package.json`

**Checkpoint**: Runtime manifests and the real development database dependency exist; no product
semantics or GIS feature has been introduced.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared configuration, application boundaries, migration mechanism, and test
harness required before any user story implementation.

**CRITICAL**: No user story implementation starts until this phase is complete.

### Tests and contracts

- [X] T011 [P] Add an OpenAPI contract validation test for `specs/001-platform-foundation/contracts/foundation-api.yaml` in `apps/api/tests/contract/test_foundation_contract.py`
- [X] T012 [P] Configure Vitest for web/package tests in `apps/web/vite.config.ts` and `packages/client-sdk/package.json`
- [X] T013 [P] Configure Playwright base settings and web/API test startup expectations in `playwright.config.ts`

### Application foundation

- [X] T014 Implement fail-fast API configuration loading with explicit development/test environment markers in `apps/api/openvietgis_api/config.py`
- [X] T015 Implement SQLAlchemy engine/session lifecycle without ORM auto-create in `apps/api/openvietgis_api/adapters/persistence/db.py`
- [X] T016 Configure Alembic to use the application database configuration in `apps/api/alembic.ini`, `apps/api/migrations/env.py`, and `apps/api/migrations/script.py.mako`
- [X] T017 [P] Define common HTTP error/response handling for the foundation API in `apps/api/openvietgis_api/adapters/http/errors.py`
- [X] T018 [P] Create the FastAPI application composition root and versioned router mount in `apps/api/openvietgis_api/main.py`
- [X] T019 [P] Implement typed client transport configuration without hard-coded endpoint URLs in `packages/client-sdk/src/http.ts`

### Architecture and documentation foundation

- [X] T020 Document repository ownership, dependency direction, Core-to-module prohibition, and artifact roles in `docs/architecture.md`
- [X] T021 Create the vertical-module boundary marker and usage rules without implementing a module in `modules/README.md`
- [X] T022 Create the minimal product-neutral OpenVietGIS web shell without readiness or record behavior in `apps/web/src/app/App.tsx`, `apps/web/src/app/FoundationPage.tsx`, and `apps/web/src/main.tsx`

**Checkpoint**: Migrations, configuration, HTTP composition, typed-client transport, architecture
documentation, and test harnesses exist. User stories can now proceed.

---

## Phase 3: User Story 1 — Start a Consistent Development Environment (Priority: P1) 🎯 MVP

**Goal**: A contributor can bootstrap the supported development foundation, start it reproducibly,
and receive clear readiness/failure information without undocumented machine-specific steps.

**Independent Test**: Follow only the repository bootstrap documentation on a clean supported
environment, start the PostGIS dependency and application processes, and observe a healthy
foundation shell; then stop PostGIS and verify readiness clearly reports the missing dependency.

### Tests for User Story 1

- [X] T023 [P] [US1] Add liveness/readiness tests including database-unavailable behavior in `apps/api/tests/integration/test_health.py`
- [X] T024 [P] [US1] Add configuration failure tests for missing required settings and invalid environment markers in `apps/api/tests/unit/test_config.py`

### Implementation for User Story 1

- [X] T025 [US1] Implement `GET /api/v1/health/live` and `GET /api/v1/health/ready` per the foundation contract in `apps/api/openvietgis_api/adapters/http/health.py`
- [X] T026 [P] [US1] Implement typed health/readiness client calls in `packages/client-sdk/src/health.ts`
- [X] T027 [P] [US1] Add foundation readiness presentation to the existing minimal shell in `apps/web/src/app/FoundationPage.tsx`
- [X] T028 [US1] Wire the web shell to the typed readiness client and show explicit ready/not-ready states in `apps/web/src/app/FoundationPage.tsx`
- [X] T029 [US1] Document supported runtimes, bootstrap, startup, port-conflict handling, and dependency failure behavior in `README.md`

**Checkpoint**: US1 is independently demonstrable without the persisted sample-record flow.

---

## Phase 4: User Story 2 — Prove One Complete Vertical Slice (Priority: P1)

**Goal**: Create and retrieve one disposable foundation record through the supported web → client →
HTTP → application → domain → repository → PostgreSQL path, including persistence across API restart.

**Independent Test**: Create a foundation sample record from the web shell, restart the API, and
retrieve the same UUID/label through the supported flow.

### Tests for User Story 2

- [X] T030 [P] [US2] Add domain validation tests for `FoundationSampleRecord.label` using the canonical constraints in `specs/001-platform-foundation/data-model.md#foundationsamplerecord` in `apps/api/tests/unit/test_foundation_domain.py`
- [X] T031 [P] [US2] Add repository integration tests against real PostGIS for create/read/persistence behavior in `apps/api/tests/integration/test_foundation_repository.py`
- [X] T032 [P] [US2] Add HTTP integration tests for create/read/not-found/validation responses defined by `contracts/foundation-api.yaml` in `apps/api/tests/integration/test_foundation_api.py`
- [X] T033 [P] [US2] Add typed-client unit tests for foundation create/read behavior in `packages/client-sdk/tests/foundation.test.ts`
- [X] T034 [P] [US2] Add browser E2E coverage for create → capture UUID → read-back in `tests/e2e/foundation.spec.ts`

### Implementation for User Story 2

- [X] T035 [P] [US2] Implement the domain entity fields `FoundationSampleRecord.id`, `FoundationSampleRecord.label`, `FoundationSampleRecord.created_at`, and `FoundationSampleRecord.updated_at` exactly from `specs/001-platform-foundation/data-model.md#foundationsamplerecord` in `apps/api/openvietgis_api/domain/foundation.py`
- [X] T036 [P] [US2] Define the foundation repository port using `FoundationSampleRecord.id` and persisted entity semantics from `specs/001-platform-foundation/data-model.md#foundationsamplerecord` in `apps/api/openvietgis_api/ports/foundation_repository.py`
- [X] T037 [US2] Create Alembic migration `0001_foundation_sample` implementing `FoundationSampleRecord.id`, `FoundationSampleRecord.label`, `FoundationSampleRecord.created_at`, and `FoundationSampleRecord.updated_at` from `specs/001-platform-foundation/data-model.md#foundationsamplerecord` in `apps/api/migrations/versions/0001_foundation_sample.py`
- [X] T038 [US2] Implement the PostgreSQL repository adapter for the canonical `FoundationSampleRecord` fields from `specs/001-platform-foundation/data-model.md#foundationsamplerecord` in `apps/api/openvietgis_api/adapters/persistence/foundation_repository.py`
- [X] T039 [US2] Implement create/read application use cases and domain validation orchestration in `apps/api/openvietgis_api/application/foundation_service.py`
- [X] T040 [US2] Implement foundation create/read HTTP routes and request/response schemas matching `contracts/foundation-api.yaml` in `apps/api/openvietgis_api/adapters/http/foundation.py`
- [X] T041 [US2] Register foundation routes in the application composition root in `apps/api/openvietgis_api/main.py`
- [X] T042 [P] [US2] Implement typed `FoundationRecord` create/read client operations matching `contracts/foundation-api.yaml` in `packages/client-sdk/src/foundation.ts`
- [X] T043 [US2] Add create/read UI for the disposable sample record and preserve the returned UUID for lookup in `apps/web/src/app/FoundationPage.tsx`
- [X] T044 [US2] Add an automated persistence-restart scenario that executes the create/read path 10 consecutive times in `apps/api/tests/integration/test_foundation_restart.py`

**Checkpoint**: US2 proves the complete persistence path and SC-003 without introducing a real product entity.

---

## Phase 5: User Story 3 — Preserve Architectural Boundaries (Priority: P1)

**Goal**: Contributors can see and automatically enforce the critical rule that Core/platform code
must not depend on vertical modules, while modules may depend on documented public contracts.

**Independent Test**: Run the architecture check against one controlled invalid fixture and one
valid fixture; the invalid Core→module direction fails and the valid module→public-contract direction passes.

### Tests for User Story 3

- [X] T045 [P] [US3] Add controlled valid/invalid architecture fixtures in `tests/architecture/fixtures/valid_module_to_contract/` and `tests/architecture/fixtures/invalid_core_to_module/`
- [X] T046 [P] [US3] Add automated architecture tests covering rejected Core→module imports, accepted module→public-contract dependencies, and successful Core validation when `modules/` is empty or absent in `tests/architecture/test_architecture.py`

### Implementation for User Story 3

- [X] T047 [US3] Implement Core/platform-to-module import and declared-dependency detection with actionable diagnostics in `tools/check_architecture.py`
- [X] T048 [US3] Add the architecture check to the root validation command in `package.json`
- [X] T049 [US3] Document how to classify new top-level code and extend architecture rules in `docs/architecture.md`

**Checkpoint**: The most important platform boundary is both documented and mechanically enforced.

---

## Phase 6: User Story 4 — Understand and Change Architecture Deliberately (Priority: P2)

**Goal**: A new maintainer can distinguish Constitution rules, ADR decisions, specs, and runtime code,
and can supersede a technical decision without rewriting unrelated governance.

**Independent Test**: Using repository documentation only, a reviewer can locate governance and ADRs,
explain why Core cannot depend on vertical modules, and follow the ADR supersession process.

### Tests for User Story 4

- [X] T050 [P] [US4] Add a documentation structure/link check in `tools/check_docs.py` and a timed reviewer navigation exercise requiring a reviewer with no prior repository orientation to locate the Constitution, ADR index, architecture guide, and active Spec 001 within the SC-006 limit in `specs/001-platform-foundation/checklists/reviewer-navigation.md`

### Implementation for User Story 4

- [X] T051 [US4] Extend the ADR index with status/supersession guidance and links to all accepted ADRs in `docs/adr/README.md`
- [X] T052 [US4] Add a concise governance-versus-ADR-versus-spec navigation section in `README.md`
- [X] T053 [US4] Add the documentation structure check to root validation in `package.json`

**Checkpoint**: Architecture governance is discoverable and replaceable technical choices remain outside the Constitution.

---

## Phase 7: User Story 5 — Run Baseline Quality Gates Before Feature Work (Priority: P2)

**Goal**: One documented validation workflow proves static quality, tests, architecture boundaries,
real database migration/integration, browser E2E, reset safety, and absence of production credentials.

**Independent Test**: Run the root validation workflow on an accepted checkout and see all mandatory
categories pass; introduce a known failing test or architecture violation and see the correct category fail.

### Tests for User Story 5

- [X] T054 [P] [US5] Add migration-from-zero integration coverage against real PostGIS in `apps/api/tests/integration/test_migrations.py`
- [X] T055 [P] [US5] Add reset-safety tests proving non-development targets are rejected in `apps/api/tests/unit/test_reset_safety.py`
- [X] T056 [P] [US5] Add a root validation smoke test that verifies mandatory validation categories are invoked in `tools/tests/test_validate_manifest.py`

### Implementation for User Story 5

- [X] T057 [US5] Implement guarded deterministic development reset with explicit environment/database identity checks in `tools/reset_dev.py`
- [X] T058 [US5] Complete the root `validate` and `dev:reset` orchestration scripts with clear category failures in `package.json`
- [X] T059 [US5] Create CI that installs supported runtimes, starts real PostGIS, applies migrations, and runs the same root validation path without production credentials in `.github/workflows/ci.yml`
- [X] T060 [US5] Update `README.md` with the single baseline validation command, expected categories, reset procedure, and common failure diagnostics
- [X] T061 [US5] Execute every scenario in `specs/001-platform-foundation/quickstart.md`, including a clean supported-environment bootstrap timed against SC-001 and the T050 navigation exercise with a reviewer who has no prior repository orientation timed against SC-006, and record measured results/corrections in `specs/001-platform-foundation/quickstart.md` without weakening acceptance behavior

**Checkpoint**: The foundation has one reproducible local/CI quality gate and is ready for convergence review.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, safety, and convergence preparation after all desired user stories are complete.

- [X] T062 [P] Add license/security-safe dependency and secret scanning hooks to CI validation where already available from repository tooling in `.github/workflows/ci.yml`
- [X] T063 [P] Verify `.env.example`, `.gitignore`, and committed fixtures contain no production secrets or private credentials in `.env.example` and `.gitignore`
- [X] T064 [P] Verify no map, GIS editing, production auth, tenant billing, offline field, processing, or House Numbering implementation leaked into Spec 001 source paths listed in `specs/001-platform-foundation/plan.md`
- [X] T065 Run the full root validation workflow and `git diff --check`, then document final implementation validation results in `specs/001-platform-foundation/tasks.md`
- [X] T066 Run `graphify update .` and confirm generated graph output remains excluded from version control via `.gitignore` or repository-local Git exclusion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 — Setup**: starts immediately.
- **Phase 2 — Foundational**: depends on Phase 1 and blocks all user stories.
- **Phase 3 — US1**: depends on Phase 2.
- **Phase 4 — US2**: depends on Phase 2 and can proceed independently of US1 because the neutral web shell is created in Foundational; US2 adds only its record workflow.
- **Phase 5 — US3**: depends on Phase 2 and can proceed in parallel with US1/US2.
- **Phase 6 — US4**: depends on the existing Constitution/ADR artifacts and Phase 2; can proceed in parallel with US1-US3.
- **Phase 7 — US5**: depends on the implemented validation surfaces from US1-US4 and therefore integrates them.
- **Phase 8 — Polish**: depends on all selected user stories.

### User Story Dependencies

- **US1 (P1)**: independent after Phase 2; provides reproducible bootstrap/readiness.
- **US2 (P1)**: independent persistence proof after Phase 2; reuses only the neutral product shell created in Foundational and does not depend on US1 readiness behavior.
- **US3 (P1)**: independent after Phase 2; architecture scanning does not require the sample-record feature.
- **US4 (P2)**: independently validates documentation/governance discoverability.
- **US5 (P2)**: intentionally integrates all preceding checks into the single required quality workflow.

### Within Each User Story

- Tests are written before the implementation they validate and should fail for the intended missing behavior.
- Domain/data definitions precede application services.
- Application services precede HTTP adapters.
- HTTP contract stays aligned with `contracts/foundation-api.yaml`.
- Browser integration follows typed client implementation.
- Story checkpoint must pass before calling the story complete.

### Parallel Opportunities

- T003-T007 can proceed in parallel after T001/T002 establish root directories/workspace.
- T011-T013 can proceed in parallel.
- T017-T019 can proceed in parallel after their relevant project manifests exist.
- US1 health tests and web shell work can proceed in parallel after Phase 2.
- T030-T034 can be authored in parallel before US2 implementation.
- T035 and T036 can proceed in parallel; T037-T040 then follow the domain/port definitions.
- US3 and US4 can proceed concurrently with most US2 implementation because they touch separate files.
- T054-T056 can proceed in parallel before US5 implementation.
- T062-T064 can proceed in parallel during final polish.

---

## Parallel Example: User Story 2

```text
Parallel test preparation:
- T030 domain validation tests
- T031 repository integration tests
- T032 HTTP integration tests
- T033 typed-client tests
- T034 browser E2E test

Parallel early implementation:
- T035 domain entity
- T036 repository port

Then:
T035 + T036
   -> T037 migration
   -> T038 persistence adapter
   -> T039 application service
   -> T040/T041 HTTP registration
   -> T042 typed client
   -> T043 browser UI
   -> T044 repeated restart/persistence validation
```

---

## Implementation Strategy

### MVP First

The smallest meaningful increment is **Setup + Foundational + US1**:

1. Complete Phase 1.
2. Complete Phase 2.
3. Complete US1.
4. Stop and validate bootstrap/readiness independently.

This proves the repository can be developed reproducibly before persistence and policy work expands.

### Architecture-Proof Increment

Then complete **US2 + US3**:
- US2 proves the intended runtime dependency path with real persistence.
- US3 proves the most important forbidden dependency direction is mechanically enforced.

At this checkpoint the repository has demonstrated architecture, not just documented it.

### Quality-Gate Increment

Complete US4 and US5, then Phase 8. The feature is ready for `/speckit-converge` only after the
single root validation workflow passes all mandatory categories.

---

## Requirement Coverage Notes

- FR-001/002/014: US1 bootstrap/readiness tasks T023-T029.
- FR-003/004/005: US2 vertical-slice tasks T030-T044.
- FR-006/007/008/009: architecture documentation T020-T021 and US3 T045-T049.
- FR-010/011: existing Constitution/ADRs plus US4 T050-T053.
- FR-012/013: US5 T054-T061.
- FR-015: Setup T009 and polish T063.
- FR-016: US5 T055/T057/T060.
- FR-017: CI/root validation T059 and branch workflow already established by Spec Kit.
- FR-018/020: scope check T064.
- FR-019: architecture documentation T020/T049 and ADR boundaries.
- SC-001: T029/T060 + clean-environment timed bootstrap execution T061.
- SC-002: T058/T059/T065.
- SC-003: T044.
- SC-004: T045-T048.
- SC-005: no-runtime-module validation in T046/T047 plus root validation T058.
- SC-006: timed reviewer-navigation exercise T050/T061 plus documentation navigation T051-T053.
- SC-007: T059/T063.
- SC-008: T064.

## Notes

- Do not create empty `apps/field`, `apps/worker`, `services/tiles`, `services/ogc`, map/edit-engine packages, or real vertical modules in Spec 001.
- `FoundationSampleRecord` is intentionally disposable proof data and must not become a hidden product model.
- Every implementing task for constrained `FoundationSampleRecord` fields cites the canonical entity definition in `data-model.md`.
- Commit after logical task groups and keep branch `001-platform-foundation` reviewable.

## Implementation Validation Results

Spec 001 implementation validation completed after all task artifacts were present.

- Accepted Node runtime gate: Node.js 26.13.1.
- TypeScript/React: lint and strict typecheck passed; client SDK 2/2 tests passed; Vite production build passed.
- Python: Ruff passed; mypy strict passed on 17 source files; 18 unit/contract/tool/architecture tests passed.
- Database: PostgreSQL 18 + PostGIS 3.7 migration/integration suite passed 8/8 tests against a real database, including a real Uvicorn process terminate/restart persistence test across 10 consecutive restarts.
- Browser: Playwright foundation vertical slice passed 1/1.
- Architecture guard: Core-to-module prohibition passed, including empty/absent module validation.
- Documentation navigation guard: passed.
- Gitleaks: 0 leaks on versioned/source surface after excluding generated/vendor directories.
- Runtime scope scan: no map engine, GIS editing, House Numbering, billing, field/offline, GeoServer, or Martin implementation leaked into Spec 001.
- Clean bootstrap acceptance (SC-001): PASS in 31.5 seconds with Node 26.13.1, warm dependency caches, fresh dependency directories and fresh PostGIS volume.
- Unfamiliar reviewer navigation (SC-006): PASS in 33.96 seconds using a fresh ephemeral read-only reviewer.
- `git diff --check`: PASS after evidence formatting cleanup.
- `graphify update .`: PASS; `graphify-out/` remains excluded from version control.

## Phase 9: Convergence

- [X] T067 Make API composition validate required configuration before serving any request and add a startup-failure integration test in `apps/api/openvietgis_api/main.py` and `apps/api/tests/integration/test_startup_config.py` per FR-014 and US1/AC3 (partial)
- [X] T068 Add a real API process terminate/restart create→persist→restart→retrieve test for 10 consecutive runs in `apps/api/tests/integration/test_foundation_process_restart.py` per SC-003, US2/AC2, and plan verification strategy (partial)

## Pre-merge review corrections — 2026-11-18

- [X] T069 Track the non-secret `.env.example` and add its explicit Git ignore exception;
  verify source checkouts include the documented bootstrap input.
- [X] T070 Restrict development reset to the exact documented local database names;
  reject driver/query connection overrides; add production-prefix and DSN-override regressions.
- [X] T071 Isolate integration/E2E validation on the dedicated local `openvietgis_test`
  database; ignore inherited application database targets, guard destructive migration
  paths, and update Compose/CI/documentation with regression coverage.

Independent pre-merge review found the three gaps above after the original convergence report.
They are corrected before promotion to main; earlier local-disk bootstrap evidence alone did
not demonstrate that the then-committed source contained the environment template.

Revalidation on Node 26.13.1: root `pnpm validate` PASS, including TypeScript lint/typecheck,
SDK 2/2, web build, Python Ruff/mypy, 40 unit/contract/tool/architecture tests, 8 real PostGIS
integration tests (including ten process restarts), and browser E2E 1/1. The dedicated test
service uses port 54330; the existing development database on 54329 is not the test target.
A dependency deprecation warning from FastAPI/Starlette remains non-blocking.
