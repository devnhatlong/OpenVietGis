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
