# Quickstart Validation: Identity, Organization & Tenancy

**Feature**: 002-identity-organization-tenancy

This guide describes the target validation experience after implementation. It extends the Spec 001
foundation and proves human identity, tenant isolation, scoped authorization, invitations, machine
identity, audit, and self-host bootstrap end to end.

## Supported development baseline

- Node.js 26
- pnpm 12.21
- Python 3.13 through uv
- Docker with Compose
- PostgreSQL 18 + PostGIS 3.7
- Keycloak 26.8.2 reference OIDC profile

All development identities, realms, credentials, and bootstrap values are synthetic test-only data.
No production identity provider or production data is required.

## 1. Configure local development

Copy the example configuration and set the test-only bootstrap secret:

```powershell
Copy-Item .env.example .env
```

The implementation must document development values for:
- OIDC issuer/client ID/client secret for the reference Keycloak realm;
- application session signing/CSRF secret;
- one-time self-host bootstrap secret;
- migration-owner database URL;
- non-superuser runtime database URL.

The checked-in example MUST contain placeholders or clearly synthetic development-only values.

## 2. Start PostgreSQL and reference OIDC provider

Target command:

```powershell
docker compose -f infra/dev/compose.yaml -f infra/dev/compose.identity.yaml up -d postgres keycloak
```

Expected result:
- PostgreSQL is healthy;
- the Keycloak development realm is imported;
- the OIDC discovery endpoint is reachable;
- at least two synthetic human identities are available for invite/multi-tenant testing.

Keycloak is a validation fixture only. Product code must consume generic issuer/client configuration.

## 3. Apply migrations using the migration-owner identity

```powershell
pnpm db:migrate
```

Expected result:
- identity, org, workspace, audit, and platform schemas migrate from zero to head;
- tenant-sensitive tables have row-security policies enabled;
- the API runtime database role is not superuser and has no BYPASSRLS;
- migrations remain separate from runtime application credentials.

## 4. Start API and web application

API:

```powershell
pnpm dev:api
```

Web:

```powershell
pnpm dev:web
```

Open the documented local web URL.

Expected result before login:
- no tenant resource is visible;
- login offers configured OIDC providers;
- the browser does not receive/store provider access or ID tokens in application storage.

## 5. Authenticate and bootstrap the first Organization

**P1 prerequisite fixture (FR-051):** T080 exercises normal human Tenant Core using a dedicated
synthetic test database initialized by the tracked test fixture. Run the actual provider login,
then normal Organization creation (5A) and sections 6–10. Do not require bootstrap in P1 or
implement bootstrap early to satisfy T080. The bootstrap-specific assertions below, including
the one-time authority and anonymous denial, remain mandatory for P2 (T097–T105) and full T113.
A fixture marker is not evidence that bootstrap itself works.

1. Sign in with the synthetic bootstrap Owner identity through Keycloak.
2. Observe that the internal User exists but has no Organization yet.
3. Open the one-time setup flow.
4. Provide the development bootstrap authority and create Organization A.

Expected result:
- one Organization is created;
- the current User becomes its active Owner;
- bootstrap is recorded as initialized;
- a second bootstrap attempt is rejected;
- an anonymous/un-authenticated caller cannot bootstrap even with only network access;
- audit history records the initialization without recording the bootstrap secret.

### 5A. Create an additional Organization through the normal product flow

While still authenticated:

1. Create Organization B from the normal Organization create flow.
2. Confirm the same User becomes B's active Owner atomically.
3. Confirm bootstrap state is unchanged and the one-time bootstrap mechanism is not reused.
4. Confirm an AuditEvent records the Organization creation.

Expected result:
- the User now belongs to both A and B;
- both Organizations have independent Owner memberships;
- normal Organization creation works after bootstrap is already consumed.

## 6. Create Workspace and Project

As Organization A Owner:

1. Create Workspace A1.
2. Create Workspace A2.
3. Create Project P1 inside A1.
4. Move P1 to A2.
5. Remove P1 from Workspace grouping.

Expected result:
- P1 keeps the same Project ID and Organization A ownership throughout;
- no ordinary operation can change P1 to another Organization;
- Workspace deletion is rejected while active Projects remain grouped inside it.

### 6A. Prove Owner-controlled Organization lifecycle

1. As an Admin in Organization B, attempt to suspend/delete B and confirm denial.
2. As an Owner, suspend B and confirm normal tenant mutations are rejected.
3. Restore B to active.
4. Soft-delete B and confirm references/audit remain recoverable while normal tenant mutation stays blocked.

Expected result:
- lifecycle transitions are Owner-controlled;
- no permanent purge occurs in Spec 002;
- Last Owner and historical audit invariants remain intact.

## 7. Prove Workspace grant inheritance

1. Create/activate a Member in Organization A.
2. Grant that Membership the Viewer resource role at Workspace A1.
3. Place P1 in A1.
4. Confirm the Member can read P1.
5. Move P1 to A2 without giving another grant.
6. Confirm inherited P1 access disappears on the next protected request.
7. Add a direct Project Viewer grant to P1.
8. Confirm P1 remains visible even when it moves again.

Expected result:
- effective permissions are an additive union;
- inherited grants are computed dynamically, not copied;
- no narrower grant subtracts a broader permission.

## 8. Invitation recipient binding and revocation

As an authorized inviter:

1. Create an invitation targeted to `member-a@example.test` with Organization role Member and one
   optional Project Viewer grant.
2. Copy the one-time invitation secret.
3. Attempt acceptance while authenticated as a different synthetic identity.
4. Confirm acceptance is rejected.
5. Authenticate as the intended verified email identity and accept.
6. Confirm Membership and optional grant are created atomically.
7. Attempt to reuse the same invitation and confirm rejection.
8. Suspend or revoke the new Membership.
9. Retry a protected Project request immediately.

Expected result:
- wrong-recipient acceptance fails;
- valid acceptance succeeds once only;
- the next protected request after suspension/revocation is denied without waiting for login expiry.

## 9. Prove multi-Organization switching

Using one User who has active Memberships in Organization A and Organization B:

1. Open Organization A route/context and inspect visible resources.
2. Switch to Organization B.
3. Confirm B role/grants apply.
4. Attempt direct navigation to an A Project while B is active.

Expected result:
- active Organization is explicit in navigation/API context;
- the User does not store one global active Organization;
- unauthorized cross-tenant Project identifiers disclose no protected data.

SC-001 target: switch and reach correct context in under 10 seconds.

## 10. Prove RLS defense-in-depth

Automated integration validation must:
1. connect as the same non-BYPASSRLS runtime database role used by the API;
2. establish actor/Organization transaction context for Organization A;
3. query each RLS-protected table;
4. verify Organization B rows are invisible/unmodifiable;
5. repeat without Organization context and confirm tenant-sensitive paths fail closed;
6. reuse pooled connections across A/B transactions and confirm context does not leak.

Minimum protected tables are listed in [data-model.md](data-model.md).

## 11. Issue and revoke a Service Credential

As an authorized Organization A administrator:

1. Create Service Principal `integration-check`.
2. Give it a scoped Project/Workspace grant.
3. Issue one credential with a permission ceiling that is a subset of principal grants.
4. Save the returned secret once.
5. Use it for an allowed API action.
6. Attempt an out-of-scope action and a request to Organization B.
7. Revoke the credential.
8. Retry the previously allowed request.

Expected result:
- allowed action succeeds;
- permission ceiling never expands principal grants;
- cross-tenant and out-of-scope actions fail;
- revoked credential fails on the next request;
- secret cannot be retrieved again from the credential metadata API.

## 12. Inspect audit history

Retrieve Organization A security audit history.

Verify events exist for at least:
- bootstrap;
- membership role/status changes;
- Owner transfer attempts/success;
- invitation create/accept/revoke;
- resource grant create/revoke;
- Service Principal/credential create/revoke;
- sensitive authorization denial tested by the feature.

Expected result:
- actor type is distinguishable as human/service/system;
- actor display snapshot remains understandable after Membership/credential revocation;
- no raw session, OIDC, invitation, credential, or bootstrap secret appears in audit metadata.

## 13. Validate Last Owner concurrency

Automated integration test must race two operations that would otherwise remove/downgrade the last
remaining active Owner.

Expected result:
- at most one transition can commit if another active Owner remains;
- no committed state ever leaves an active Organization with zero active Owners.

## 14. Run the full validation workflow

```powershell
pnpm validate
```

Spec 002 expands the existing root validation to include:
- existing Spec 001 static/unit/architecture checks;
- OpenAPI contract validation and generated client-type freshness;
- OIDC/session/CSRF tests;
- foundational append-only AuditEvent storage and tenant-RLS tests before the P1 gate;
- RequestedActorContext serialization/restoration tests without introducing a worker runtime;
- domain/authorization unit tests;
- real PostgreSQL RLS integration tests using the runtime role;
- invitation concurrency/recipient tests;
- Service Credential scope/revocation tests;
- audit immutability tests;
- Keycloak-backed browser E2E for the P1 tenant flow;
- bootstrap and P2 machine-identity acceptance;
- scope guard ensuring no GIS/Layer/Map/Editing/Processing/Field feature leaks into Spec 002.

## 15. Performance/scale acceptance

Run the planned authorization benchmark with:
- one actor;
- one active Organization;
- at least 50 relevant/irrelevant grants across Organization/Workspace/Project scope;
- Project access checks that exercise dynamic Workspace inheritance.

Target:
- permission resolution overhead p95 <= 50 ms in the repository integration benchmark;
- no permission cache is required to meet the target;
- revocation remains effective on the next request.

User-facing SC-001/SC-004/SC-011/SC-013 time limits remain authoritative.

### SC-013 unfamiliar-user evidence

SC-013 is not satisfied by a Playwright stopwatch alone. Use a reviewer who has no prior OpenVietGIS
product orientation and give them only the minimal product entry point plus ordinary in-product
navigation. Time the reviewer completing:

1. switch Organization;
2. create a Workspace;
3. create a Project;
4. view their own membership.

Pass condition:
- all four actions complete in under 5 minutes;
- no coaching from someone already familiar with the product;
- record reviewer role, elapsed time, blockers, and result in
  `checklists/unfamiliar-user-timing.md`.

## 16. Logical isolated-deployment parity

Run the same domain/contract acceptance fixtures in isolated-tenant configuration.

Expected result:
- no product-domain behavior changes;
- Organization IDs, Memberships, grants, invitation semantics, Service Principals, and audit actors
  remain identical;
- no production dedicated database provisioning is required for Spec 002.

## 17. Foundation-sample retirement

After the Spec 002 end-to-end vertical slice passes:
- remove the disposable FoundationSampleRecord UI/API/client surface and its persistence table;
- preserve Spec 001 health, architecture, CI, reset, documentation, and validation foundations.

The application must still pass the historical platform-foundation architecture/security gates after
the disposable sample is removed.

## 18. Partial P1 takeover validation — 2026-11-18

Code checkpoint: 3a74fa7 on takeover/002-identity-tenancy. **This is partial evidence, not T080 or full quickstart acceptance.**

| Check | Observed result |
| --- | --- |
| Ruff | pass |
| mypy | pass, 60 source files |
| Backend unit, contract, tools, architecture | 104 passed |
| Backend integration, dedicated test database | 39 passed |
| Client grant/invitation tests | 12 passed in isolated agent validation; TypeScript strict compilation passed |
| Runtime-role isolation | application engine checks actual current_user; tests verify six tenant RLS tables, A/B/no-context on same connection, audit immutability, cross-tenant FK rejection |
| Concurrency and identity | invitation double acceptance, last Owner downgrade, identity unlink and conflicting link audit persistence tested |
| HTTP | cross-tenant non-disclosure, same-tenant 403, recipient binding, one-time accept, next-request membership revoke tested with runtime role |
| Browser P1 | NOT run; browser test code exists/typechecks only |
| Full quickstart, Node 26 pnpm validate, P2, convergence | NOT executed |

Dedicated test database openvietgis_test on loopback port 54330; the development DB was not mutated. Migration sequence includes additive 0003a_identity_unlink_security following 0003, before future 0004. Migration/admin credential used solely for setup/migrations/assertions; protected API and dedicated runtime tests use openvietgis_runtime. Test fixtures are synthetic. OIDC provider discovery was reachable, but this is not proof of interactive login. Frozen dependency installation is blocked by minimumReleaseAge policy; no override was applied. Do not advance P2 or claim T080 until all P1 requirements, including browser, are evidenced.

## 19. P1 backend verification — 2026-11-18

Code checkpoint **830dea5** on takeover/002-identity-tenancy. This supersedes section 18's partial backend evidence; it does not establish T080 acceptance.

| Check | Observed result |
| --- | --- |
| Ruff / mypy | pass; 60 source files |
| Backend unit, contract, tools and architecture | 121 passed |
| Integration against dedicated PostgreSQL test database | 58 passed, runtime-role API/repository access; admin only for fixtures, migrations and assertions |
| Contract, runtime scope, architecture, documentation guards | pass |
| Node 26 isolated SDK and protected-query tests | 20 passed; strict TypeScript compilation of those modules |
| Repository context | explicit actor/tenant membership proof, transaction-local context, pooled A/B/no-context reuse, invalidation on transaction changes |
| Independent review follow-up | fixed empty PATCH and missing/foreign scope fail-open; additionally required verified context for invitation expiry mutation |
| Browser acceptance and full frontend lint/typecheck/build | NOT run; browser fixture pinned to accepted Node and local test OIDC; stale-cache/revocation regression added |
| T080 / P2 / T115 / main integration | NOT accepted or executed |

The integration suite covers T057/T059/T070/T073/T074 and the protected repository context evidence for T076/T078. These tasks are checked. T062/T069/T079 and T080 remain unchecked. The original dirty worktree and main remain unchanged.

Portable official Node 26.13.1 is installed in the ignored local-only toolchain directory `C:/code/openvietgis-r002-browser/dist/toolchains/node-v26.13.1-win-x64`; SHA-256 of official ZIP `E2EDDA75BFB089654705CF65A13B58933BFD5F57148E8EBDA916F58A2474F1F7` and official release signing-key fingerprint `5BE8A3F6C8A5C01D106C0AD820B1A390B168D356` were verified. Actual Node 26 runtime check passed. pnpm 12.21 is available in the selected process. Normal frozen install remains blocked by unchanged minimumReleaseAge for @tanstack/query-core and @tanstack/react-query 5.108.0 (published Nov 17 13:43 UTC; expected eligible around Nov 18 20:44 Vietnam time, verify rather than assume). Do not override the policy or use already-installed ineligible packages. On next eligible run, from the takeover worktree using cmd.exe:

```bat
set "PATH=C:\code\openvietgis-r002-browser\dist\toolchains\node-v26.13.1-win-x64;%PATH%"
node tools/check_node_runtime.mjs
pnpm.cmd install --frozen-lockfile
pnpm.cmd validate:ts
pnpm.cmd validate:e2e
```

Run each step only if its prerequisite succeeds. Confirm local synthetic test OIDC provider and dedicated test database before browser execution; do not log OAuth secrets. Capture actual results and independent review against all T080 requirements. P2 remains gated.

## 20. P1 runtime evidence and performance checkpoint — 2026-11-18

Code HEAD **872c4ad** (takeover/002-identity-tenancy). P1 remains open pending genuine browser acceptance; P2 has not started.

| Check | Observed result |
| --- | --- |
| Python static, unit, contract, tools, architecture | 134 passed; Ruff, mypy (60 files), contract/scope/architecture/docs guards pass on final code HEAD after test-only cookie patch |
| Restricted-runtime integration and performance | 64 passed, 1 opt-in test skipped in default run (63 integration + one benchmark) |
| Real Keycloak authorization-code + PKCE backend flow, separately opted in | 1 passed, 6.54s; two real logins stable internal User ID, actual token exchange, opaque session/hashed persistence, /me, CSRF logout and replay denial |
| RequestedActorContext | actual JSON boundary for human, service envelope, system; no cached authority restored |
| Authorization benchmark | 63 grants (3 relevant, 60 irrelevant), 150 fresh transactions; p95 5.225ms combined, worst phase 5.746ms; independent targeted repeat 7.954ms combined, worst 9.053ms |
| P1 HTTP acceptance | next-request grant revoke and membership suspend/revoke, inherited access disappears on move and direct grant survives move, foreign payload non-disclosure; 5 added integration tests pass |
| Browser | 3 tests collected and independently strict typechecked with policy-eligible Playwright/TS; measured SC-001/SC-004 paths implemented, NOT executed |
| T080 / P2 / T115 / main integration | NOT accepted or executed |

Before optimization, the benchmark failed with p95 80.235ms. The permission resolver now obtains live membership, valid tenant placement and applicable grants in one SQL statement after the unchanged mandatory repository context checks. No permission cache or RLS relaxation. The same benchmark and threshold passed twice; independent static review and complete runtime regression passed. T106 is checked; root `validate:integration` now includes performance tests.

The opt-in backend test uses the tracked synthetic local Keycloak fixture and dedicated test DB; it does not launch the frontend or use a mocked token exchange. Test-only cookie handling emulates loopback browser behavior for Secure provider cookies exclusively on the exact pinned local realm, checked against other hosts/ports/realms. No change to production cookie security. Run with:

```bat
set "OPENVIETGIS_LIVE_OIDC=1"
uv run --offline --project apps/api python -m tools.run_with_test_database pytest apps/api/tests/integration/identity/test_live_keycloak_oidc.py -o addopts= -q --show-capture=no
```

Reference Keycloak discovery and real login work on existing synthetic container; its Docker health status was unhealthy because the management health endpoint was disabled. Compose configuration now enables health and binds provider publishing to loopback only; config validation passed, no existing container was recreated. Verify runtime health at the next safe test-fixture startup without disrupting another active user/container. The E2E seed now refuses non-test or mismatched DB targets before connecting. Browser timing assertions cover three actual organization switches (<10s each) and intended invite acceptance (<180s). Do not claim these timings until browser execution. Section 5 explicitly separates FR-051 P1 synthetic initialized fixture from mandatory P2 bootstrap acceptance.

Next: normal age-gated frozen pnpm install on signed Node 26 when eligible (as section 19); verify actual Chromium/Keycloak, run full frontend lint/typecheck/test/build and E2E; record timings, independent review and all T080 evidence. Do not begin P2, retire sample, or promote main before gates.

## 21. P1 independent hardening checkpoint — 2026-11-18

Code HEAD **61bacc6**, authoritative takeover branch. **77/115 checked, 38 open**; this checkpoint strengthens evidence but does not close any remaining P1 acceptance gate.

- Python static/unit/contract/tools/architecture suite: 173 passed, 1 skipped (Windows synthetic symlink creation unavailable); Ruff, mypy (60 files), contracts, scope, architecture and docs guards pass. Full integration + performance: 66 passed, 1 opt-in live OIDC skipped (separate successful run documented in §20). Targeted final P1 audit/log test: 2 passed.
- T107 partial: actual synthetic P1 sensitive HTTP mutations proved raw application session/cookie fragments, CSRF and invitation secrets absent from captured runtime log/stdout/stderr and full selected audit rows. Independent review found pytest's second report handler and raw response assertion diagnostics could leak on failure; root isolated private log capture, drained stdout/stderr, checks audit canaries before assertions, removed raw body messages. Scoped text artifact scanner has 38 passing unit regressions and one symlink skip; no real browser artifacts exist yet. Gitleaks reviewed 55 commits with no unignored leak; one verified noncredential 12-character synthetic prefix recorded by exact historical fingerprint only, no broad exclusion. P2 service/bootstrap and actual browser/evidence artifact scans still required.
- T108 partial: CI prepares local synthetic Keycloak and loopback test PostGIS, guarded migration/runtime role, discovery, pnpm full validate including contract generation, integration and E2E; docker compose config and manifest tests pass. Added the exact takeover branch push trigger/manual dispatch. No remote GitHub CI execution at this checkpoint (local repo has no remote; named GitHub repo absent); private GitHub destination must be authorized before publishing code.
- T111 partial: isolated disposable PostGIS migration cycle and scoped six-schema logical backup/restore passed 1/1 (77.27s), also in the full suite. Preserved data across security-only downgrade, restored exact snapshots and runtime grants/FORCE RLS, verified tenant visibility. Original DB untouched. Independent review found implicit container port publishing; fixed fixture to force dynamic loopback port and verify actual Docker binding before database operations. Re-run observed 127.0.0.1 binding, but Local MCP command timed out before collecting the final result; no new passing claim for that run. Check the disposable test container/process completion before any further local run. This is not full-cluster recovery or P2 migration evidence.
- P1 frontend: account-scoped identity cache, fail-closed membership/invitation/account refetches (paused/error/fetch), fresh scope validation, secret cleanup, successful self-unlink and ambiguous logout revalidate session; ordinary validation/conflict mutation errors preserve form/notice. Agent isolated eligible tooling: 15 helper tests passed; strict helper and E2E TS checks; changed TSX transpilation; four E2E scenarios collected, not executed. No full frontend validation or real browser evidence.
- Graphify refreshed (2243 nodes, 6078 edges); independent review findings addressed, except verification of the loopback migration repeat is pending.

Continue using only eligible signed Node26 dependencies per §19. CI or local browser suite must not bypass dependency age policy: verify eligible release window before frozen install. T062/T069/T079/T080 remain open; P2 and R003 are gated, T107/T108/T111/T112 stay open until their complete acceptance. No main promotion, production deploy, or public publication.

## 22. Supply-chain-compatible frontend dependency pin — 2026-11-18

The active P1 frontend dependency was changed from `@tanstack/react-query` 5.108.0 to the compatible 5.107.1 line because the newer release was still inside the enforced pnpm `minimumReleaseAge` window. This is not a policy bypass: 5.107.1 was already outside the age cutoff, its matching `@tanstack/query-core` dependency is pinned to 5.107.1, and registry integrity metadata was used for both lockfile entries. The product research decision requires TanStack Query 5.x, not 5.108.0 specifically.

On official Node 26.13.1 with pnpm 12.21.0, `pnpm install --frozen-lockfile` passed the supply-chain policy check for all 204 lockfile entries. Local `validate:runtime`, `validate:ts`, and `validate:contracts` passed: SDK 12 tests, web helper 15 tests, strict TypeScript/lint, production Vite build, and generated OpenAPI freshness. This removes the dependency-age blocker only; real Playwright browser acceptance, T062/T079/T080 and full CI remain open until executed on the exact committed head.

## 23. P1 Tenant Core browser gate — 2026-11-18

Exact source HEAD **f2bd300** passed public GitHub Actions run **44221805527** on Linux after the browser synchronization fixes. This closes the P1 execution gate; it does **not** claim P2, full Spec 002 convergence, or main integration.

Evidence on the exact source line:

- Supply-chain gate: Node 26.13.1; frozen pnpm install succeeded with policy-eligible TanStack Query 5.107.1; no minimum-release-age bypass.
- Backend/static: Ruff, mypy (60 source files), contracts/scope/architecture/docs; **175 passed** unit/contract/tool/architecture checks.
- Restricted-runtime PostgreSQL: **67 passed, 1 skipped** integration/performance checks, including tenant/RLS/runtime-role, pool reuse, concurrency, invitation/revocation, audit, migration/restore and authorization benchmark coverage. The opt-in item is exercised separately by the live-provider step.
- Live reference OIDC: **2 passed** against the synthetic Keycloak realm, including code+PKCE/session flow and private credential non-disclosure monitor.
- Frontend: SDK **12 passed**, protected-query/web **15 passed**, strict TypeScript/lint, production Vite build and generated OpenAPI freshness all passed.
- Browser: **8/8 Playwright tests passed in 17.1s** on GitHub Chromium. Local confirmation on the final E2E synchronization diff also passed 8/8 in 19.0s.
- Secrets: GitHub Gitleaks job passed. Browser invitation handoff remains trace/screenshot/video disabled and is never written to test logs/artifacts by the test.

P1 quickstart mapping:

- §§2–4: CI starts isolated PostGIS + reference Keycloak, verifies discovery, applies guarded migrations with separate migration/runtime roles, then starts real API/web for browser tests.
- §5A and §9: browser acceptance signs in through Keycloak, creates multiple normal Organizations under one User and performs explicit Organization route/context switches with the SC-001 threshold.
- §6: browser acceptance creates two Workspaces and a Project, moves/ungroups/archives it while preserving Organization ownership; backend lifecycle/FK tests cover rejected cross-tenant mutations and Owner lifecycle invariants.
- §7: restricted-runtime integration verifies dynamic Workspace inheritance and next-request permission changes without copied grants.
- §8: browser acceptance rejects the wrong verified recipient, accepts the intended recipient exactly once, proves only the granted Project is visible, revokes the Membership without replacing the browser session, then confirms the next protected request is denied and stale protected UI data is hidden during refetch.
- §10: restricted-runtime RLS matrix covers protected tables, A→B→no-context pooled reuse, direct-ID substitution and non-disclosing 403/404 behavior. Foundational AuditEvent RLS and RequestedActorContext serialization/transaction binding are included in the passing backend suites.

Task evidence: **T062, T069, T079, T080 and T108 are checked at this checkpoint.** P1 now unlocks P2 sequencing T081–T105. T107/T111/T112/T113/T114/T115 remain open where their wording requires P2 secrets/migrations/bootstrap, all-scenario evidence, full root validation or convergence. The external Codex reviewer service returned HTTP 429 during the attempted independent read-only review; no independent-agent review is claimed. Coordinator evidence review found no unmet P1 test gate, but a separate independent review should still be attempted before final T115/main promotion.


---

## 2026-11-18 P2 Service Identity checkpoint

T081-T090 are implemented and locally validated on the dedicated `takeover/002-p2-service` worktree. Evidence at this checkpoint:

- Service credential/permission-ceiling unit tests: **6 passed**.
- Service Identity restricted-runtime PostgreSQL integration: **5 passed**, covering forced RLS, cross-tenant FK rejection, invalid hash/permission/expiry constraints, one-time issued secret storage as digest+safe prefix, `last_used_at`, allowed scoped access, real same-tenant out-of-scope denial, cross-tenant denial, credential revoke on the next request, principal revoke, and human-only service administration.
- P1 tenant HTTP regression subset after shared auth/RLS changes: **12 passed**.
- Python unit/contract regression: **111 passed**; Ruff and strict mypy passed.
- Client SDK/web lint, strict TypeScript and tests passed: SDK **13 passed**, web **15 passed**.
- Spec 002 contracts, architecture boundaries, and runtime scope checks: **OK**.
- Local shell currently provides Node 24, while the repository requires Node 26. Node-26 root validation remains a CI/final-gate responsibility under T114; this checkpoint does not claim T114.

Task evidence: **T081-T090 checked**. Audit T091-T096, bootstrap T097-T105, and final convergence remain open.


---

## 2026-11-18 P2 Audit read checkpoint

T091-T094 and T096 are implemented on the dedicated audit worktree. Evidence:

- Audit redaction unit tests: **2 passed** for session, OIDC/provider token, invitation, service credential and bootstrap secret surfaces, including nested metadata.
- Restricted-runtime PostgreSQL audit read/snapshot integration: **2 passed**, proving tenant filtering/RLS, permission denial, stable newest-first ordering/limit, and human/service/system display snapshots after human/service revocation.
- P1 audit + Service Identity regression: **7 passed** after the repository/read changes.
- Ruff and strict mypy: **passed**.

Task evidence: **T091-T094 and T096 checked**. T095 remains open until bootstrap audit wiring is implemented and verified.

---

## 2026-11-18 P2 Bootstrap checkpoint

Code commit `22d1615` was verified by [GitHub CI 44232402147](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44232402147), all three jobs successful. Status/read-lock/update, atomic first Organization/Owner/audit commit, session plus bootstrap authority and CSRF, and authenticated UI have been implemented. Restricted runtime integration covers anonymous, secret-only, wrong authority, invalid CSRF, success-once, reuse denial, stored state/owner/audit, two concurrent requests with exactly one successful commit, immutable state transition. Browser runs separately against a guarded uninitialized test fixture rather than mixing it with P1 initialized flows.

- GitHub Python static/unit/contract/tools/architecture: 192 passed; restricted-runtime integration/performance: 77 passed, 1 skipped; opt-in live OIDC: 2 passed. Ruff and mypy: 66 source files, green.
- Node 26 frontend: SDK 14, web 15 tests passed; lint, TypeScript, build and generated contracts passed. Existing browser E2E 8/8 (12.8s), separate first-owner OIDC/bootstrap browser 1/1 (2.8s total suite), including wrong authority, successful owner context and reuse denial. Test enforces SC-011 under 300 seconds and attaches measured timing; the 2.8s suite duration is not a claim about fresh infrastructure installation time.
- Gitleaks green; test suite uses synthetic secrets only. No final T107 evidence claimed.

Task evidence: **T097-T104 checked**. T095 still needs real service-actor mutation audit/snapshot evidence, T105 parity and final gates remain open. T112 remains open for the separate unfamiliar-user exercise and remaining timing evidence.

## 2026-11-18 P2 runtime audit and logical deployment parity checkpoint

Code commit `d4624d5` passed all jobs in [GitHub CI 44233392909](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44233392909). Service actor Workspace/Project create and update now retain the verified credential context through domain and persistence calls; audit append checks the bound service actor, tenant and credential instead of accepting an unauthenticated actor. The real restricted-runtime HTTP regression verifies four service-authored mutation events, stable historical actor display/tenant after credential and principal revocation, and the administrator's principal/credential audit events. Bootstrap audit was verified in the prior checkpoint. Logical shared (extra tenant present) vs isolated (single-tenant fixture universe) acceptance exercises the same identity, membership, invitation, grant, scoped service access/revocation and audit contracts and compares normalized outcomes. This is not physical dedicated deployment provisioning.

Task evidence: **T095 and T105 checked**. All P2 functional tasks T081–T105 are implemented and tested. T107 and final T109–T115 remained open at this checkpoint.

### P2 secret-surface completion

Candidate `0cd16b1` passed backend, validate and secrets in [GitHub CI 44234019284](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44234019284). Synthetic P2 service/bootstrap runtime and audit scans supplement the P1 tests. The explicit evidence scan reported all three artifacts clean: P1 Playwright JSON, bootstrap Playwright JSON and Keycloak log. Git history secret scan also passed. Integrated as `b41ea57`; **T107 checked (108/115)**. No actual customer credentials or production data were used.

### Foundation retirement, migration cycle and OIDC concurrency

Integrated code `87e0cd4` passed all three jobs in [GitHub CI 44237487171](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44237487171): 202 static/unit/contract/tool/architecture tests, 81 integration/performance passed (one separately enabled OIDC case skipped), two live Keycloak tests, eight P1 browser scenarios and one separate uninitialized-instance browser test. Secret scan found all three selected artifacts clean. Spec 001 health, client, repository, real Project API persistence, ten application and ten process restart regressions, contract/architecture/validation gates are preserved. Migration 0005 drops only the disposable sample table; isolated P1/P2 downgrade/re-upgrade and backup/restore verifies real tenant rows, ACL and RLS, including service identities and grants. No production migration was applied. **T109–T111 checked; 111/115.**

Two earlier CI attempts on `4837408` failed all browser cases by timeout while backend and secrets passed. New code moves sync callback database work off the ASGI event loop, locks verified issuer/subject claims within each transaction and tests concurrent first login against one ASGI process: one identity, one user, two sessions. The new successful CI includes the regression; serial browser fixture execution avoids state interference but does not replace concurrency testing. Root cause hypothesis is consistent with the fix and observed failure, not an independently captured deadlock trace.

Measured Playwright evidence (not whole-test duration): SC-001 switches 192, 178 and 186 ms (<10,000 ms each); SC-004 acceptance 1,139 ms (<180,000 ms); SC-011 bootstrap 1,294 ms (<300,000 ms). The timing tool validates these exact successful report attachments and emits only scalar measurements. Graphify update on code 87e0cd4: 2,457 nodes, 7,207 edges. Automated timing is embedded in tenant-core, invitation-revocation and bootstrap journeys rather than duplicating those flows; T112 remains open for the dedicated timing touchpoint and actual uncoached SC-013 exercise. Full root invocation, final all-scenario evidence and convergence remained pending at this code checkpoint; no main promotion.

### Exact root validation and scenario evidence index (2026-11-18)

Authoritative commit `8ec8272` passed [GitHub CI 44237932898](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44237932898), all three jobs. The validate runner executed the **exact root `pnpm validate`** on Node 26.13.1, with 202 static Python tests, 81 integration/performance tests plus one opt-in skip, 28 SDK/web tests, production build, generated contract freshness, architecture/docs/scope gates, eight P1 browser cases and one bootstrap browser case. The separate backend job repeated the required Python gates and passed two live Keycloak tests. Explicit report and provider-log secret scans were clean and Gitleaks passed. Measured second run: SC-001 189/159/156 ms, SC-004 960 ms, SC-011 1,052 ms. Each is within the original threshold; no threshold was changed.

| Quickstart section | Automated evidence from the accepted code |
|---|---|
| 1–4 Configuration, provider, migrations, startup | CI synthetic configuration, realm discovery, dedicated migration/runtime identities, live OIDC, readiness and browser storage assertions |
| 5, 5A Bootstrap and normal Organization creation | `test_bootstrap.py`, `test_bootstrap_concurrency.py`, `test_bootstrap_storage.py`, `test_multi_org_session.py`, separate bootstrap browser + tenant-core |
| 6, 6A Workspace/Project and Organization lifecycle | `test_workspace_project.py`, `test_project_ownership_boundary.py`, `test_organization_lifecycle.py`, tenant-core browser |
| 7 Dynamic scope | `test_workspace_grant_inheritance.py`, `test_p1_http_access_gate.py`, authorization benchmark |
| 8 Invitation | `test_invitation_lifecycle.py`, `test_cross_tenant_api.py`, invitation-revocation browser |
| 9 Tenant switching | tenant-core browser three switches and cross-tenant direct URLs |
| 10 RLS | all `tests/integration/rls/` regressions and machine-identity table/grant RLS gates |
| 11 Machine identity | `test_service_authorization.py`, `test_service_identity_migration.py` |
| 12 Audit | `test_p1_audit_mutations.py`, `test_audit_actor_snapshot.py`, `test_audit_storage.py`, P2 secret surfaces |
| 13 Last Owner | `test_last_owner.py` concurrent role/status transitions |
| 14 Root validation | `pnpm validate` on exact CI source plus independent backend and Gitleaks |
| 15 Performance | `test_authorization_benchmark.py` enforced p95 <= 50 ms; actual browser measurements above; **SC-013 human exercise explicitly pending** |
| 16 Shared/isolated logical parity | `test_isolated_deployment_parity.py` |
| 17 Retirement | tenant-foundation regressions, isolated P1/P2 migration cycle, README and architecture update |

This index identifies automated scenario evidence, not a claim that a new human has manually run every workflow. SC-013 requires a genuinely unfamiliar, uncoached reviewer on a prepared synthetic instance. At that checkpoint T112/T113/T114/T115 remained open. Main and production remained unchanged.

### Product-owner internal acceptance decision (2026-11-18)

The product owner explicitly approved proceeding past the R002 acceptance gate. The automated scenario index above and green CI 44238336464 for 9010a79 support internal functional acceptance. SC-013 is an explicit exception: the actual unfamiliar-human exercise is deferred until before external acceptance/release and is not reported as passed. Preserve the original five-minute threshold and reviewer protocol. No security, functional, migration, browser, performance or other technical requirement is waived. T112 uses the existing measured journey attachments rather than a duplicate timing-only test; T113 accepts the scenario index with the documented SC-013 exception. T114/T115 and code review remained required before main promotion.

### Final internal validation checkpoint

Exact approved-scope commit `7edb4f4` passed [GitHub CI 44242387123](https://github.com/nguyentrieu210/OpenVietGis/actions/runs/44242387123) in all three jobs: full Node 26 root validation, 202 static Python tests, 81 integration/performance tests (one opt-in skip, live Keycloak verified by independent backend job), 28 SDK/web tests, eight P1 and one bootstrap browser test, generated contracts, scope and architecture checks, measured timing verification, explicit synthetic evidence scan and Gitleaks. Local whitespace check passed and Graphify refreshed to 2,461 nodes / 7,211 edges. T114 checked against internal acceptance scope (114/115); T115 convergence and code review still required. No external acceptance or SC-013 pass claimed.
