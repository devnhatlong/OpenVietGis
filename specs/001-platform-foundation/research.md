# Research: Platform Foundation

**Feature**: 001-platform-foundation  
**Date**: 2026-11-17

This phase resolves implementation choices for the architecture runway only. It does not expand the
feature into GIS, identity, tenancy, processing, or a public module SDK.

## Decision 1 — Runtime baselines

**Decision**: Use Node.js 26 LTS for the web toolchain, Python 3.13 for the application backend,
and PostgreSQL 18 with PostGIS 3.7 for the development database baseline.

**Rationale**:
- Node 26 entered LTS in October 2026 and is an appropriate current production baseline.
- React 19.3 is the current React major/minor line as of this planning date.
- Vite's current supported Node ranges include modern LTS versions; Node 26 avoids adopting the
  experimental Node 27 alpha line.
- Python 3.13 is intentionally conservative for native geospatial dependencies even though the
  current FastAPI line supports newer Python versions.
- PostgreSQL 18 is the current stable supported major; PostGIS 3.7.0 provides released support for
  PostgreSQL 18 and 19.

**Alternatives considered**:
- Node 27 alpha: rejected because it is not an LTS production baseline.
- Python 3.15: rejected for the foundation because native GIS wheel compatibility matters more than
  adopting the newest interpreter immediately.
- PostgreSQL 19 release candidate: rejected because Spec 001 should start on a stable major.

## Decision 2 — Monorepo tooling remains light

**Decision**: Use pnpm workspaces for TypeScript/JavaScript packages and applications. Do not add Nx
or Turborepo in Spec 001. Python remains in the same repository but is managed by its Python project
metadata and uv.

**Rationale**: The repository is still small. Workspace package linking is needed, but distributed
task graph/caching infrastructure is not yet justified.

**Alternatives considered**:
- Nx: powerful but adds policy and generated structure before the repository needs it.
- Turborepo: useful later for task caching; deferred until build/test volume demonstrates value.
- Multiple repositories: conflicts with ADR-001 and makes early contract refactors slower.

## Decision 3 — Development services

**Decision**: Run PostgreSQL/PostGIS as the only mandatory containerized infrastructure service for
Spec 001. Run web and API processes on the host during development. Provide deterministic startup,
health checking, schema migration, and reset commands.

**Rationale**: This gives real database behavior without forcing every code edit through container
rebuilds. It also keeps the first vertical slice small.

**Alternatives considered**:
- Containerize web/API immediately: rejected as unnecessary friction for the first development
  runway.
- SQLite for the foundation: rejected because it would fail to prove the chosen persistence and
  migration boundary.
- Full self-host deployment stack: deferred to the operations specification.

## Decision 4 — Minimal vertical slice

**Decision**: Use a development-only `FoundationSampleRecord` with a UUID identifier, a short label,
and timestamps. Expose create/read behavior through a versioned HTTP contract and a minimal web
screen.

**Rationale**: It proves browser -> client boundary -> HTTP adapter -> application service -> domain
object -> repository -> PostgreSQL -> response without prematurely defining Organization, Project,
Layer, identity, or other future product semantics.

**Alternatives considered**:
- Use Project as the first entity: rejected because Project ownership/tenancy semantics belong to
  Spec 002.
- Use a spatial feature: rejected because spatial catalog/map/editing belong to later specs.
- Health endpoint only: rejected because it does not prove persistence or application layering.

## Decision 5 — HTTP contract and web client

**Decision**: FastAPI publishes the OpenAPI contract. The web application consumes a generated or
thin typed client from a dedicated client package; UI components do not scatter raw endpoint URLs
or response-shape assumptions.

**Rationale**: Even the disposable vertical slice should prove the API contract boundary used by
future web and field clients.

**Alternatives considered**:
- Hand-written fetch calls throughout UI: rejected because it creates immediate coupling.
- GraphQL: rejected by ADR direction; there is no foundation use case requiring it.
- Shared backend model imports into the frontend: rejected because runtime/language boundaries must
  remain explicit.

## Decision 6 — Architecture boundary enforcement

**Decision**: Add a repository-owned architecture check that validates critical path/dependency
rules, starting with the non-negotiable rule that platform/Core code cannot import a vertical
module. Use normal language linters for local import restrictions where they improve error
locality, but do not introduce a general architecture framework in Spec 001.

**Rationale**: The specification requires an automated failure for the critical dependency rule,
not a full policy engine. A small explicit checker is easier to understand and can evolve as the
repository grows.

**Alternatives considered**:
- Manual code review only: rejected because FR-009 requires automation.
- A large architecture-analysis framework from day one: rejected as premature.
- Rely only on package-manager dependency declarations: insufficient because source-level imports
  can still violate intended ownership.

## Decision 7 — Validation strategy

**Decision**:
- Python unit/integration tests: pytest.
- Web/package unit tests: Vitest.
- Browser critical-flow test: Playwright.
- Integration tests use a real PostgreSQL/PostGIS instance.
- One root validation command orchestrates static checks, unit tests, architecture checks, database
  integration, and the foundation browser flow.

**Rationale**: This directly satisfies the Constitution requirement that critical boundaries be
tested at real runtime boundaries.

**Alternatives considered**:
- Mock database integration: rejected for the persistence/migration proof.
- Browser test deferred entirely: rejected because the vertical slice explicitly includes the
  product shell.
- Many separate undocumented commands: rejected because FR-012 requires one documented baseline
  validation workflow.

## Decision 8 — Migration and reset model

**Decision**: Manage schema through versioned migrations. Development reset is an explicit
environment-guarded command that refuses non-development database targets, recreates the local
foundation schema/database state, and reapplies migrations.

**Rationale**: Reproducibility requires deterministic reset while the Constitution requires
destructive actions to consider recovery and environment safety.

**Alternatives considered**:
- Auto-create tables from ORM metadata: rejected because it bypasses the migration path later
  features must use.
- Unrestricted drop/recreate script: rejected because accidental target mistakes would be unsafe.

## Decision 9 — CI baseline

**Decision**: Add one CI workflow that installs the pinned runtime baselines, starts a real
PostGIS service, runs the root validation workflow, and requires no production credentials.

**Rationale**: The default branch must remain deployable and accepted foundation work needs an
objective repeatable gate.

**Alternatives considered**:
- CI only after several features: rejected because architectural drift is cheapest to catch now.
- Cloud deployment pipeline in Spec 001: deferred; deployment belongs to later operations work.
