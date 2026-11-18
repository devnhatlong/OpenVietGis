# Implementation Plan: Spatial Catalog & CRS (R003)

**Branch**: `integration/003-on-verified-main` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Baseline**: verified main `64f00e67c18c87ddd16e76498e100c30ddfad455` (R002; internal integration only, external release still requires SC-013 human timing). R003 planning checkpoint `443a40c`.

## Summary

Deliver Project-scoped spatial catalog registration and read-only feature inspection over pre-established platform-owned fixtures; distinguish DataSource from Layer, preserve source-native coordinates, publish explicit CRS profiles, and provide bounded pinned reads for R004. Reuse R002 actor/tenant/permission boundaries, transactional audit and PostgreSQL RLS. No importer, renderer, arbitrary connection, editor or export.

## Technical Context

- **Language/runtime**: Python 3.13, Node 26, TypeScript 6, React 19; use locked dependency versions and existing workspace scripts.
- **Dependencies**: FastAPI, SQLAlchemy, Alembic, psycopg, PostGIS, React Router, TanStack Query, generated OpenAPI TypeScript SDK; no new renderer or GIS client engine. Verify exact PostGIS/PROJ operations and dependency API usage before implementation.
- **Storage**: PostgreSQL 18/PostGIS 3.7, PROJ 9.9, network grids disabled. New spatial schema with composite organization/project/source keys; source-native XY geometry, explicit SRID and typed logical attributes; trusted private fixture registry. Do not mutate native coordinates when reading or correcting declaration.
- **Tests**: pytest unit/contract/integration/performance, restricted runtime PostgreSQL role, pnpm lint/typecheck/test/build, Playwright catalog inspection, independent contract consumer, full CI and migration-cycle/security tests.
- **Platform**: existing local Docker development/test configuration and modular monolith; web SPA uses the existing protected query/API stack.
- **Scale and performance**: 10,000 deterministic features across three homogeneous sources, maximum 100 records/page; catalog list/detail p95 ≤1 s, page100 p95 ≤2 s; measure warmed HTTP paths with ≥100 samples per target, native and accepted transformation separately.
- **Constraints**: project ownership immutable; archive read-only, deleted hidden, suspended org inaccessible. Stable logical feature/field IDs, schema/content revision pins, no silent CRS inference, no unsupported edge chaining, no data purge or public anonymous access.

## Constitution Check

| Gate | Design decision |
| --- | --- |
| Modular monolith, explicit domain boundaries | New spatial domain/ports, PostgreSQL and HTTP adapters; no direct database coupling from browser or other modules. |
| Spatial truth and capabilities (ADR-005/006) | Native PostGIS geometry; DataSource owns schema, CRS, content; Layer owns presentation-neutral catalog metadata and truthful read capability. |
| Revision and audit (ADR-007) | Separate catalog, Layer, content and schema revisions; immutable safe per-mutation evidence in the same transaction; no generic edit history engine. |
| Source assets (ADR-010) | No uploaded SourceAsset in R003; trusted pre-established reference selection only. |
| Security (ADR-014) | Explicit org/project scope; authorize human/service every request, enforce RLS and composite FK scope; no broad role or bypass. |
| Testable, independently verifiable delivery | Contract first; deterministic acceptance fixtures and independent geodetic controls; no self-derived target or claimed benchmark before measuring. |
| Scope and reuse | R004/R005 consume contracts only; no map, import/export, external connectors or generic processing. |

Pre-research check passes on verified main. Phase 1 design and independent cross-spec/security review pass after aligning scoped audit FK, native fixtures in foundation, permission-safe metadata inspection, and numeric domain tolerance. OpenAPI 3.1 validates 10 paths/14 operations, 64 implementation tasks trace five stories and nine SCs. No constitutional exception requested. Runtime acceptance remains unmeasured; the unchecked requirements checklist outcome is not a design finding or a successful runtime result.

## Decisions and implementation sequence

1. **Foundation**: define spatial domain entities and typed attributes; create migration after 0005, project-bound policies on new tables, composite FKs and per-scope indexes, immutable revision evidence; preserve R002 behavior and existing GUCs. Apply transaction-local project binding only after verified project authorization. Deny missing/incorrect context. Build private deterministic fixture definitions and transactional registration binding; no arbitrary storage paths or caller-supplied coordinates.
2. **US1: DataSource catalog**: allowlist pre-established source key; validate independently known geometry/CRS/schema, count and extent with explicit empty/unknown state. One registration per key per Project (including retired); failures atomic, invalid metadata records actionable. Metadata correction requires independent registry evidence that existing native rows already match the new declaration; no guessed SRID or coordinate rewrite.
3. **US2: Layer**: distinct identity, same-project ready source reference, explicit capability/availability; serialize Layer create vs source retire; retire Layer independently. Source retirement requires project.manage and no active Layer; no physical delete.
4. **US3: feature reads**: source-native geometry stored, explicit XY envelope and CRS metadata, stable feature ID order; pin content and schema for both page/detail. Bounded keyset continuation by stable feature ID, scoped by explicit project/Layer and source pins; caller preserves read options during traversal. Reject stale pins. Serialize or snapshot reads so metadata and records share one version. Null values distinct from empty strings; decimal strings exact, timestamps ISO UTC. No physical storage details in public contract.
5. **US4: boundary and evidence**: project.read for reads, project.edit for registration/metadata and Layer writes, project.manage for source retirement. Reuse current tenant access and permissions; service credentials verified each request; human unsafe requests CSRF checked. Lock org→project→source→layer, acquire locks before rechecking lifecycle and permissions; stable safe errors. Audit actor, time, previous/current revision and changed values; failed operations do not commit.
6. **US5: CRS**: finite accepted definitions and eight direct directed edges; 3405/3406 definition-only. Explicit XY application convention; native EPSG axis metadata separately. Validate every coordinate (finite, dimensions, domains, applicability, geometry family); reject unsupported edge, arbitrary parameters, silent swapping, clipping or ballpark fallback. Explicit verified EPSG 6960 pipeline and deterministic analytic controls. See [research](research.md) and the original [matrix](crs-support-matrix.md).
7. **Consumer and convergence**: extend contract tooling and SDK without weakening R002; minimal authorized catalog inspection in existing SPA, small independent API-only consumer; benchmark, migration downgrade/upgrade, restart/rollback, full validate/CI, Graphify update, independent exact-commit review. No main promotion until all nine R003 success criteria have recorded evidence and explicit gate verdict.

## Project Structure

```text
specs/003-spatial-catalog-crs/
  spec.md, plan.md, research.md, data-model.md, quickstart.md
  contracts/                    # OpenAPI + semantic read contract
  crs-support-matrix.md, vn2000-control-evidence.md
  reference-fixture-profile.md, tasks.md

apps/api/openvietgis_api/domains/spatial/
  domain.py, ports.py, service.py, crs.py
apps/api/openvietgis_api/adapters/persistence/
  spatial_repository.py, spatial_fixtures.py
apps/api/openvietgis_api/adapters/http/spatial.py
apps/api/migrations/versions/0006_spatial_catalog.py
apps/api/tests/{unit,contract,integration,performance}/
packages/client-sdk/src/
  spatial.ts, generated/spatial-catalog.ts
apps/web/src/features/spatial/
  SpatialCatalogPage.tsx
tools/
  check_contracts.py               # extend, preserve existing checks
```

Existing main application, SDK export, router and project page receive narrowly scoped wiring. New routes must follow existing R002 request/session and tenant-access logic. Exact schemas and API shape are in the companion model and contracts.

## Complexity Tracking

None. The scope is a single existing modular monolith; no new deployment unit or service.
