# R003 quickstart and acceptance protocol

This is the planned reproducible protocol, not executed R003 evidence yet. Use a fresh checkout of the exact R003 candidate and the isolated test database only. Never use a production database or overwrite an existing dev/review database.

## Setup

1. From repository root, use Node 26 and the existing Python/uv toolchain. Run `pnpm install --frozen-lockfile`, `uv sync --project apps/api --locked`, and `pnpm exec playwright install chromium`.
2. Start the isolated PostgreSQL test service using the existing Compose/test database guard. Use `pnpm validate:integration` and `pnpm validate:e2e` (both invoke tools.run_with_test_database). Verify migrations upgrade from 0005 and downgrade safely in disposable test DB, restricted runtime role, forced RLS. Capture PostgreSQL, PostGIS, PROJ and container digest; network grids off.
3. Use the test fixture provisioner (implementation task) to create two synthetic organizations and distinct projects, authorized human and narrowly scoped service actors, and frozen reference registry entries. Do not import external data. A separate scenario provisions an archived/deleted Project, suspended Organization and revoked credential.
4. Build SDK from the committed OpenAPI document via `pnpm contracts:generate`; verify generated output clean and contract consumer uses public IDs only.

## Setup checkpoint — 2026-11-18

Owner approved implementation with the outcomes checklist item still unchecked; all SC-001–009 remain required. Baseline 25ff038: independent design review passed; Graphify 311 files, 2632 nodes, 7447 edges, 152 communities. Verified portable Node 26.13.1 (`C:/code/openvietgis-r002-browser/dist/toolchains/node-v26.13.1-win-x64` on this host), corepack pnpm 12.21.0; node runtime check passed. Python 3.13.18; FastAPI 0.163.1, SQLAlchemy 2.1.9, Alembic 1.20.1, psycopg 3.3.9, pytest 9.2.0, openapi-spec-validator 0.9.0. For restricted integration, allocate a dedicated loopback test container/port and database named `openvietgis_test`; explicitly set `OPENVIETGIS_TEST_DATABASE_URL` before invoking `tools.run_with_test_database` (never trust its default). Guard dry-run confirms non-test DB rejected and distinct owner/runtime connection URLs, runtime only NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOINHERIT/NOBYPASSRLS. Pinned PostGIS image present. Scaffold a25c135 passed Ruff, scope and architecture checks; no actual test acceptance implied. T003 integrated c1fd787: contract tooling validates R002 + R003, all four generated artifacts deterministic, Node26/pnpm frozen offline install, SDK lint/typecheck and 13 SDK tests pass; 2 new contract tooling regressions red before implementation then green, also re-run green on integration worktree. Setup phase T001–T004 complete. Exact setup CI 9703f6f / [44248466471](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44248466471) all three jobs green. Foundation in progress: T006 tests-only cf0a37f verified red against 0005 in dedicated synthetic DB (2 failures/4 fixture errors, absent spatial schema/tables); do not interpret as passing RLS before 0006. T010 e5b9ccf immutable registry metadata and 10 focused tests pass after expected missing-module red, Ruff/mypy passed on isolated worker and integrated tests green. No operational transforms exposed. T005/T007–009 domain 79f0bad integrated tests: 52 domain tests + 10 CRS tests pass together, Ruff and mypy (64 files) passed. T011 7b0667e scoped query/command port, Ruff/mypy (65 files)/architecture passed. T001–T011 complete (11/64; T006 remains test-first red until migration).

## Acceptance sequence

| Criterion | Reproducible check |
| --- | --- |
| SC-001 | Register each approved fixture by key, list/detail source; assert expected native CRS/schema/extent/count, zero/empty state distinct from unknown; invalid fixture remains non-ready with actionable reason. |
| SC-002 | Create two Layers referencing same source, compare feature IDs and backing scoped row count; retire one, verify the other and source still available. Source retire with an active Layer fails. |
| SC-003 | Walk ordered pages at exact content/schema revisions, assert complete ID set with no duplication; compare detail with page plus independent typed fixture expectations; metadata-only rename preserves pins; incompatible revision returns explicit stale conflict. |
| SC-004 | Execute every direct edge against independent numeric controls (inverse from published targets), verify profile tolerance and selected operation. Reject unknown, definition-only, unvalidated edge, out-of-area, demonstrably swapped axis, non-finite, Z/M, contradictory metadata. |
| SC-005 | Exercise cross-org/project ID substitution in every list/detail/schema/extent/feature/reference/mutation path as human and applicable service actor, including actor authorized in both projects. Check no leaks or unauthorized writes; pool GUC reset, RLS role and lifecycle/grant revocation regression. |
| SC-006 | Inspect committed safe revision evidence; expected actor, time, stable resource and actual old/new values; stale/concurrent/interrupted operations cannot commit partial state. |
| SC-007 | Warm restricted-role HTTP benchmark of catalog list and detail and 100-feature pages on deterministic 10k dataset; ≥100 measured samples per target, native and accepted transformed paths; record p50/p95/max and environment, enforce <=1s catalog and <=2s page. |
| SC-008 | Independent contract consumer discovers Layer, schema, capability, pins, page and stable feature detail without physical storage knowledge or R004 code. |
| SC-009 | Restart test database/app and re-read committed catalog and pins; inject failure in fixture registration transaction and verify no partial ready record or orphan rows. |

## Verification

Run `pnpm validate` using repository scripts; preserve existing R002 gates. Use dedicated test fixtures for performance and destructive migration tests. Run docs/scope/architecture checks, contract validation/generation, secret scanning and exact-commit CI. Update Graphify for runtime changes. Record actual pass/fail plus evidence path per SC; independent reviewer approves exact tested commit before fast-forward integration. R002 unfamiliar-human timing remains mandatory before external release despite its internal-integration waiver.
