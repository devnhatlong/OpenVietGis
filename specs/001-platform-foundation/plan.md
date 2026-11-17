# Implementation Plan: Platform Foundation

**Branch**: `001-platform-foundation` | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-platform-foundation/spec.md`

## Summary

Spec 001 establishes the architecture runway for OpenVietGIS without implementing GIS capability.
The implementation will create a light monorepo foundation, a React/TypeScript product shell, a
Python/FastAPI application backend, a real PostgreSQL/PostGIS development database, versioned
migrations, architecture boundary checks, one disposable persisted `FoundationSampleRecord`
vertical slice, and a single baseline validation workflow.

The vertical slice exists only to prove the approved dependency path:

```text
Web shell
  -> typed client boundary
  -> HTTP adapter
  -> application service
  -> foundation domain object
  -> repository port
  -> PostgreSQL adapter
  -> persisted record
  -> response back to web
```

It deliberately does not define Organization, Workspace, Project, Layer, identity, tenancy,
map rendering, editing, processing, field/offline, billing, or House Numbering semantics.

## Technical Context

**Language/Version**: Node.js 26 LTS; TypeScript 5.x; React 19.3; Python 3.13

**Primary Dependencies**: React, Vite, pnpm workspaces; FastAPI, Pydantic, SQLAlchemy 2, Alembic;
uv for Python environment management

**Storage**: PostgreSQL 18 + PostGIS 3.7; only the disposable foundation sample table is introduced
in this feature

**Testing**: Vitest for web/package unit tests; pytest for Python unit/integration tests; Playwright
for the critical browser vertical slice; real PostgreSQL/PostGIS for integration behavior

**Target Platform**: Development on Windows 11 and Linux-capable environments with Docker Compose;
web runtime in current evergreen desktop browsers; API runtime on Linux-compatible Python
environments

**Project Type**: Monorepo web platform foundation: desktop web SPA + HTTP API + shared packages +
development infrastructure

**Performance Goals**:
- clean supported bootstrap reaches the working foundation within 20 minutes excluding downloads;
- baseline validation is designed to remain small enough for normal contributor use and CI;
- the create/persist/restart/read integration scenario passes 10 consecutive automated runs;
- no GIS-scale performance target is introduced before GIS capability exists

**Constraints**:
- zero House Numbering/Bình Hưng-specific Core concepts;
- zero end-user GIS tools in Spec 001;
- no production authentication, tenancy, billing, processing, field/offline, or map engine;
- Core must build/run with `modules/` empty or absent;
- database schema changes go through migrations, not ORM auto-create;
- no production secret or production data is needed for development or tests;
- destructive development reset must reject non-development targets

**Scale/Scope**:
- 1 web app, 1 API app, foundation packages/tooling, 1 PostGIS dev service;
- 1 disposable persisted entity;
- 3 API behaviors beyond liveness/readiness: create/read foundation record;
- 1 critical architecture rule automated initially: Core/platform must not depend on vertical modules;
- 12 existing foundational ADRs remain the architectural source for replaceable technical choices

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Constitution rule | Pre-design assessment | Post-design assessment |
| --- | --- | --- |
| I. Platform-First, Module-Isolated | PASS — Spec explicitly forbids vertical-domain dependencies. | PASS — source layout keeps `modules/` outside platform apps/packages; architecture check enforces the critical direction. |
| II. Open Data and Interoperability | PASS — no user GIS data is introduced. | PASS — HTTP contract is documented and no proprietary data lock-in is introduced. |
| III. Tenant Isolation Is a Security Boundary | PASS — tenant-owned resources are intentionally not created in Spec 001. | PASS — the only persisted record is explicitly development/foundation proof data; tenancy is deferred rather than guessed. |
| IV. Spatial Correctness and Explicit CRS | PASS — no spatial data or transformation exists in this feature. | PASS — PostGIS is infrastructure only; no CRS behavior is implemented prematurely. |
| V. Changes Are Versioned and Auditable | PASS — no material user/business data exists. | PASS — the disposable foundation record is non-business proof data; future material changes remain governed by ChangeSet ADR/design. |
| VI. Capability-Driven Architecture | PASS — no GIS capability model is prematurely implemented. | PASS — boundary packages/contracts are created without pretending the sample record is a product capability. |
| VII. Web-Native, Engine-Agnostic | PASS — architecture runway separates adapters from application/domain behavior. | PASS — FastAPI/React/PostgreSQL choices remain ADR-level implementation decisions, not constitutional coupling. |
| VIII. Workflow Value Before Feature Count | PASS — feature is intentionally narrow. | PASS — only one end-to-end proof workflow is implemented; no feature-parity work is added. |
| Architectural boundaries | PASS — monorepo/modular-monolith ADRs already define intended direction. | PASS — UI session, API, application, domain, and persistence boundaries are explicit; no long-lived DB transaction pattern is introduced. |
| Development and quality gates | PASS — Spec Kit, tests, ADRs, architecture checks, migrations, and no-secrets requirements are in scope. | PASS — quickstart, test strategy, CI baseline, real PostGIS integration, and architecture validation are part of the design. |

**Gate result**: PASS. No constitutional violation requires Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-platform-foundation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── foundation-api.yaml
├── checklists/
│   └── requirements.md
└── tasks.md              # created later by /speckit-tasks
```

Architecture decisions remain under:

```text
docs/adr/
├── README.md
├── ADR-001-monorepo.md
├── ...
└── ADR-012-deployment.md
```

### Source Code (repository root)

```text
openvietgis/
├── apps/
│   ├── web/
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── App.tsx
│   │   │   │   └── FoundationPage.tsx
│   │   │   └── main.tsx
│   │   ├── tests/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   │
│   └── api/
│       ├── openvietgis_api/
│       │   ├── adapters/
│       │   │   ├── http/
│       │   │   │   ├── health.py
│       │   │   │   └── foundation.py
│       │   │   └── persistence/
│       │   │       ├── db.py
│       │   │       └── foundation_repository.py
│       │   ├── application/
│       │   │   └── foundation_service.py
│       │   ├── domain/
│       │   │   └── foundation.py
│       │   ├── ports/
│       │   │   └── foundation_repository.py
│       │   ├── config.py
│       │   └── main.py
│       ├── migrations/
│       │   ├── env.py
│       │   └── versions/
│       │       └── 0001_foundation_sample.py
│       ├── tests/
│       │   ├── unit/
│       │   └── integration/
│       └── pyproject.toml
│
├── packages/
│   └── client-sdk/
│       ├── src/
│       │   └── foundation.ts
│       ├── tests/
│       ├── package.json
│       └── tsconfig.json
│
├── modules/
│   └── README.md          # boundary documentation only; no domain module implementation
│
├── tools/
│   ├── check_architecture.py
│   └── reset_dev.py
│
├── tests/
│   └── e2e/
│       └── foundation.spec.ts
│
├── infra/
│   └── dev/
│       └── compose.yaml
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docs/
│   ├── architecture.md
│   └── adr/
│
├── package.json
├── pnpm-workspace.yaml
├── playwright.config.ts
├── .env.example
└── README.md
```

**Structure Decision**: Use the ADR-approved monorepo with only the pieces required to prove the
foundation. `apps/web` owns the product shell, `apps/api` owns the HTTP/application/domain/persistence
path, `packages/client-sdk` owns the typed web-to-API boundary, `modules/` exists only to make the
forbidden dependency boundary concrete, and `infra/dev` provides the real PostGIS dependency.
Worker, tile, OGC, map/edit engines, field app, object storage, and real module packages are not
created in Spec 001 because they would be empty architecture theater.

## Phase 0 — Research Decisions

Research is recorded in [research.md](research.md). All Technical Context choices are resolved;
there are no unresolved planning questions.

Key outcomes:
1. Node.js 26 LTS, Python 3.13, PostgreSQL 18/PostGIS 3.7 are the foundation runtime baselines.
2. pnpm workspaces are sufficient; no Nx/Turborepo is added yet.
3. PostgreSQL/PostGIS is the only required containerized local infrastructure service.
4. A disposable `FoundationSampleRecord` is the sole vertical-slice entity.
5. OpenAPI is the web/API contract boundary.
6. Architecture enforcement starts with one explicit repository-owned rule rather than a general
   architecture framework.
7. pytest + Vitest + Playwright cover unit, integration, and browser boundaries.
8. Migrations and a guarded development reset are mandatory.
9. CI runs the same root validation behavior against real PostGIS.

## Phase 1 — Design

### 1. Vertical-slice data model

[data-model.md](data-model.md) defines one entity:

`FoundationSampleRecord(id, label, created_at, updated_at)`

It is deliberately non-tenant, non-spatial, and non-business. Update/delete are not exposed. It may
be removed once real product entities arrive.

### 2. HTTP contract

[contracts/foundation-api.yaml](contracts/foundation-api.yaml) defines:
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `POST /api/v1/foundation-records`
- `GET /api/v1/foundation-records/{record_id}`

The web app consumes this boundary through `packages/client-sdk`; it does not share backend ORM or
domain classes.

### 3. Persistence and migration boundary

The API application service depends on a repository port. The PostgreSQL adapter implements it.
Alembic migration `0001_foundation_sample` creates only the foundation proof table/schema.

Tests and local development use real PostgreSQL/PostGIS. Application startup does not silently
create tables.

### 4. Architecture boundary check

`tools/check_architecture.py` initially enforces the critical dependency direction:
- files/packages classified as Core/platform MUST NOT import or declare a dependency on paths/packages
  under `modules/`;
- test fixtures demonstrate one rejected invalid dependency and one accepted valid module-to-public
  contract direction.

The checker remains intentionally small and repository-owned. Additional rules are added only when
later specs introduce real boundaries that need enforcement.

### 5. Development environment

`infra/dev/compose.yaml` provides PostgreSQL/PostGIS with:
- development-only credentials from documented local configuration;
- a health check;
- a named local volume;
- explicit port/config documentation.

Web/API run on the host for short feedback loops. `.env.example` contains non-secret sample values.
Configuration loading fails fast for missing required settings.

### 6. Baseline validation workflow

The root `pnpm validate` target orchestrates the mandatory checks, including Python commands through
uv. It must report categories clearly enough to know whether static quality, tests, architecture,
integration, or E2E failed.

CI invokes the same logical workflow rather than maintaining a separate hidden validation path.

### 7. Safe development reset

`tools/reset_dev.py` verifies an explicit development/test environment marker and validates the
target database identity before destructive reset. It then resets foundation development data and
reapplies migrations. It refuses ambiguous or production-like targets.

### 8. Documentation

`docs/architecture.md` explains:
- the top-level monorepo ownership model;
- allowed dependency direction;
- why `modules/` is downstream of Core;
- where Constitution, ADRs, specs, and runtime code each belong;
- that empty future services/packages are not created until their first feature needs them.

README links bootstrap, architecture, Spec Kit, ADRs, and root validation.

## Verification Strategy

The implementation is accepted only when all of the following are true:

1. **Static quality**: TypeScript/Python formatting, linting, and type checks pass.
2. **Unit**: web/package and Python domain/application tests pass.
3. **Architecture**: the known forbidden Core-to-module fixture is rejected and valid direction passes.
4. **Migration**: a fresh real PostGIS database migrates from zero to head successfully.
5. **Persistence integration**: create/read survives API process restart and passes 10 consecutive runs.
6. **Readiness behavior**: database outage produces non-ready behavior instead of a false healthy state.
7. **Browser E2E**: the web shell creates a sample record and reads it back through the supported
   client/API path.
8. **Module absence**: deleting/omitting `modules/` runtime contents does not break Core validation.
9. **Secrets**: validation needs no production credential/data.
10. **Reset safety**: destructive reset refuses a non-development target in an automated test.

## Complexity Tracking

No Constitution violations.
