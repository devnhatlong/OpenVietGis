# Research: Identity, Organization & Tenancy

**Feature**: 002-identity-organization-tenancy
**Date**: 2026-11-18

This research resolves the implementation choices needed for Spec 002. Product semantics remain
owned by the specification. Technology and protocol choices remain replaceable through ADRs.

## Decision 1 — Human authentication uses OIDC, then a first-party OpenVietGIS session

**Decision**: External identity providers authenticate humans through OIDC Authorization Code flow.
After a successful callback, OpenVietGIS resolves `(issuer, subject)` to an internal User and creates
an opaque first-party application session. The browser receives only an HttpOnly application-session
cookie; provider access/ID tokens are not persisted in browser storage.

Use Authlib 1.9.8 as the initial OIDC client integration behind an `IdentityProvider` adapter. Use
Keycloak 26.8.2 as the reference development/self-host provider, not as a Core dependency.

**Rationale**:
- OpenVietGIS owns membership and authorization while the provider owns authentication.
- A first-party session means membership revocation can take effect on the next request without
  relying on stale role claims inside a long-lived provider token.
- Provider tokens do not need to be exposed to JavaScript or stored in local/session storage.
- Authlib 1.9.8 is the current release and includes recent security fixes; its OIDC integration fits
  FastAPI/Starlette while remaining provider-neutral.
- Keycloak is useful for reproducible self-host/E2E validation but other OIDC issuers remain valid.

**Alternatives considered**:
- SPA stores OIDC bearer tokens and calls the API directly: rejected for Spec 002 because it pushes
  token lifecycle/XSS exposure into the browser and encourages authorization claims to drift into
  provider tokens.
- Local username/password as the primary identity model: rejected because it forks Cloud and
  Enterprise identity architecture.
- Keycloak-specific user/role APIs as Core contracts: rejected because ADR-009 requires provider
  independence.

## Decision 2 — Stable external identity key is issuer + subject

**Decision**: The unique external identity key is `issuer + subject`. Email, display name, and
provider profile data are snapshots only. A single issuer+subject may map to only one internal User.

**Rationale**:
- Email addresses change and are not stable identity keys.
- Multi-issuer deployments require issuer to be part of identity uniqueness.
- Current Authlib security guidance explicitly emphasizes resolving identity with issuer and subject
  rather than subject alone when multiple identity providers/tenants are trusted.

**Alternatives considered**:
- Email as the unique user key: rejected because it can change and can collide across providers.
- Subject alone: rejected because subjects are only unique within an issuer.

## Decision 3 — OIDC state and application session are separate concerns

**Decision**: OIDC login/link state is short-lived and used only to protect the authorization
redirect/callback. Successful authentication creates an application session with:
- random high-entropy session secret;
- only a hash of that secret stored server-side;
- internal User and IdentityLink references;
- issued/expiry/revocation timestamps.

Cookie settings are HttpOnly, SameSite=Lax, and Secure outside explicit local development.

**Rationale**: Login protocol state should not become the long-lived application authorization
session. The application session lets OpenVietGIS check live membership and grants on every
protected request.

## Decision 4 — Cookie-authenticated mutations require CSRF protection

**Decision**: Unsafe session-authenticated requests require a CSRF header derived from the current
opaque application session and an application secret. The web client obtains the current CSRF token
from an authenticated endpoint and sends it on POST/PATCH/PUT/DELETE. Service-credential bearer
requests do not use cookie CSRF.

**Rationale**: SameSite cookies reduce but do not replace explicit CSRF protection for a security
boundary. The token is not an authorization permission; it only proves same-origin request intent.

**Alternatives considered**:
- Rely only on SameSite=Lax: rejected as insufficient defense for a security-critical session.
- Store provider bearer tokens in JavaScript instead of cookies: rejected by Decision 1.

## Decision 5 — Active organization is explicit request context, not User state

**Decision**:
- The web application represents the active organization in its route/navigation state.
- Tenant APIs include `organization_id` explicitly in the resource path.
- The server builds an `AuthorizationContext` per request from the authenticated actor plus explicit
  organization/resource identifiers.
- No `active_organization_id` is stored permanently on User.
- Background work must serialize organization and actor context when it is introduced by later specs.

**Rationale**: A user can belong to many organizations. Hidden sticky tenant state makes cross-tenant
bugs much easier.

**Alternatives considered**:
- Persist active organization on User: rejected because multiple browser tabs/devices would race.
- Infer organization only from a Project/Workspace lookup: rejected because protected data would be
  queried before tenant context is established.

## Decision 6 — Authorization is additive RBAC + resource scope

**Decision**: Implement one `AuthorizationService` with an explicit permission registry.

Human effective permission is the union of:
1. fixed Organization-role permissions;
2. Organization-scoped resource grants;
3. Workspace-scoped resource grants that dynamically apply to Projects currently in that Workspace;
4. direct Project grants.

Service Principal effective permission is the union of its valid resource grants, intersected with
the current Service Credential permission ceiling when one exists.

No general deny-policy/ABAC engine and no long-lived permission cache are introduced in Spec 002.

**Rationale**:
- This exactly matches the post-review specification.
- DB-backed evaluation makes membership/grant/credential revocation effective on the next protected
  request.
- Avoiding deny rules keeps precedence deterministic and explainable.

**Alternatives considered**:
- Hard-code checks such as `role == Admin`: rejected because modules and later commands need stable
  permissions rather than role-name conditionals.
- Cached permission graph without invalidation: rejected because SC-003/SC-009 require immediate
  revocation behavior.
- Full policy language/ABAC: explicitly out of scope.

## Decision 7 — Resource grants use concrete foreign keys plus scope/subject discriminators

**Decision**: The relational ResourceGrant representation uses:
- `organization_id`;
- `subject_kind` plus exactly one of `membership_id` / `service_principal_id`;
- `scope_kind` plus zero or one of `workspace_id` / `project_id` (neither means Organization
  resource scope);
- fixed resource role;
- lifecycle timestamps.

Composite organization-aware foreign keys/checks are used where practical so a grant cannot point
to a subject/resource owned by a different organization.

**Rationale**: A generic `subject_type + subject_id` pair is flexible but loses relational integrity
exactly where tenant safety matters most.

## Decision 8 — PostgreSQL RLS is defense-in-depth with transaction-local tenant context

**Decision**:
- Keep application authorization mandatory.
- Use PostgreSQL 18 row-level security on tenant-sensitive tables required by the spec.
- API traffic uses a non-superuser, non-`BYPASSRLS` runtime role.
- Migration/administrative ownership uses a separate database role.
- Apply `FORCE ROW LEVEL SECURITY` on protected tenant tables where the runtime role might otherwise
  inherit ownership behavior.
- Set request context with transaction-local settings such as
  `openvietgis.organization_id` and `openvietgis.actor_user_id`; never use persistent session-level
  tenant settings on pooled connections.
- RLS policies use simple row ownership comparisons wherever possible.

**Rationale**:
- PostgreSQL documents that table owners normally bypass RLS and superusers/`BYPASSRLS` always do.
  A dedicated runtime role is therefore required for RLS tests to mean anything.
- `SET LOCAL`/transaction-local context naturally clears at transaction end and avoids pooled
  connection tenant leakage.
- PostgreSQL also warns that complex policy subqueries can create race/security problems, so policy
  expressions should remain simple.

**Special access paths**:
- `/me/organizations` uses actor-user context to read the caller's own membership rows before an
  active organization is selected.
- Invitation acceptance carries explicit organization/invitation identifiers plus a secret; it does
  not scan invitations across tenants.
- Bootstrap operates through a global installation-state path before tenant initialization.

## Decision 9 — Cross-tenant non-disclosure

**Decision**: A tenant resource identifier that belongs to another organization is returned to the
caller as not found, not as a detailed forbidden response that confirms existence. Same-tenant
resources for which the actor lacks a permission may return forbidden.

**Rationale**: Tenant isolation includes avoiding unnecessary existence disclosure.

## Decision 10 — Concurrency-sensitive invariants use short locked transactions

**Decision**:
- Last-Owner mutation locks the Organization row (or equivalent ownership coordination row) before
  counting/changing active Owners.
- Invitation acceptance locks/atomically transitions the invitation from pending to accepted and
  creates/activates membership in the same transaction.
- Workspace moves validate Organization ownership and update Project grouping in one transaction.
- Credential revocation and membership suspension/revocation are committed before returning success.
- No user edit/session holds a database transaction open.

**Rationale**: These invariants must survive concurrent requests without violating the Constitution's
short-transaction rule.

## Decision 11 — Invitation secrets are high entropy, one-time, and tenant-addressable

**Decision**: Invitation links carry non-secret tenant/invitation identifiers plus a high-entropy
secret. Only a hash of the secret is stored. The web route keeps the secret out of server access logs
until it is submitted in a request body. Acceptance additionally checks the intended verified email,
User, or issuer+subject target.

**Rationale**:
- RLS can establish the intended organization before looking up the invitation.
- Possession of a link alone cannot let a different authenticated user claim a targeted invitation.

## Decision 12 — Service credentials are high-entropy bearer credentials with a permission ceiling

**Decision**:
- Service credentials use a recognizable OpenVietGIS prefix plus a random high-entropy secret.
- Only a cryptographic hash and safe display prefix/metadata are stored.
- Credential ID/prefix enables direct lookup without scanning all credentials.
- Credential permission scopes are an intersection/ceiling over the Service Principal's currently
  effective grants; they never expand the principal.

Because secrets are generated with high entropy rather than chosen by humans, a fast cryptographic
hash is appropriate; password hashing is not used as a substitute for entropy.

## Decision 13 — Audit events are append-only security records

**Decision**: Security-sensitive mutations append an AuditEvent in the same transaction when
possible. Runtime application code has no update/delete path for audit records. Events record:
- organization context;
- actor type/id and display snapshot;
- action;
- resource reference;
- success/denial outcome when relevant;
- timestamp and safe metadata.

Raw invitation/session/service secrets and provider tokens are never recorded.

## Decision 14 — Self-host bootstrap requires both OIDC identity and one-time installation authority

**Decision**:
- A fresh operator configures an OIDC provider and a one-time bootstrap secret through deployment
  configuration.
- The operator authenticates through the same OIDC path as normal users.
- Bootstrap initialization requires that authenticated User plus the one-time installation secret.
- The transaction creates the first Organization, active Owner membership, audit event, and immutable
  initialized installation state.
- Once initialized, the bootstrap secret/path cannot create another first Owner even if the original
  secret remains configured.

**Rationale**: This preserves a single identity model and prevents "first anonymous caller wins".

## Decision 15 — Keycloak is a reference integration, not production identity architecture

**Decision**: Add a reproducible Keycloak 26.8.2 development/E2E profile with imported test realm and
users. Production/provider configuration remains issuer/client based.

**Rationale**: Keycloak 26.8.2 is a current release with recent security fixes and provides a real OIDC
surface for end-to-end tests without coupling Core semantics to Keycloak.

## Decision 16 — Current framework baseline for Spec 002

**Decision**:
- Python 3.13 (unchanged platform baseline)
- FastAPI 0.163.1 line
- SQLAlchemy 2.1.9 line
- Alembic 1.20.1 line
- Authlib 1.9.8 line
- PostgreSQL 18 + PostGIS 3.7
- React 19.3
- TypeScript 6
- Vite 8.3
- TanStack Query 5.x for server state
- React Router 7.x for organization/invitation routes
- openapi-typescript 7.x for generated contract types

**Rationale**: These are current compatible baselines as of the planning date. Spec 002 introduces
enough server state and navigation that Query/Router now provide real value rather than empty
framework scaffolding.

## Decision 17 — P1 Tenant Core precedes P2 Machine Identity & Bootstrap

**Decision**:
- P1: OIDC/User/IdentityLink/session, Organization membership, active org context, Workspace/Project,
  resource grants, invitations, authorization, RLS, tenant-isolation E2E.
- P2: Service Principal, Service Credential, audit completion, self-host bootstrap.

P1 must be independently runnable/testable before P2 is layered on.

**Rationale**: This keeps the branch reviewable and prevents the 50+ requirements from becoming one
undifferentiated implementation step.

## Decision 18 — Dedicated enterprise infrastructure is not built in Spec 002

**Decision**: The domain/contracts and acceptance fixtures must not assume that many organizations
share one database, but provisioning/operating a dedicated enterprise database/deployment remains an
operations feature.

**Rationale**: This preserves ADR-012 without pulling Spec 013-style deployment work into tenancy
semantics.

## Decision 19 — Spec 001 disposable sample is retired after the real tenant slice replaces it

**Decision**: Once the P1 identity/tenant E2E path is green, remove the FoundationSampleRecord UI/API/
table and its client methods/tests that exist only to prove Spec 001 architecture. Preserve health,
architecture, validation, and infrastructure foundations.

**Rationale**: Spec 001 explicitly defined the sample record as disposable proof data. Keeping it
after real product entities exist would create dead public surface.
