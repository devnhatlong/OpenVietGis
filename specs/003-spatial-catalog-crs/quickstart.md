# R003 quickstart and acceptance protocol

This is the planned reproducible protocol, not executed R003 evidence yet. Use a fresh checkout of the exact R003 candidate and the isolated test database only. Never use a production database or overwrite an existing dev/review database.

## Setup

1. From repository root, use Node 26 and the existing Python/uv toolchain. Run `pnpm install --frozen-lockfile`, `uv sync --project apps/api --locked`, and `pnpm exec playwright install chromium`.
2. Start the isolated PostgreSQL test service using the existing Compose/test database guard. Use `pnpm validate:integration` and `pnpm validate:e2e` (both invoke tools.run_with_test_database). Verify migrations upgrade from 0005 and downgrade safely in disposable test DB, restricted runtime role, forced RLS. Capture PostgreSQL, PostGIS, PROJ and container digest; network grids off.
3. Use the test fixture provisioner (implementation task) to create two synthetic organizations and distinct projects, authorized human and narrowly scoped service actors, and frozen reference registry entries. Do not import external data. A separate scenario provisions an archived/deleted Project, suspended Organization and revoked credential.
4. Build SDK from the committed OpenAPI document via `pnpm contracts:generate`; verify generated output clean and contract consumer uses public IDs only.

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
