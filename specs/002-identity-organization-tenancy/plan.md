# Implementation Plan: Identity, Organization & Tenancy

**Branch**: `002-identity-organization-tenancy` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-identity-organization-tenancy/spec.md`

## Summary

Spec 002 replaces the disposable foundation vertical slice with the first real OpenVietGIS product
domain: human identity, Organization membership, Workspace/Project hierarchy, additive scoped
authorization, invitations, tenant isolation, machine identity, audit actors, and one-time self-host
bootstrap.

The implementation is deliberately split into two independently verifiable milestones:

```text
P1 Human Tenant Core
OIDC -> User/IdentityLink -> first-party session
     -> Organization create/membership / active org context
     -> Workspace / Project
     -> ResourceGrant / Invitation
     -> AuthorizationService
     -> append-only AuditEvent + PostgreSQL RLS defense-in-depth

P2 Machine Identity & Bootstrap
ServicePrincipal -> ServiceCredential -> same AuthorizationService
Audit read/actor-after-revoke completion
OIDC-authenticated operator + one-time installation authority -> first Org/Owner
```

P1 must be demonstrable before P2 is required. Cross-Organization Project transfer, public sharing,
custom role builders, GIS/Layer/Map features, and production dedicated-enterprise provisioning are
not implemented in this feature.

## Technical Context

**Language/Version**:
- Python 3.13
- Node.js 26
- TypeScript 6
- React 19.3

**Primary Dependencies**:
- FastAPI 0.163.1 line
- SQLAlchemy 2.1.9 line
- Alembic 1.20.1 line
- Authlib 1.9.8 line for OIDC client integration
- PostgreSQL 18 + PostGIS 3.7
- React Router 7.18.5 line
- TanStack Query 5.107.1 line
- openapi-typescript 7.13.0 line for generated client contract types
- existing pnpm/Vite/Playwright/pytest/Ruff/mypy foundation

**Storage**:
- PostgreSQL/PostGIS remains source of truth
- schemas: `identity`, `org`, `workspace`, `audit`, `platform`
- no Redis/cache required in Spec 002
- no browser persistence of provider tokens

**Testing**:
- pytest unit/domain tests
- real PostgreSQL integration tests using the non-BYPASSRLS runtime role
- OpenAPI/permission-registry contract tests
- Keycloak-backed OIDC integration/E2E
- Vitest for client/UI behavior
- Playwright for real browser login/bootstrap/invite/tenant flows
- existing architecture, secret, scope, migration, and production-build gates

**Target Platform**:
- same logical product on Cloud, self-hosted, and Enterprise
- Windows/Linux development with Docker
- Linux-compatible production API runtime
- evergreen desktop browsers for the minimal admin UI

**Project Type**: monorepo web platform: React SPA + FastAPI modular-monolith backend + PostgreSQL
tenant/security model + shared typed client contracts

**Performance Goals**:
- satisfy user-facing SC-001/004/011/013 time limits
- permission resolution overhead p95 <= 50 ms in a real-database integration benchmark with at least
  50 relevant/irrelevant scoped grants and dynamic Workspace inheritance
- revocation becomes effective on the next protected request; no stale permission-cache window
- tenant context setup must not require a second database round trip after actor/membership resolution
  purely for framework bookkeeping

**Constraints**:
- Organization is the tenant ownership boundary
- active Organization is explicit request/navigation context and is never stored as sticky User state
- server authorization is mandatory; UI visibility is never authorization
- RLS is defense-in-depth and must be tested using a non-superuser/non-BYPASSRLS runtime role
- tenant context is transaction-local on pooled DB connections
- provider access/ID tokens are not stored in browser local/session storage
- cookie-authenticated unsafe requests require CSRF protection
- identity uniqueness is issuer + subject; email is descriptive/verified targeting data only
- permissions are additive; no general deny engine/ABAC and no long-lived permission cache
- Workspace inheritance is dynamic and never copied to Projects
- ServiceCredential scope can only restrict ServicePrincipal grants
- owner/invitation concurrency invariants use short transactions
- no ordinary operation changes Project.organization_id
- no public/anonymous sharing or custom role builder
- no GIS/Layer/Map/Editing/Processing/Field/vertical-module implementation
- actual dedicated Enterprise database provisioning is deferred

**Scale/Scope**:
- 7 user journeys, 54 functional requirements, 14 success criteria
- P1 correctness/security is the primary milestone
- authorization benchmark fixture covers at least 50 grants per actor/resource scenario
- list APIs must be designed so pagination can be added/used without changing tenant ownership
  semantics; Spec 002 does not require a high-volume portal UI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Constitution rule | Pre-design assessment | Post-design assessment |
| --- | --- | --- |
| I. Platform-First, Module-Isolated | PASS — identity/tenant/security are reusable platform capabilities, not vertical-domain behavior. | PASS — no vertical module dependency or GIS-domain concept is introduced. |
| II. Open Data and Interoperability | PASS — Organization/Project metadata remains accessible through documented product contracts. | PASS — versioned OpenAPI/typed client contracts avoid provider lock-in; identity-provider data is adapter-owned. |
| III. Tenant Isolation Is a Security Boundary | PASS — central requirement of Spec 002. | PASS — explicit org context + AuthorizationService + non-BYPASSRLS runtime role + RLS tests provide layered enforcement. |
| IV. Spatial Correctness and Explicit CRS | PASS — no spatial data/CRS behavior is implemented. | PASS — spatial concerns remain deferred. |
| V. Changes Are Versioned and Auditable | PASS — sensitive membership/grant/invite/service/bootstrap changes require audit. | PASS — AuditEvent is append-only; sensitive mutations append in the same transaction where practical. No spatial ChangeSet behavior is invented. |
| VI. Capability-Driven Architecture | PASS — permission codes are stable capabilities; role names are bundles. | PASS — UI/API use effective permission codes rather than role-name conditionals. |
| VII. Web-Native, Engine-Agnostic | PASS — OIDC provider is behind an adapter and Cloud/Self-host share semantics. | PASS — Keycloak is test/reference only; identity-provider and deployment choices remain replaceable. |
| VIII. Workflow Value Before Feature Count | PASS — scope is identity/tenancy foundation needed by all later workflows. | PASS — public sharing, custom roles, cross-org Project transfer, and GIS capability remain explicitly deferred. |
| Architectural boundaries | PASS — Project directly belongs to Organization; Workspace grouping optional. | PASS — composite tenant constraints and explicit resource paths preserve Organization ownership independent of Workspace. |
| Development/quality gates | PASS — security-sensitive feature requires real DB/browser/integration coverage. | PASS — plan includes real RLS runtime-role tests, OIDC E2E, concurrency tests, secret scanning, and convergence. |

**Gate result**: PASS before and after design. No Constitution violation requires Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-identity-organization-tenancy/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── auth-session-api.yaml
│   ├── tenant-core-api.yaml
│   ├── service-admin-api.yaml
│   └── permission-registry.md
├── checklists/
│   └── requirements.md
└── tasks.md                    # generated later by /speckit-tasks
```

Architecture decisions added by this plan:

```text
docs/adr/
├── ADR-013-oidc-application-session.md
└── ADR-014-explicit-tenant-context-rls.md
```

### Source Code (repository root)

```text
apps/
├── api/
│   ├── openvietgis_api/
│   │   ├── domains/
│   │   │   ├── identity/
│   │   │   │   ├── domain.py
│   │   │   │   ├── service.py
│   │   │   │   └── ports.py
│   │   │   ├── tenancy/
│   │   │   │   ├── domain.py
│   │   │   │   ├── service.py
│   │   │   │   └── ports.py
│   │   │   ├── authorization/
│   │   │   │   ├── context.py
│   │   │   │   ├── permissions.py
│   │   │   │   ├── roles.py
│   │   │   │   ├── service.py
│   │   │   │   └── ports.py
│   │   │   ├── audit/
│   │   │   │   ├── domain.py
│   │   │   │   ├── service.py
│   │   │   │   └── ports.py
│   │   │   └── bootstrap/
│   │   │       ├── domain.py
│   │   │       └── service.py
│   │   ├── adapters/
│   │   │   ├── http/
│   │   │   │   ├── auth.py
│   │   │   │   ├── me.py
│   │   │   │   ├── organizations.py
│   │   │   │   ├── workspaces.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── grants.py
│   │   │   │   ├── invitations.py
│   │   │   │   ├── service_principals.py
│   │   │   │   ├── audit.py
│   │   │   │   └── bootstrap.py
│   │   │   ├── oidc/
│   │   │   │   └── provider.py
│   │   │   └── persistence/
│   │   │       ├── db.py
│   │   │       ├── rls.py
│   │   │       ├── identity_repository.py
│   │   │       ├── tenancy_repository.py
│   │   │       ├── authorization_repository.py
│   │   │       ├── audit_repository.py
│   │   │       └── platform_repository.py
│   │   ├── security/
│   │   │   ├── sessions.py
│   │   │   ├── csrf.py
│   │   │   └── secrets.py
│   │   ├── config.py
│   │   └── main.py
│   ├── migrations/
│   │   └── versions/
│   │       ├── 0002_identity_tenant_core.py
│   │       ├── 0003_tenant_rls.py
│   │       ├── 0004_machine_identity.py
│   │       └── 0005_retire_foundation_sample.py
│   └── tests/
│       ├── contract/
│       ├── unit/
│       │   ├── identity/
│       │   ├── tenancy/
│       │   └── authorization/
│       └── integration/
│           ├── identity/
│           ├── tenancy/
│           ├── rls/
│           └── service_identity/
│
└── web/
    └── src/
        ├── app/
        │   ├── App.tsx
        │   ├── router.tsx
        │   └── query.ts
        └── features/
            ├── auth/
            ├── organizations/
            ├── workspaces/
            ├── projects/
            ├── invitations/
            └── membership/

packages/
└── client-sdk/
    ├── src/
    │   ├── generated/
    │   ├── auth.ts
    │   ├── organizations.ts
    │   ├── workspaces.ts
    │   ├── projects.ts
    │   ├── invitations.ts
    │   └── service-principals.ts
    └── tests/

infra/
└── dev/
    ├── compose.yaml
    ├── compose.identity.yaml
    └── keycloak/
        └── realm-openvietgis.json

tests/
└── e2e/
    ├── tenant-core.spec.ts
    ├── invitation-revocation.spec.ts
    └── bootstrap-service-identity.spec.ts
```

**Structure Decision**: Keep the ADR-002 modular monolith. Spec 002 introduces explicit backend
domain packages because identity, tenancy, authorization, and audit now have durable boundaries.
External OIDC, HTTP, and persistence remain adapters. No separate auth microservice is introduced.
The old Spec 001 foundation sample paths are removed only after the real P1 tenant slice passes.

## Phase 0 — Research Decisions

Research is recorded in [research.md](research.md). All planning unknowns are resolved.

### Authentication/session

- External OIDC authentication through provider-neutral adapter.
- Authlib 1.9.8 initial implementation.
- First-party opaque OpenVietGIS session after callback.
- HttpOnly/SameSite cookie; provider tokens do not enter browser application storage.
- explicit CSRF token required for unsafe cookie-authenticated requests.
- Keycloak 26.8.2 is real dev/E2E reference provider only.

### Identity

- External identity key is `issuer + subject`, unique across IdentityLink.
- Email is verified targeting/profile data, never permanent identity key.
- Existing issuer+subject linked to another User is a conflict, never an automatic account merge.

### Tenancy/authorization

- explicit `organization_id` in tenant API paths.
- active Organization exists in route/request context, not User persistence.
- one AuthorizationService/PermissionRegistry for human/service contexts plus a serializable
  RequestedActorContext envelope for future background execution; Spec 002 adds no worker runtime.
- additive permission union; no deny policy.
- Organization-scoped grants apply resource-role permissions tenant-wide without granting member admin.
- Workspace grants dynamically inherit to currently grouped Projects.
- direct Project grants are additive.
- no permission cache in Spec 002.

### Database isolation

- separate migration-owner and runtime DB identities.
- runtime identity is not superuser and has no BYPASSRLS.
- selective RLS + FORCE RLS on tenant-sensitive tables.
- transaction-local tenant/actor context only.
- cross-tenant lookup returns non-disclosing not-found behavior.

### Security-sensitive mutation

- Owner invariant serialized with short transaction lock.
- Invitation accept is atomic + recipient-bound + one-time.
- session/invitation/service secrets are high entropy and stored as hashes only.
- audit is append-only and excludes raw secrets.

### Scope sequencing

- P1 Human Tenant Core first, including minimal append-only AuditEvent persistence and Audit RLS
  required by P1 security-sensitive mutations.
- P2 Machine Identity/Audit-read/Bootstrap second.
- actual dedicated-enterprise infrastructure remains outside Spec 002.
- foundation sample retired after P1 real product E2E succeeds.

## Phase 1 — Design

### 1. Human authentication pipeline

```text
Browser
  -> /auth/login/{provider}
  -> OIDC provider
  -> /auth/callback/{provider}
  -> validate issuer/subject/nonce/state
  -> resolve/create User + IdentityLink
  -> create opaque WebSession
  -> HttpOnly ovg_session cookie
  -> /me + /me/organizations
```

The session proves human identity only. Every tenant request subsequently resolves live Membership
and effective permissions.

### 2. Protected request pipeline

```text
session cookie OR service bearer
        |
        v
Actor authentication
        |
explicit organization_id from route
        |
        v
Membership / ServicePrincipal active check
        |
        v
AuthorizationContext
        |
        +--> AuthorizationService(permission, resource)
        |
        +--> SET LOCAL tenant/actor DB context
        |
        v
Repository operation under RLS
        |
        v
Audit sensitive mutation/decision
```

No protected repository query should discover a tenant before AuthorizationContext exists, except
the narrowly-defined self-membership/invitation/bootstrap paths in research.md.

### 3. Database/RLS design

[data-model.md](data-model.md) defines schemas/entities/constraints.

Migration sequence:
1. `0002_identity_tenant_core`: identity/users/sessions, Organization/Membership,
   Workspace/Project, ResourceGrant, Invitation, append-only AuditEvent, foundational
   InstallationState storage, constraints/indexes.
2. `0003_tenant_rls`: runtime role grants, RLS/FORCE RLS for all P1 tenant tables including
   `audit.audit_events`, and transaction-context helpers.
3. `0004_machine_identity`: ServicePrincipal/Credential and their tenant/security policies;
   AuditEvent and InstallationState storage already exist from P1.
4. `0005_retire_foundation_sample`: remove disposable Spec 001 sample only after new E2E gates pass.

Application runtime and migration database URLs are separate configuration values.

### 4. Organization creation and lifecycle

Normal authenticated Organization creation is distinct from one-time self-host bootstrap and is
available only after installation state is initialized:

```text
initialized installation + authenticated User
  -> POST /organizations
  -> create Organization(active)
  -> create active Owner membership for same User
  -> append AuditEvent
  -> commit atomically
```

Owner-controlled Organization lifecycle supports `active -> suspended -> active` and recoverable
`active/suspended -> deleted` transitions. Admin cannot perform Owner-only Organization
suspend/delete transitions. Suspended/deleted Organizations reject normal tenant mutations while
remaining inspectable only through explicitly permitted recovery/administration paths.

### 5. Permission evaluation

[contracts/permission-registry.md](contracts/permission-registry.md) is the stable action contract.

AuthorizationService inputs:

```text
actor
organization_id
action
optional workspace_id
optional project_id
```

Human:
```text
active membership role bundle
UNION active Organization resource grants
UNION active Workspace grants applicable now
UNION active direct Project grants
```

Service:
```text
active ServicePrincipal grants
INTERSECT optional credential permission ceiling
```

Owner invariants are domain rules and cannot be bypassed merely because a permission code is present.

### 6. Requested actor context envelope

`RequestedActorContext` is a serializable value object containing actor type/reference,
organization_id, and optional workspace/project scope. It round-trips to/from a plain payload and
can be restored into AuthorizationContext by a future job/worker implementation. Spec 002 does not
add a queue, worker, retry system, or background executor.

### 7. Invitation flow

Invitation delivery itself is not implemented as an email-service integration in Spec 002; the
system creates an invitation and returns a one-time link/secret that a later notification service may
deliver.

Browser route keeps invitation secret out of server URL logs (client fragment/local handoff) and
submits organization_id + invitation_id + secret in a protected request body after login.

Acceptance locks invitation row, verifies target identity, activates membership/optional grant,
marks accepted, writes audit, and commits atomically.

### 8. Minimal web experience

Use React Router because Organization and invitation context are URL/navigation concerns. Use
TanStack Query for server state.

Minimum screens:
- login/provider choice;
- current User + Organization switcher;
- first-time bootstrap screen when applicable;
- Organization home/membership summary;
- Workspace list/create;
- Project list/create/move/archive;
- invitation create/accept/revoke;
- membership suspend/revoke.

ServicePrincipal and audit acceptance may be API-driven; FR-042 does not require full UI for them.

### 9. Contract/client strategy

OpenAPI surfaces:
- [auth-session-api.yaml](contracts/auth-session-api.yaml)
- [tenant-core-api.yaml](contracts/tenant-core-api.yaml)
- [service-admin-api.yaml](contracts/service-admin-api.yaml)

Generate TypeScript contract types with openapi-typescript. Keep request transport and feature methods
in `packages/client-sdk` so React UI does not scatter raw endpoint/response assumptions.

Contract freshness becomes part of root validation.

### 10. P1 verification

P1 cannot be considered complete until:
- real Keycloak OIDC browser login works;
- an authenticated User can create additional Organizations and atomically become Owner;
- one User can belong to multiple Organizations;
- active org switch is explicit;
- Workspace/Project hierarchy and dynamic grant inheritance work;
- invite recipient binding/one-time acceptance works;
- membership revoke blocks next protected request;
- cross-tenant API and direct repository/RLS attempts fail;
- Last Owner and Owner-only Organization lifecycle invariants pass;
- append-only AuditEvent storage exists before P1 sensitive mutations are accepted;
- AuditEvent is protected by tenant RLS and tested with the runtime DB role;
- RequestedActorContext serialization/restoration preserves actor + Organization/resource scope;
- minimal P1 Playwright flow passes.

### 11. P2 verification

P2 adds:
- ServicePrincipal and ServiceCredential;
- permission ceiling;
- immediate credential revocation;
- audit read/query API and actor-after-revocation completion on top of P1 AuditEvent storage;
- OIDC + one-time-authority bootstrap;
- bootstrap reuse denial;
- logical isolated-deployment fixture parity.

### 12. Foundation retirement

After P1 real product E2E is green:
- remove FoundationSampleRecord route/domain/repository/client/UI/test surface;
- migrate/drop `foundation.sample_records`;
- keep Spec 001 liveness/readiness, architecture checks, reset safety, CI, secret scanning, and
  baseline validation behavior.

## Verification Strategy

Implementation is accepted only when all are true:

1. **Static/contract**: lint/typecheck/OpenAPI parsing/generated-type freshness pass.
2. **OIDC**: real reference-provider login/link flow validates state/nonce and resolves issuer+subject.
3. **Session/CSRF**: session secret not stored raw; unsafe cookie mutations reject missing/invalid CSRF.
4. **Tenant context**: User has no persisted active Org; protected APIs require explicit org path/context.
5. **RLS**: tests run as non-superuser/non-BYPASSRLS runtime role and prove A cannot see/write B.
6. **Pool safety**: A/B transactions reuse pooled connections without tenant-context leakage.
7. **Authorization**: role/grant union and Workspace inheritance match permission registry.
8. **Revocation**: Membership/Grant/Credential revocation affects next protected request.
9. **Invitation**: wrong recipient, expired/revoked/reused token, and concurrent acceptance fail safely.
10. **Owner invariant**: concurrent Owner mutations cannot leave zero active Owners.
11. **Project boundary**: Workspace move never changes Organization; cross-org ownership change rejected.
12. **Machine identity**: ServiceCredential ceiling only restricts and cross-tenant access fails.
13. **Audit**: actor snapshots remain readable after revoke; no secret material is logged/audited.
14. **Bootstrap**: requires both authenticated human and one-time installation authority; reuse rejected.
15. **Browser**: Playwright P1 and bootstrap/invite flows pass with Keycloak reference provider.
16. **Unfamiliar-user timing**: SC-013 is measured with a reviewer who has no prior product orientation.
17. **Performance**: authorization p95 target in quickstart benchmark is met without stale permission cache.
18. **Scope**: zero public sharing/custom role/GIS/Map/Processing/Field/vertical-domain implementation.
19. **Legacy cleanup**: disposable FoundationSampleRecord is removed without breaking Spec 001 platform gates.

## Complexity Tracking

No Constitution violations.