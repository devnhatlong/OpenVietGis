# R003 quickstart and acceptance protocol

This document contains the reproducible protocol and executed R003 evidence. The final acceptance section supersedes historical partial checkpoints. Use a fresh checkout of the exact R003 candidate and the isolated test database only. Never use a production database or overwrite an existing dev/review database.

## Setup

1. From repository root, use Node 26 and the existing Python/uv toolchain. Run `pnpm install --frozen-lockfile`, `uv sync --project apps/api --locked`, and `pnpm exec playwright install chromium`.
2. Start the isolated PostgreSQL test service using the existing Compose/test database guard. Use `pnpm validate:integration` and `pnpm validate:e2e` (both invoke tools.run_with_test_database). Verify migrations upgrade from 0005 and downgrade safely in disposable test DB, restricted runtime role, forced RLS. Capture PostgreSQL, PostGIS, PROJ and container digest; network grids off.
3. Use the test fixture provisioner to create two synthetic organizations and distinct projects, authorized human and narrowly scoped service actors, and frozen reference registry entries. Do not import external data. A separate scenario provisions an archived/deleted Project, suspended Organization and revoked credential.
4. Build SDK from the committed OpenAPI document via `pnpm contracts:generate`; verify generated output clean and contract consumer uses public IDs only.

## Setup checkpoint — 2026-11-18

Owner approved implementation with the outcomes checklist item still unchecked; all SC-001–009 remain required. Baseline 25ff038: independent design review passed; Graphify 311 files, 2632 nodes, 7447 edges, 152 communities. Verified portable Node 26.13.1 (`C:/code/openvietgis-r002-browser/dist/toolchains/node-v26.13.1-win-x64` on this host), corepack pnpm 12.21.0; node runtime check passed. Python 3.13.18; FastAPI 0.163.1, SQLAlchemy 2.1.9, Alembic 1.20.1, psycopg 3.3.9, pytest 9.2.0, openapi-spec-validator 0.9.0. For restricted integration, allocate a dedicated loopback test container/port and database named `openvietgis_test`; explicitly set `OPENVIETGIS_TEST_DATABASE_URL` before invoking `tools.run_with_test_database` (never trust its default). Guard dry-run confirms non-test DB rejected and distinct owner/runtime connection URLs, runtime only NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOINHERIT/NOBYPASSRLS. Pinned PostGIS image present. Scaffold a25c135 passed Ruff, scope and architecture checks; no actual test acceptance implied. T003 integrated c1fd787: contract tooling validates R002 + R003, all four generated artifacts deterministic, Node26/pnpm frozen offline install, SDK lint/typecheck and 13 SDK tests pass; 2 new contract tooling regressions red before implementation then green, also re-run green on integration worktree. Setup phase T001–T004 complete. Exact setup CI 9703f6f / [44248466471](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44248466471) all three jobs green. Foundation in progress: T006 tests-only cf0a37f verified red against 0005 in dedicated synthetic DB (2 failures/4 fixture errors, absent spatial schema/tables); do not interpret as passing RLS before 0006. T010 e5b9ccf immutable registry metadata and 10 focused tests pass after expected missing-module red, Ruff/mypy passed on isolated worker and integrated tests green. No operational transforms exposed. T005/T007–009 domain 79f0bad integrated tests: 52 domain tests + 10 CRS tests pass together, Ruff and mypy (64 files) passed. T011 7b0667e scoped query/command port, Ruff/mypy (65 files)/architecture passed. T001–T012 complete (12/64). Independent domain review passed with timestamp/manifest refinements integrated 912e5ee (58 domain +10 CRS tests, Ruff/mypy pass). Migration ec9ccdc passed 8 real restricted-role integration tests twice on dedicated DB 54336, including forced RLS, cross-org/project FK, append-only history, data pin consistency, malformed metadata, pooled scope reset, 0005 downgrade and re-upgrade preserving R002 rows/policies. Independent migration review passed. Full integrated static/unit/contract/architecture suite green with one existing skip; T013 project proof integrated 5cfc0ae: 43 worker checks passed (12 migration/project proof, 26 R002 RLS/context, 5 service authorization). T014 scoped repository e157b58: 25 combined real DB tests passed, including archived read, scope failure/reset, cross-org resources, and current permission. T015 134a5fb: server-derived content and schema pins, CAS, atomic R002 audit and safe actual old/new evidence; 100 combined spatial unit/restricted-role integration tests passed. Independent T013–T015 review found archived mutation was rejected before permission; regression reproduced and corrected at f7812e5, 101 combined tests green including unauthorized archived mutation denied by missing permission and authorized mutation read-only. Ruff, mypy (67 source files), full unit/contract/tools/architecture with one existing skip, contract/scope/docs checks all pass. T016 dd442ad: 25 immutable allowlisted definitions, 4,000 point/3,000 line/3,000 polygon records, wide and narrow independent controls, explicit negative manifests, 23 fixture tests green; candidate metadata is NOT_READY until T020 actual native validation. T017 integrated at 0ad4ebc: 136/136 foundational tests passed via tools.run_with_test_database (spatial domain, fixture registry, migration and repository/RLS, R002 RLS, service identity and migration regressions) using dedicated pinned PostGIS loopback 54338 and restricted NOBYPASSRLS role. Full broad regression process exceeded transport timeout and was stopped by exact owned PID tree after confirming no active DB connections; no result claimed. T001–T017 Foundation gate complete, 17/64; all nine end-to-end acceptance criteria remain pending user-story implementation.

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

## US1 checkpoint (T018–T026)

Local integrated runtime baseline `a85f992` (2026-11-18), synthetic restricted PostGIS database only. T018: 28 HTTP contract cases failed on absent routes, then passed; full contract suite 35/35. T019: 32 real HTTP integration cases failed before routes, then passed in two explicitly isolated test invocations (11 ready cases and 21 remaining). The 25 reference fixtures (11 ready, 14 invalid/not-ready) are registered through the actual authenticated POST and inspected via GET using the restricted `openvietgis_runtime` role; expectations are frozen independent literals. The three primary ready fixtures contain exactly 10,000 features. Metadata checks cover native CRS/axis/unit, exact count and extent states/bounds, stable typed fields, provenance, pins, invalid reasons and raw geometry retention. T020: 104 spatial unit tests and 10 native fixture-validator integration tests green, including persistent geometry/attribute drift and correction; T021/T022 focused real DB and service checks green and independently reviewed. T023: actual HTTP rollback, CAS, safe audit evidence, scope and dependency rejection green. T024: 3 SDK TDD cases red then green, 16/16 entire SDK, lint/typecheck, deterministic regeneration. T025: 15/15 existing web tests, lint/typecheck and production build green; the spatial catalog route and Project link are implemented. Browser E2E remains for later R003 verification.

SC-001 **local PASS** for the approved 25 synthetic reference sources: reproducible evidence in `apps/api/tests/integration/spatial/test_sources.py` (`test_ready_native_metadata`, `test_nonready_fixture_preserves_truthful_metadata_and_native_geometry`); rollback, correction and scope evidence in the same file. PostGIS 3.7/PG18.7/PROJ 9.9, network off, dedicated loopback port 54338; no dev/production writes. The exact integration commit must still pass CI. SC-002–SC-009 remain pending their end-to-end gates; partial tests do not confer acceptance. No main promotion or deployment.

## US2 checkpoint (T027–T033)

US1 integrated exact `311d8ada68f7e702595d92ea8d11e33ec53af88f` passed all three GitHub jobs ([run 44265735610](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44265735610)). US2 T027: 28 Layer ASGI contract cases failed on absent routes then all passed (entire 63/63 contract suite green). T028: five real authenticated HTTP/PostGIS integration cases verified red on missing routes then green. Both competing transaction winner orders were forced with an actual database lock wait observed via pg_stat_activity; source retirement and Layer creation cannot commit an orphan. T029: direct restricted-role repository test red on missing insert_layer then passed, with nine total source/repository scope checks. Same-scope source lock verifies active and ready; shared Project-lock reads ensure bounded nested metadata consistency; duplicate display names allowed. T030: independent Layer CAS and nine capability dispositions tested after missing-service red; independent read-only review exact `3b373c8` found no blockers. T031: SDK two red→green tests, entire 18/18 SDK suite and regenerated contracts identical. T032: Layer catalog UI, create from ready selected source, current scopes, capability display and safe rename/retirement; web lint/typecheck, 15/15 existing tests and production build green. Browser E2E remains T061. Additional 33 real non-ready/lifecycle source and migration/RLS regressions green; full unit/contract/tools/architecture suite green with one existing skip; Ruff/mypy 69 files, architecture/contracts/scope/docs passed.

SC-002 **local PASS** (synthetic reference scope): `apps/api/tests/integration/spatial/test_layers.py` verifies two distinct same-source Layers with duplicate names, all four native reference feature IDs, exact EWKB/attributes/pins and unchanged storage row count after each independent retirement; the other Layer and source remain accessible until explicitly retired; source retirement while referenced fails. It verifies scope denial even for actor authorized in both Projects, revisions and safe actual audit evidence. DB was dedicated loopback 54338, pinned PG18.7/PostGIS3.7/PROJ9.9 with network off; no dev/production data touched. All subsequent feature-read and security/CRS SC gates remain pending. Exact US2 CI is required before advancing the next story.

## US3 checkpoint (T034–T042)

US2 exact `ea517af0cdc93021daa248a17d124bf474a3467e` passed all three GitHub CI jobs ([run 44285617577](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44285617577)). T034: 20 ASGI contract cases proved red on absent feature routes, then passed. T037: six logical serialization cases red before the serializer, then green. The native reader preserves binary64 coordinates and exact logical field types, and requires current authorization, active ready source and Layer, both pins, and bounded stable-ID keyset pagination. Nine focused native WKB and controlled-refresh unit cases passed; overall backend unit/contract tests (before the independent consumer addition), Ruff and mypy passed. T040: SDK feature page/detail tests red then green; entire SDK 30/30, lint and typecheck pass. T041: web inspector test-first red on the absent module, then 24/24 web tests, lint, TypeScript typecheck and production build pass. The inspector uses account/organization/project/layer/source and both pins in its cache protection, restarts its page traversal on a stale pin and preserves the exact selected feature ID; browser acceptance remains a later gate.

T035 and T036 real restricted PostGIS tests (five cases each) were blocked locally by Docker Desktop Linux engine HTTP 500/timeout. The exact runtime commit `52cee0b0411bc3ebf96cbaa48dd8d97d0301d1da` was therefore dispatched once to the isolated GitHub validation ref `validation/r003-us3-52cee0b` ([CI run 44320458138](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44320458138), [backend job](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44320458138/job/134857699864)). Backend passed: 401 unit/contract/tools/architecture cases, 166 integration/performance cases (one skip, the separate live OIDC invocation passed 2/2), including all 11 US3 restricted-PostGIS cases. The tests contain no skip markers. CI creates a dedicated synthetic database, applies guarded migrations and checks the restricted runtime role. T038 bounded C-collation keyset, exact pins, source/layer availability and native WKB, and T039 controlled test-only refresh/rollback under consistent transaction locks are verified on actual SQL, not the contract double. T042 independently consumes 4,000 stable IDs with page size 97, typed values, native CRS, exact detail and independent stale-pin rejection, firstly through ASGI and then through the actual restricted PostGIS relay. Independent review of the exact runtime commit found no blocker in SQL, transaction locks, current authority, SDK or revision integrity. A web detail-404 revalidation improvement is tracked for US4.

SC-003 **PASS**: `apps/api/tests/integration/spatial/test_features.py` proves complete 10,000 primary point, line and polygon stable IDs exactly once, independently expected typed attributes/native geometry and exact detail, cursor failures, empty and unavailable state. SC-008 **PASS**: `apps/api/tests/integration/spatial/test_pinned_reads.py` exercises both content/schema-only refresh, metadata rename unaffected pins, both real reader/refresh competing orders without mixed state and failure rollback; `test_consumer.py` proves independent API-only consumption on the restricted role. No development or production data touched. Full CI for exact runtime `52cee0b` completed SUCCESS (3/3 jobs). The validate job independently passed all 401 static Python cases, 166 real integration/performance cases (one existing skip), all 30 SDK and 24 web cases, production build, contract regeneration, scope/architecture/docs, 8 Playwright cases and 1 bootstrap case, security-surface and tenant-timing evidence. The separate backend job passed the live OIDC 2/2. Documentation-only acceptance commits preserve the tested runtime; promote only the verified integration branch, not main. No deployment.

## US4 checkpoint (T043–T050)

US3 final docs-only verified integration `789cfcd5722c0ad41d3b149e2a32061ba2e8b0a9` passed all three CI jobs ([run 44322047857](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44322047857)). T046: six actual ASGI contract tests failed on the absent history route, then passed after implementing project.read, bounded ascending UUID keyset and exact safe CatalogChange wire serialization (no internal source/layer FKs, raw records/geometry or physical details). T043/T044/T045 add 8/16/8 real restricted-role integration cases respectively. Initial isolated CI ([run 44323497735](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44323497735)) ran 190 passing cases, eight failing T044 preflight reads to the not-yet-implemented US5 CRS discovery endpoint, and one existing skip. The future CRS lifecycle assertions are assigned to T053/T057; all 16 US4 lifecycle cases and all current history/pinned-read security assertions remain. The corrected exact candidate `d1019b56ca2e09d10446ecea16473703da5e7dd7` ran on isolated ref `validation/r003-us4-d1019b5` ([run 44324749105](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44324749105), [backend job](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44324749105/job/134872937090)). Backend passed 407 static unit/contract/tools/architecture tests, 198 actual integration/performance cases (one existing skip; separate live OIDC 2/2), including all 32 US4 cases. Restricted runtime-role migrations and GUC/ownership/append-only enforcement are exercised, not mocked. T047 verifies all 13 current spatial routes: each read project.read, register/update/create/rename/retire Layer project.edit, retire Source project.manage, all human mutations use CSRF and bearer mutations use current credential ceiling/current principal. T048 real migration/RLS tests cover all five spatial tables, missing/wrong project GUC, pooled reset, sibling/cross-org/project reads and writes, composite ownership and source references, no runtime update/delete/truncate of catalog history. T049 SDK seven tests red on missing function then green 37/37; web tests red on absent history/latch and green 31/31; scoped actor/project cache protection, exact old/new scalar and revision display, history refresh on source and Layer command, and feature detail 404 blocks stale values until explicit current metadata revalidation. No development/production data touched.

SC-005 **PASS**: `apps/api/tests/integration/spatial/test_authorization.py`, `test_lifecycle_security.py`, and `test_migration_rls.py` prove current human and applicable service grant/membership/credential-ceiling/CSRF behavior, denied and dual-authorized cross-project ID/link substitution, archive/delete/suspend/move/current-grant and credential revocation race ordering, no data leak or mutation, pinned reads cannot retain old authority, and fail-closed restricted-role RLS/GUC isolation. All current negative cases run on actual PostGIS.

SC-006 **PASS**: `apps/api/tests/integration/spatial/test_change_evidence.py` proves seven committed catalog mutation types with exact safe old/new/revision/actor/time and linked success audit, project-scoped UUID continuation and retirement visibility; independently injected failures after real evidence append roll back Layer rename and CRS correction atomically; actual lock-wait concurrent CAS commits exactly one mutation/audit, stale/denied/no-op/dependency conflict append nothing, and runtime UPDATE/DELETE/TRUNCATE on evidence is denied. All eight tests run on actual PostGIS. Restart/registration interruption convergence remains SC-009; final benchmark and browser acceptance remain later gates.

Full CI for exact runtime `d1019b5` completed SUCCESS (3/3 jobs). The Node 26 validate job independently passed 407 static Python and 198 real integration/performance cases (one existing skip), 37 SDK and 31 web, production build, deterministic contract regeneration, architecture/scope/docs, 8 Playwright cases and one bootstrap case, and security/timing checks. Independent read-only review of the exact candidate found no acceptance/production blocker (scope/order/count defenses, safe immutable revision decode and wire, current authentication/CSRF permission gates, all current route and lifecycle negative matrices, real audit/rollback/lock/CAS/RLS protections, scoped history UI and detail-404 revalidation). Preserve the tested runtime in the docs-only acceptance commit. Verified integration branch only, no main promotion or deployment.


## Final runtime acceptance — 2026-11-18

Exact runtime candidate `ea18f13722beeaa17e9c53b9a83a3df7c12db595` passed
[CI 44336830562](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44336830562)
(all three jobs). [Backend job](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44336830562/job/134915715763)
passed 446 static unit/contract/tools/architecture tests, 233 actual restricted-role
integration/performance cases and one pre-existing opt-in skip; the separate live
OIDC invocation passed 2/2. The Node 26 validate job independently passed the full
root workflow: 40 SDK tests, 35 web tests, lint/typecheck/build, the same 446 static
and 233 integration/performance cases, 11 browser journeys plus one bootstrap
journey, deterministic contract regeneration, migration cycle, scope/architecture/
docs, secret-surface and tenant-timing gates. Gitleaks passed. Three new browser
journeys exercise real OIDC/catalog/Layer/native and transformed inspection,
history/CAS, explicit stale-pin handling and wrong/deleted-project access; the
stale 409 UI injection is labeled test-only, while real pin refresh/concurrency is
independently covered by the restricted SQL suite.

T051–T058 freeze independent controls and verify the immutable six-definition/
eight-directed-edge registry, current scoped discovery, exact pipeline function
and explicit output SRID. Each operation joins original scoped/pinned native WKB,
validates all input/output/intermediate vertices and trusted regional manifest
provenance, changes only a bounded response copy, and rejects unsupported edges,
definition-only CRS, dimensions/families and out-of-area inputs. Source EWKB,
attributes, metadata/pins and history remain unchanged. Registry/wire contract
tests proved missing-route/unavailable-runtime RED before implementation.

### SC-004 measured independent controls

PostgreSQL 18.7, PostGIS 3.7.0, PROJ 9.9.0 with NETWORK_ENABLED=OFF. Both CI jobs
record the actual observed image, not just a requested tag:
`postgis/postgis@sha256:fe440a27c6567aefa932e988962e5827bb2c29e4b97dac2ca5268f5eafe10262`.
All 44 directed independent controls and 16 additional LineString/Polygon vertex
comparisons passed (60 observations). Analytic Web Mercator targets and published
DMS/projected VN-2000 targets are independent of the runtime transform. Inverse
checks start from published targets; these are not roundtrip-only claims.

| Directed edge | Operation | Maximum measured residual | Tolerance | Unit |
| --- | --- | ---: | ---: | --- |
| 4326 -> 3857 | epsg-1024-forward | 7.45058059692e-09 | 0.001 | metre |
| 3857 -> 4326 | epsg-1024-inverse | 2.84217094304e-14 | 1e-08 | degree |
| 4756 -> 4326 | epsg-6960-forward | 1.55598435 | 3 | metre |
| 4326 -> 4756 | epsg-6960-inverse | 1.55628658 | 3 | metre |
| 5899 -> 4756 | epsg-5899-inverse-tm3 | 0.18943416 | 1 | metre |
| 4756 -> 5899 | epsg-5899-forward-tm3 | 0.189424228172 | 1 | metre |
| 5899 -> 4326 | epsg-5899-to-4326-via-6960 | 0.12948302 | 1 | metre |
| 4326 -> 5899 | epsg-4326-to-5899-via-6960 | 0.128818984165 | 1 | metre |

All 30 real CRS integration cases passed, including strict boundaries, every
agreed native-invalid fixture, trusted provenance, native storage equality,
page/detail/continuation metadata, explicit operation identity and scoped
discovery lifecycle. VN-2000 applicability remains restricted to the documented
Quang Ninh control-fixture rectangles; this is not survey-grade certification or
a claim over all Vietnam positions. UTM48N/49N remain definition-only.

### SC-007 measured reference benchmark

The owner explicitly directed testing on GitHub. The accepted
[reference profile](reference-fixture-profile.md#benchmark-environment) makes CI
authoritative for regression; no Windows hardware was prescribed. Observed
runner `GitHub Actions 1000023393`, Linux x86_64, Python 3.13.18,
with the exact pinned PostgreSQL/PostGIS/PROJ runtime above. The report records
all three fixture manifests and both revision pins (4,000 Point + 3,000 LineString
+ 3,000 Polygon = 10,000). Each of 20 scenarios uses five warmups and 100 measured
complete in-process ASGI HTTP responses against the real restricted
`openvietgis_runtime` role with RLS active, no profiler and no catalog writes.

This claim covers warmed sequential application/serialization/job-local database
execution. It excludes browser/WAN/socket/TLS latency, concurrent production load
and the user's Windows workstation. Budgets are unchanged: catalog/detail p95
<=1,000 ms; page100 p95 <=2,000 ms.

| Scenario | p50 ms | p95 ms | max ms | p95 budget ms |
| --- | ---: | ---: | ---: | ---: |
| LineString_feature_detail_3857 | 10.284934 | 12.195155 | 15.100894 | 1000 |
| LineString_feature_detail_4326 | 9.073028 | 10.154609 | 10.545159 | 1000 |
| LineString_layer_detail | 7.807111 | 8.438721 | 10.056590 | 1000 |
| LineString_page100_3857 | 21.811972 | 23.387397 | 24.952883 | 2000 |
| LineString_page100_4326 | 12.606911 | 14.366297 | 16.471738 | 2000 |
| LineString_source_detail | 6.215383 | 7.805020 | 8.459215 | 1000 |
| Point_feature_detail_3857 | 10.806529 | 12.926743 | 14.739312 | 1000 |
| Point_feature_detail_4326 | 9.282279 | 11.264104 | 13.704317 | 1000 |
| Point_layer_detail | 6.922408 | 8.870443 | 11.595054 | 1000 |
| Point_page100_3857 | 20.136812 | 22.253421 | 25.661839 | 2000 |
| Point_page100_4326 | 11.961391 | 14.420376 | 16.208004 | 2000 |
| Point_source_detail | 6.307119 | 7.129948 | 7.545807 | 1000 |
| Polygon_feature_detail_3857 | 10.255249 | 12.716665 | 13.708363 | 1000 |
| Polygon_feature_detail_4326 | 9.142284 | 10.913697 | 13.024626 | 1000 |
| Polygon_layer_detail | 7.904134 | 9.252098 | 10.711760 | 1000 |
| Polygon_page100_3857 | 26.475905 | 28.681498 | 106.795299 | 2000 |
| Polygon_page100_4326 | 13.646131 | 15.370115 | 16.144933 | 2000 |
| Polygon_source_detail | 5.766386 | 6.681415 | 6.813484 | 1000 |
| layer_list | 8.621550 | 9.826318 | 11.688107 | 1000 |
| source_list | 6.582464 | 7.763107 | 8.937654 | 1000 |

All 20 budgets passed. Raw exact-run observations and immutable fixture/version/
pin details are in [the measured report](evidence/ci-44336830562.json), also
printed as R003_SPATIAL_BENCHMARK and R003_CRS_CONTROLS in the backend job log.

### SC-009 interrupted registration and restart

All four tests in `apps/api/tests/integration/spatial/test_restart.py` passed.
Fresh app/pool recreation twice preserves committed source/Layer metadata, exact
native rows, page/detail results, pins and immutable history. Three independent
interruption cases terminate only the observed restricted backend in guarded
`openvietgis_test`, after an actual source, feature or change INSERT. The failed
transaction commits no ready partial source, fields, features or success audit;
previously committed data stays exact. A new app retries registration to a
complete 3,000-feature source once; duplicate retries conflict safely and another
app recreation preserves the successful retry. No shared DB server was restarted.

### Per-criterion acceptance

| SC | Verdict | Current evidence |
| --- | --- | --- |
| SC-001 | PASS | `test_sources.py`: all supported/invalid manifests, exact metadata and native storage, correction/rollback. |
| SC-002 | PASS | `test_layers.py`: two Layers share exact rows/pins; independent retirement, dependency and cross-link races. |
| SC-003 | PASS | `test_features.py`, `test_pinned_reads.py`: complete 10k IDs once, exact typed page/detail, both stale domains/concurrency. |
| SC-004 | PASS | `test_crs_controls.py`, independent `spatial_controls.py`: every approved edge/control and negative matrix; measured above. |
| SC-005 | PASS | `test_authorization.py`, `test_lifecycle_security.py`, `test_migration_rls.py`: human/service/current scope/credential/RLS. |
| SC-006 | PASS | `test_change_evidence.py`: atomic exact safe old/new/revisions, audit/actor/time, immutable runtime grants, real CAS/rollback. |
| SC-007 | PASS | `test_spatial_benchmark.py`: full 10k, 20 scenarios, 100 measured each; exact environment and results above. |
| SC-008 | PASS | Independent ASGI and restricted SQL API-only consumers `test_spatial_consumer.py` / `test_consumer.py`; no R004 dependency or physical details. |
| SC-009 | PASS | `test_restart.py`: four actual recovery/interruption cases; no partial commits, exact committed state/retry preservation. |

### Functional requirement and convergence trace

Paths below are repository-root relative under the spatial domain/adapters/test
packages unless stated; the accepted contracts remain
`contracts/spatial-catalog-api.yaml` and `contracts/catalog-semantics.md`.

| Requirements | Implementation | Evidence |
| --- | --- | --- |
| FR-001, FR-002, FR-003, FR-004 | DataSource/Layer domain IDs, project ownership, safe catalog/schema/count/extent service and SQL | domain/source/migration/RLS contracts and integration |
| FR-005, FR-006, FR-007, FR-008 | Private trusted fixture registry, native SQL validation, atomic materialization and explicit ready/reason state | fixture/domain/source tests and unsupported-registration contract |
| FR-009, FR-010, FR-011 | Layer independent identity/revision/CAS, shared source lock and retirement guard | Layer contracts, same-source row equality, both source-retire/create race outcomes |
| FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019, FR-020 | Native geometry/CRS domain, finite definitions/direct profiles, approved response pipelines, all-vertex/provenance validation and no native mutation | CRS/domain/source native fixtures, all independent directed controls and negative matrix |
| FR-021, FR-022, FR-023 | Explicit technical support, lifecycle availability and current permission-separated Layer capabilities | capability/domain/Layer/service actor tests |
| FR-024, FR-025, FR-026, FR-027, FR-028 | Exact typed serializer, bounded C keyset, both pins, explicit page/detail scope and safe response envelope | full 10k traversal, independent consumer, stale/empty/cursor/detail, protected SDK/web/browser |
| FR-029, FR-030, FR-031, FR-032 | Current R002 tenant/actor/credential/grant checks, project proof, FORCE RLS and composite ownership | real human/service authorization, lifecycle and revocation races; no disclosure/writes |
| FR-033, FR-034, FR-035, FR-036, FR-037 | Transactional safe immutable history/audit, revisions/CAS, safe errors, durable registration/retry | change-evidence, race, interrupted-registration/restart and browser history/conflict tests |
| FR-038 | Domain/port/adapter boundary; public logical source/Layer/read contract; no renderer/importer/editor/module coupling | architecture/scope guards and independent public-contract consumer |

Independent read-only final review approved runtime exact `ea18f13`, then parsed
the actual backend raw logs to independently verify measured controls, image and
all 20 performance budgets. Convergence assessed 38 FRs, nine SCs, 22 acceptance
scenarios across five stories, ten edge cases, all 64 tasks, seven implementation
decisions plus seven technical-context categories, eight constitutional principles,
eight architectural boundaries and nine quality gates. Additional build findings:
missing 0, partial 0, contradicts 0, unrequested 0; no new convergence tasks or empty
phase were appended. Correct feature prerequisites resolved with authorized
process-only RemoteSigned; no extension hooks exist. Graphify updated 375 files,
3,815 nodes/12,837 edges/164 communities; local Gitleaks scanned 14 commits with no
leaks, and exact CI secret scan passed.

R003 is converged for internal integration. The final documentation/evidence
closure commit retains this tested runtime and requires its own exact full CI
before fast-forward verified-main promotion. No deployment is performed; R002's
external unfamiliar-human timing gate remains mandatory before external release.
