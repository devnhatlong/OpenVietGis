# Tasks: Identity, Organization & Tenancy

**Input**: Design documents from `/specs/002-identity-organization-tenancy/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. Spec 002 is a security-boundary feature; contract, unit, real PostgreSQL/RLS integration, OIDC, concurrency, and browser E2E tests are part of acceptance.

**Organization**: Tasks are grouped by user story. Shared identity/authorization/RLS infrastructure lives in Setup/Foundational so each story can be exercised with controlled fixtures without duplicating security primitives.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after its phase prerequisites are satisfied
- **[Story]**: Maps directly to the user story in spec.md
- Every task includes an exact repository path
- Field constraints cite the canonical `data-model.md` entity/field definitions

---

## Phase 1: Setup

**Purpose**: Add the dependencies, contract tooling, reference identity-provider fixture, and configuration surface required by Spec 002 without implementing user journeys.

- [X] T001 Add Authlib, cryptographic/session support dependencies, OpenAPI contract validation dependencies, and exact compatible versions from research.md to `apps/api/pyproject.toml`
- [X] T002 Add React Router, TanStack Query, and openapi-typescript dependencies/scripts to `apps/web/package.json`, `packages/client-sdk/package.json`, and root `package.json`
- [X] T003 [P] Add identity/tenant configuration keys for OIDC providers, application session/CSRF secret, one-time bootstrap authority, migration-owner DB URL, and runtime DB URL to `apps/api/openvietgis_api/config.py` and synthetic placeholders to `.env.example`
- [X] T004 [P] Add Keycloak 26.8.2 reference service profile to `infra/dev/compose.identity.yaml` and synthetic realm/users/client import to `infra/dev/keycloak/realm-openvietgis.json`
- [X] T005 [P] Add generated-contract output directory and generation entrypoints for all three OpenAPI surfaces to `packages/client-sdk/src/generated/` and root/package scripts in `package.json`
- [X] T006 [P] Add OpenAPI validation and generated-client freshness checks to `tools/check_contracts.py` and wire them into root `validate` in `package.json`
- [X] T007 [P] Add Spec 002 runtime-scope guard rules excluding GIS/Layer/Map/Editing/Processing/Field/public-share/custom-role implementation to `tools/check_scope.py` and its tests in `tools/tests/test_scope.py`
- [X] T008 Add Keycloak-aware local startup/validation documentation without production secrets to `README.md` and keep the runnable acceptance flow canonical in `specs/002-identity-organization-tenancy/quickstart.md`

**Checkpoint**: Setup tooling and reference OIDC fixture exist; no tenant behavior is implemented yet.

---

## Phase 2: Foundational Security & Persistence

**Purpose**: Blocking primitives shared by all seven user stories.

**CRITICAL**: No user-story implementation starts until this phase is green.

### Contract and architecture guards

- [X] T009 [P] Add contract tests that parse/validate `specs/002-identity-organization-tenancy/contracts/auth-session-api.yaml`, `tenant-core-api.yaml`, `service-admin-api.yaml`, and `permission-registry.md` in `apps/api/tests/contract/test_identity_tenancy_contracts.py`
- [X] T010 [P] Extend architecture scanner rules so `domains/*` cannot import HTTP/OIDC/persistence adapters and vertical modules cannot be imported by tenancy Core in `tools/check_architecture.py` with fixtures/tests in `tests/architecture/test_architecture.py`
- [X] T011 [P] Add permission-registry drift test ensuring role bundles use stable permission codes and no `project.transfer`/deny-policy/custom-role code enters Spec 002 in `apps/api/tests/contract/test_permission_registry.py`

### Persistence model

- [X] T012 Implement User and IdentityLink persistence/domain mappings in `apps/api/openvietgis_api/domains/identity/domain.py` and migration `apps/api/migrations/versions/0002_identity_tenant_core.py`, citing [data-model.md#user] `User.id`, `User.display_name`, `User.email_snapshot`, `User.status`, `User.created_at`, `User.updated_at` and [data-model.md#identitylink] `IdentityLink.id`, `IdentityLink.user_id`, `IdentityLink.issuer`, `IdentityLink.subject`, `IdentityLink.email_snapshot`, `IdentityLink.email_verified`, `IdentityLink.display_name_snapshot`, `IdentityLink.created_at`, `IdentityLink.last_login_at`
- [X] T013 Implement WebSession persistence/domain mapping in `apps/api/openvietgis_api/domains/identity/domain.py` and migration `apps/api/migrations/versions/0002_identity_tenant_core.py`, citing [data-model.md#websession] `WebSession.id`, `WebSession.user_id`, `WebSession.identity_link_id`, `WebSession.secret_hash`, `WebSession.issued_at`, `WebSession.expires_at`, `WebSession.last_seen_at`, `WebSession.revoked_at`
- [X] T014 Implement Organization and OrganizationMembership persistence/domain mappings in `apps/api/openvietgis_api/domains/tenancy/domain.py` and migration `apps/api/migrations/versions/0002_identity_tenant_core.py`, citing [data-model.md#organization] `Organization.id`, `Organization.name`, `Organization.slug`, `Organization.status`, `Organization.created_by_actor_type`, `Organization.created_by_actor_id`, `Organization.created_at`, `Organization.updated_at`, `Organization.deleted_at` and [data-model.md#organizationmembership] `OrganizationMembership.id`, `OrganizationMembership.organization_id`, `OrganizationMembership.user_id`, `OrganizationMembership.role`, `OrganizationMembership.status`, `OrganizationMembership.created_at`, `OrganizationMembership.activated_at`, `OrganizationMembership.suspended_at`, `OrganizationMembership.revoked_at`
- [X] T015 Implement Workspace and Project persistence/domain mappings plus composite same-Organization foreign keys in `apps/api/openvietgis_api/domains/tenancy/domain.py` and migration `apps/api/migrations/versions/0002_identity_tenant_core.py`, citing [data-model.md#workspace] `Workspace.id`, `Workspace.organization_id`, `Workspace.name`, `Workspace.slug`, `Workspace.status`, `Workspace.created_by_actor_type`, `Workspace.created_by_actor_id`, `Workspace.created_at`, `Workspace.updated_at`, `Workspace.archived_at`, `Workspace.deleted_at` and [data-model.md#project] `Project.id`, `Project.organization_id`, `Project.workspace_id`, `Project.name`, `Project.slug`, `Project.status`, `Project.created_by_actor_type`, `Project.created_by_actor_id`, `Project.created_at`, `Project.updated_at`, `Project.archived_at`, `Project.deleted_at`
- [X] T016 Implement ResourceGrant persistence/domain mapping with subject/scope check constraints and organization-aware composite FKs in `apps/api/openvietgis_api/domains/authorization/domain.py` and migration `apps/api/migrations/versions/0002_identity_tenant_core.py`, citing [data-model.md#resourcegrant] `ResourceGrant.id`, `ResourceGrant.organization_id`, `ResourceGrant.subject_kind`, `ResourceGrant.membership_id`, `ResourceGrant.service_principal_id`, `ResourceGrant.scope_kind`, `ResourceGrant.workspace_id`, `ResourceGrant.project_id`, `ResourceGrant.role`, `ResourceGrant.created_at`, `ResourceGrant.created_by_actor_type`, `ResourceGrant.created_by_actor_id`, `ResourceGrant.revoked_at`
- [X] T017 Implement Invitation persistence/domain mapping with target/scope constraints and token digest fields in `apps/api/openvietgis_api/domains/tenancy/domain.py` and migration `apps/api/migrations/versions/0002_identity_tenant_core.py`, citing [data-model.md#invitation] `Invitation.id`, `Invitation.organization_id`, `Invitation.status`, `Invitation.target_kind`, `Invitation.target_email_normalized`, `Invitation.target_user_id`, `Invitation.target_issuer`, `Invitation.target_subject`, `Invitation.organization_role`, `Invitation.resource_scope_kind`, `Invitation.resource_workspace_id`, `Invitation.resource_project_id`, `Invitation.resource_role`, `Invitation.token_hash`, `Invitation.token_prefix`, `Invitation.expires_at`, `Invitation.created_at`, `Invitation.created_by_actor_type`, `Invitation.created_by_actor_id`, `Invitation.accepted_at`, `Invitation.accepted_by_user_id`, `Invitation.revoked_at`
- [X] T018 Implement foundational append-only AuditEvent and InstallationState domain/persistence in `apps/api/openvietgis_api/domains/audit/domain.py`, `apps/api/openvietgis_api/domains/audit/ports.py`, `apps/api/openvietgis_api/domains/bootstrap/domain.py`, `apps/api/openvietgis_api/adapters/persistence/audit_repository.py`, `apps/api/openvietgis_api/adapters/persistence/platform_repository.py`, and `apps/api/migrations/versions/0002_identity_tenant_core.py`, then extend zero-to-head migration/immutability/singleton tests in `apps/api/tests/integration/tenancy/test_identity_tenant_migrations.py`, citing [data-model.md#auditevent] `AuditEvent.id`, `AuditEvent.organization_id`, `AuditEvent.actor_type`, `AuditEvent.actor_id`, `AuditEvent.actor_display_snapshot`, `AuditEvent.action`, `AuditEvent.resource_type`, `AuditEvent.resource_id`, `AuditEvent.outcome`, `AuditEvent.metadata`, `AuditEvent.created_at` and [data-model.md#installationstate] `InstallationState.singleton_key`, `InstallationState.initialized_at`, `InstallationState.initial_organization_id`, `InstallationState.initialized_by_user_id`, `InstallationState.updated_at`

### Shared security primitives

- [X] T019 [P] Implement stable permission codes and fixed Organization/resource role bundles exactly from `contracts/permission-registry.md` in `apps/api/openvietgis_api/domains/authorization/permissions.py` and `roles.py`
- [X] T020 [P] Implement high-entropy secret generation, SHA-256 digest/constant-time verification, safe prefixes, and no-raw-secret logging helpers in `apps/api/openvietgis_api/security/secrets.py` with unit tests in `apps/api/tests/unit/identity/test_secrets.py`
- [X] T021 [P] Implement opaque WebSession cookie encode/lookup/revoke behavior in `apps/api/openvietgis_api/security/sessions.py` with unit tests in `apps/api/tests/unit/identity/test_sessions.py`
- [X] T022 [P] Implement session-bound CSRF token generation/verification for unsafe cookie requests in `apps/api/openvietgis_api/security/csrf.py` with unit tests in `apps/api/tests/unit/identity/test_csrf.py`
- [X] T023 Implement `Actor`, `AuthorizationContext`, and serializable `RequestedActorContext` primitives plus round-trip tests in `apps/api/openvietgis_api/domains/authorization/context.py` and `apps/api/tests/unit/authorization/test_context.py`, citing [data-model.md#requestedactorcontext] `RequestedActorContext.actor_type`, `RequestedActorContext.actor_id`, `RequestedActorContext.organization_id`, `RequestedActorContext.workspace_id`, `RequestedActorContext.project_id`
- [X] T024 Implement additive `AuthorizationService` evaluation skeleton and permission-denied/not-found result semantics in `apps/api/openvietgis_api/domains/authorization/service.py` with unit tests in `apps/api/tests/unit/authorization/test_authorization_service.py`
- [X] T025 Implement transaction-local tenant/actor database context helpers in `apps/api/openvietgis_api/adapters/persistence/rls.py` with pool-leak regression tests in `apps/api/tests/integration/rls/test_transaction_context.py`
- [X] T026 Create separate migration-owner/runtime PostgreSQL roles, grants, RLS policies, FORCE RLS, and protected-table policies including `audit.audit_events` in `apps/api/migrations/versions/0003_tenant_rls.py`
- [X] T027 Prove the configured API runtime role is neither superuser nor BYPASSRLS and cannot bypass any P1 protected rows including `audit.audit_events` in `apps/api/tests/integration/rls/test_runtime_role.py`
- [X] T028 Implement shared HTTP actor/session/service-auth resolution and CSRF enforcement dependencies in `apps/api/openvietgis_api/adapters/http/security.py`
- [X] T029 Wire generated OpenAPI types plus common session/service request transport into `packages/client-sdk/src/generated/`, `packages/client-sdk/src/http.ts`, and `packages/client-sdk/src/index.ts`
- [X] T030 Add common Testcontainers/fixture helpers for synthetic Users, Organizations, pre-initialized InstallationState, runtime-role DB sessions, and authenticated test actors in `apps/api/tests/fixtures/identity_tenancy.py` and register them in `apps/api/tests/conftest.py`

**Checkpoint**: Persistence, permission vocabulary, session/CSRF, actor/context-envelope primitives, foundational append-only audit storage, runtime DB role, and P1 RLS mechanics are green. Story work can start.

---

## Phase 3: User Story 1 — Work Across Multiple Organizations Safely (Priority: P1) — P1 Tenant Core

**Goal**: A human authenticates through OIDC, resolves to one internal User, holds memberships in multiple Organizations, and switches explicit Organization context without tenant leakage.

**Independent Test**: One synthetic User linked to one OIDC identity belongs to three Organizations with different roles. Login once, list memberships, switch URL/context among all three, and verify effective permissions/resources change without cross-tenant disclosure.

### Tests first

- [X] T031 [P] [US1] Add OIDC state/nonce/issuer+subject/link-conflict plus explicit link/unlink AuditEvent integration tests against the reference provider adapter in `apps/api/tests/integration/identity/test_oidc_login.py`
- [X] T032 [P] [US1] Add multi-Organization session/context, pre-initialization normal-Organization-create rejection, normal authenticated Organization creation + atomic creator-Owner membership/audit after initialization, and role-switch API integration tests for `/organizations`, `/me`, and `/me/organizations` in `apps/api/tests/integration/identity/test_multi_org_session.py`
- [X] T033 [P] [US1] Add client contract tests for auth/session/current-user/organization discovery in `packages/client-sdk/tests/auth-session.test.ts`
- [X] T034 [P] [US1] Add Playwright login + normal additional-Organization creation + three-Organization switch acceptance covering SC-001 in `tests/e2e/tenant-core.spec.ts`

### Implementation

- [X] T035 [P] [US1] Implement provider-neutral OIDC adapter and issuer/provider registry in `apps/api/openvietgis_api/adapters/oidc/provider.py`
- [X] T036 [US1] Implement User/IdentityLink resolution, explicit link/unlink with foundational AuditEvent records, link conflict handling, and application-session creation in `apps/api/openvietgis_api/domains/identity/service.py`
- [X] T037 [US1] Implement `/auth/providers`, login, callback, CSRF, logout, `/me`, `/me/organizations`, identity-link HTTP contract, and normal authenticated `POST /organizations` in `apps/api/openvietgis_api/adapters/http/auth.py`, `me.py`, and `organizations.py`
- [X] T038 [US1] Implement self-membership discovery repository path that resolves only the authenticated User's active memberships before active Organization selection in `apps/api/openvietgis_api/adapters/persistence/tenancy_repository.py`
- [X] T039 [US1] Implement Organization membership lookup/current-role paths plus initialization guard and atomic normal Organization creation with creator Owner membership and foundational AuditEvent in `apps/api/openvietgis_api/domains/tenancy/service.py` and `apps/api/openvietgis_api/adapters/persistence/tenancy_repository.py`
- [X] T040 [P] [US1] Add auth/current-user/Organization discovery and normal Organization-create client methods in `packages/client-sdk/src/auth.ts` and `organizations.ts`
- [X] T041 [P] [US1] Add React Router and TanStack Query application composition in `apps/web/src/app/router.tsx`, `apps/web/src/app/query.ts`, and `apps/web/src/app/App.tsx`
- [X] T042 [US1] Implement provider login, current-user shell, normal Organization-create flow, Organization switcher, and explicit organization-route context in `apps/web/src/features/auth/` and `apps/web/src/features/organizations/`
- [X] T043 [US1] Add session/logout/identity-link minimal UI and ensure no provider token is persisted in browser storage in `apps/web/src/features/auth/IdentityPage.tsx`

**Checkpoint**: US1 works with a real OIDC provider and one login across multiple Organizations.

---

## Phase 4: User Story 2 — Organize Workspaces and Projects (Priority: P1) — P1 Tenant Core

**Goal**: Authorized actors create/move/archive Workspace/Project resources while Project ownership remains directly with one Organization.

**Independent Test**: With a controlled authorized actor fixture, create two Workspaces and one Project, move/un-group Project, archive/restore, reject Workspace deletion with active Projects, and reject every ordinary cross-Organization ownership change.

### Tests first

- [X] T044 [P] [US2] Add Workspace/Project contract and lifecycle tests including same-Organization composite FK rejection in `apps/api/tests/integration/tenancy/test_workspace_project.py`
- [X] T045 [P] [US2] Add cross-Organization Project move/ownership mutation rejection tests in `apps/api/tests/integration/tenancy/test_project_ownership_boundary.py`
- [X] T046 [P] [US2] Add Workspace deletion-with-active-Project invariant tests in `apps/api/tests/unit/tenancy/test_workspace_lifecycle.py` and integration coverage in `apps/api/tests/integration/tenancy/test_workspace_project.py`
- [X] T047 [P] [US2] Add Workspace/Project typed-client tests in `packages/client-sdk/tests/workspace-project.test.ts`

### Implementation

- [X] T048 [US2] Implement Workspace create/update/archive/delete lifecycle and Project create/move/un-group/archive/delete domain services in `apps/api/openvietgis_api/domains/tenancy/service.py`
- [X] T049 [US2] Implement Organization-safe Workspace/Project repositories and cross-tenant non-disclosure lookups in `apps/api/openvietgis_api/adapters/persistence/tenancy_repository.py`
- [X] T050 [US2] Implement Workspace/Project HTTP endpoints from `contracts/tenant-core-api.yaml` in `apps/api/openvietgis_api/adapters/http/workspaces.py` and `projects.py`
- [X] T051 [P] [US2] Implement Workspace/Project client methods in `packages/client-sdk/src/workspaces.ts` and `packages/client-sdk/src/projects.ts`
- [X] T052 [P] [US2] Implement minimal Workspace list/create/lifecycle UI in `apps/web/src/features/workspaces/`
- [X] T053 [P] [US2] Implement minimal Project list/create/move/un-group/archive UI in `apps/web/src/features/projects/`
- [X] T054 [US2] Add browser acceptance for create A1/A2/P1, move/un-group/archive, and ownership preservation to `tests/e2e/tenant-core.spec.ts`

**Checkpoint**: US2 can be validated with a fixture actor independently of OIDC UI and never changes Project.organization_id.

---

## Phase 5: User Story 3 — Invite People and Grant Scoped Access (Priority: P1) — P1 Tenant Core

**Goal**: Owners/Admins create recipient-bound one-time invitations and additive scoped grants; Workspace inheritance updates dynamically and revocation takes effect on the next protected request.

**Independent Test**: Create invitation targeted to a verified synthetic identity with optional Project grant, reject wrong recipient, accept intended identity once, verify Workspace/direct Project permission union, then suspend/revoke membership and observe immediate denial.

### Tests first

- [X] T055 [P] [US3] Add role-bundle/additive-union/Organization-Workspace-Project inheritance unit tests in `apps/api/tests/unit/authorization/test_role_grant_union.py`
- [X] T056 [P] [US3] Add dynamic Workspace inheritance tests proving access appears/disappears when Project moves without grant copying in `apps/api/tests/integration/tenancy/test_workspace_grant_inheritance.py`
- [X] T057 [P] [US3] Add invitation email/User/external-identity recipient-binding, expiry/revoke/reuse tests in `apps/api/tests/integration/tenancy/test_invitation_lifecycle.py`
- [X] T058 [P] [US3] Add concurrent double-accept invitation test proving exactly one atomic acceptance in `apps/api/tests/integration/tenancy/test_invitation_concurrency.py`
- [X] T059 [P] [US3] Add Last Owner role/status concurrency plus Owner-vs-Admin Organization suspend/restore/soft-delete lifecycle tests in `apps/api/tests/integration/tenancy/test_last_owner.py` and `test_organization_lifecycle.py`
- [X] T060 [P] [US3] Add next-request membership/grant revocation tests in `apps/api/tests/integration/tenancy/test_revocation.py`
- [X] T061 [P] [US3] Add grant/invitation client contract tests in `packages/client-sdk/tests/grants-invitations.test.ts`
- [X] T062 [P] [US3] Add Playwright intended-recipient invitation accept + revoke journey to `tests/e2e/invitation-revocation.spec.ts`

### Implementation

- [X] T063 [US3] Complete AuthorizationService role/grant resolution for Organization, dynamic Workspace, direct Project scope, and current Project placement in `apps/api/openvietgis_api/domains/authorization/service.py`
- [X] T064 [US3] Implement Last Owner invariant, atomic ownership-transfer operation, and Owner-controlled Organization active/suspended/deleted lifecycle with short locking transactions in `apps/api/openvietgis_api/domains/tenancy/service.py`
- [X] T065 [US3] Implement ResourceGrant create/revoke repositories and duplicate-active-grant protection in `apps/api/openvietgis_api/adapters/persistence/authorization_repository.py`
- [X] T066 [US3] Implement invitation issue/accept/revoke service including secret hashing, recipient matching, atomic membership activation/optional grant, and one-time state transition in `apps/api/openvietgis_api/domains/tenancy/service.py`
- [X] T067 [US3] Implement Organization lifecycle/ownership-transfer/member plus grant/invitation/effective-permission HTTP endpoints from `contracts/tenant-core-api.yaml` in `apps/api/openvietgis_api/adapters/http/organizations.py`, `grants.py`, and `invitations.py`
- [X] T068 [P] [US3] Implement grants/invitations/effective-permissions client methods in `packages/client-sdk/src/organizations.ts` and `invitations.ts`
- [X] T069 [P] [US3] Implement minimal membership/invite/grant UI including suspend/revoke and invitation accept handoff in `apps/web/src/features/membership/` and `apps/web/src/features/invitations/`
- [X] T070 [US3] Ensure Organization creation/lifecycle/ownership, membership, grant, and invitation mutations append foundational AuditEvent records through the T018 audit port before the P1 gate, without requiring the P2 audit-read UI, in `apps/api/openvietgis_api/domains/tenancy/service.py`

**Checkpoint**: P1 collaboration access works, inheritance is dynamic, recipient/token races are safe, and revocation is next-request effective.

---

## Phase 6: User Story 4 — Prevent Cross-Tenant Data Leakage (Priority: P1) — P1 Security Gate

**Goal**: Unauthorized cross-Organization access fails through API, repository, RLS, pooled connections, and automated-context primitives.

**Independent Test**: Create Organizations A/B with parallel resources and actors, then attempt cross-tenant reads/mutations through every protected repository and HTTP surface as the actual runtime DB role; no protected B data is returned in A context.

### Tests first

- [X] T071 [P] [US4] Add cross-tenant API/repository matrix for Organization metadata, Membership, Workspace, Project, Grant, Invitation, and protected list/detail paths in `apps/api/tests/integration/rls/test_cross_tenant_api.py`
- [X] T072 [P] [US4] Add direct repository/RLS matrix using the real runtime role for every P1 RLS-protected table listed in `data-model.md`, explicitly including `audit.audit_events`, in `apps/api/tests/integration/rls/test_cross_tenant_repository.py`
- [X] T073 [P] [US4] Add connection-pool A→B→no-context leakage regression tests under repeated pooled reuse in `apps/api/tests/integration/rls/test_pool_tenant_leak.py`
- [X] T074 [P] [US4] Add cross-tenant existence non-disclosure tests distinguishing 404 other-tenant from 403 same-tenant insufficient permission in `apps/api/tests/integration/tenancy/test_tenant_error_semantics.py`
- [X] T075 [P] [US4] Add direct cross-tenant FK/ownership insert/update rejection tests for Project/Workspace/Grant/Invitation records in `apps/api/tests/integration/rls/test_cross_tenant_constraints.py`

### Implementation / hardening

- [X] T076 [US4] Apply explicit AuthorizationContext + transaction-local RLS context to every P1 protected repository transaction in `apps/api/openvietgis_api/adapters/persistence/db.py` and `rls.py`
- [X] T077 [US4] Enforce non-disclosing cross-tenant lookup/error semantics across Organization/Workspace/Project/Grant/Invitation HTTP adapters in `apps/api/openvietgis_api/adapters/http/errors.py` and tenant adapters
- [X] T078 [US4] Add authorization-required repository interfaces so protected repositories cannot be called without explicit tenant/actor context in `apps/api/openvietgis_api/domains/tenancy/ports.py` and `domains/authorization/ports.py`
- [X] T079 [US4] Add P1 security E2E with direct URL manipulation across Organizations to `tests/e2e/tenant-core.spec.ts`
- [X] T080 [US4] Run and record the P1 Tenant Core checkpoint from quickstart sections 2-10, including foundational AuditEvent/RLS and RequestedActorContext round-trip evidence, in `specs/002-identity-organization-tenancy/quickstart.md` before enabling P2 work

**Checkpoint**: P1 Tenant Core is independently demonstrable and cross-tenant isolation is proven at application + database layers.

---

## Phase 7: User Story 5 — Use Service Principals for Automation (Priority: P2)

**Goal**: Non-human principals receive scoped additive grants and one-time bearer credentials whose optional ceiling can only restrict permissions.

**Independent Test**: Create ServicePrincipal in Org A, grant Project access, issue credential with subset ceiling, call allowed action, reject denied/cross-tenant action, revoke credential, and deny the next request.

### Tests first

- [X] T081 [P] [US5] Add ServicePrincipal/ServiceCredential migration and field-constraint tests in `apps/api/tests/integration/service_identity/test_service_identity_migration.py`
- [X] T082 [P] [US5] Add credential one-time-secret/hash/prefix/expiry/revoke unit tests in `apps/api/tests/unit/identity/test_service_credentials.py`
- [X] T083 [P] [US5] Add permission-ceiling intersection tests proving credentials cannot expand principal grants in `apps/api/tests/unit/authorization/test_service_permission_ceiling.py`
- [X] T084 [P] [US5] Add real API allowed/out-of-scope/cross-tenant/revoked-next-request tests in `apps/api/tests/integration/service_identity/test_service_authorization.py`
- [X] T085 [P] [US5] Add service-admin contract/client tests in `packages/client-sdk/tests/service-principals.test.ts`

### Implementation

- [X] T086 [US5] Implement ServicePrincipal and ServiceCredential persistence/domain mappings in `apps/api/openvietgis_api/domains/authorization/domain.py` and migration `apps/api/migrations/versions/0004_machine_identity.py`, citing [data-model.md#serviceprincipal] `ServicePrincipal.id`, `ServicePrincipal.organization_id`, `ServicePrincipal.name`, `ServicePrincipal.description`, `ServicePrincipal.status`, `ServicePrincipal.created_at`, `ServicePrincipal.created_by_actor_type`, `ServicePrincipal.created_by_actor_id`, `ServicePrincipal.revoked_at` and [data-model.md#servicecredential] `ServiceCredential.id`, `ServiceCredential.organization_id`, `ServiceCredential.service_principal_id`, `ServiceCredential.name`, `ServiceCredential.prefix`, `ServiceCredential.secret_hash`, `ServiceCredential.permission_ceiling`, `ServiceCredential.created_at`, `ServiceCredential.expires_at`, `ServiceCredential.last_used_at`, `ServiceCredential.revoked_at`
- [X] T087 [US5] Implement ServicePrincipal/credential issue/revoke/authentication and ceiling-aware authorization in `apps/api/openvietgis_api/domains/authorization/service.py` and `security/secrets.py`
- [X] T088 [US5] Implement ServicePrincipal/credential persistence and runtime RLS policies in `apps/api/openvietgis_api/adapters/persistence/authorization_repository.py` and `apps/api/migrations/versions/0004_machine_identity.py`
- [X] T089 [US5] Implement service-admin HTTP endpoints and bearer credential authentication from `contracts/service-admin-api.yaml` in `apps/api/openvietgis_api/adapters/http/service_principals.py` and shared security adapter
- [X] T090 [P] [US5] Implement ServicePrincipal client methods in `packages/client-sdk/src/service-principals.ts`

**Checkpoint**: Machine actor authorization reuses the same permission vocabulary and tenant boundary as humans.

---

## Phase 8: User Story 6 — Trace Who Performed Sensitive Actions (Priority: P2)

**Goal**: Sensitive security events remain attributable to human/service/system actors after later revocation and never contain raw secrets.

**Independent Test**: Perform sensitive mutations as a human and service principal, revoke both access paths, then query audit history and still identify actor type/display/Organization with no raw secret material.

### Tests first

- [X] T091 [P] [US6] Add authorized audit-read filtering/RLS tests on the foundational AuditEvent table in `apps/api/tests/integration/service_identity/test_audit_storage.py`
- [X] T092 [P] [US6] Add actor snapshot-after-revocation tests for human/service/system actors in `apps/api/tests/integration/service_identity/test_audit_actor_snapshot.py`
- [X] T093 [P] [US6] Add audit secret-redaction tests covering session/OIDC/invitation/service/bootstrap secret patterns in `apps/api/tests/unit/authorization/test_audit_redaction.py`

### Implementation

- [X] T094 [US6] Extend the foundational T018 audit repository with authorized tenant-scoped query/read behavior and pagination-ready ordering in `apps/api/openvietgis_api/adapters/persistence/audit_repository.py` and `apps/api/openvietgis_api/domains/audit/service.py`
- [x] T095 [US6] Complete P2 ServicePrincipal/credential/bootstrap audit wiring and actor-after-revocation snapshot behavior on top of the foundational P1 audit port in `apps/api/openvietgis_api/domains/audit/service.py` and relevant P2 domain services
- [X] T096 [US6] Implement authorized audit-read endpoint from `contracts/service-admin-api.yaml` in `apps/api/openvietgis_api/adapters/http/audit.py`

**Checkpoint**: Security actions remain explainable after revoke and audit storage has no mutation/secret path.

---

## Phase 9: User Story 7 — Bootstrap a Fresh Self-Hosted Installation (Priority: P2)

**Goal**: A fresh self-hosted installation requires both normal OIDC human identity and explicit one-time installation authority to create the first Organization/Owner, and cannot be claimed twice.

**Independent Test**: Fresh database + configured reference OIDC + bootstrap authority: anonymous/secret-only attempts fail, authenticated Owner bootstrap succeeds once, reuse fails, and resulting Owner uses normal tenant authorization.

### Tests first

- [x] T097 [P] [US7] Add bootstrap read/lock/uninitialized→initialized state-transition and immutable-initialization tests over the foundational InstallationState table in `apps/api/tests/integration/identity/test_bootstrap_storage.py`
- [x] T098 [P] [US7] Add anonymous, secret-only, authenticated-with-wrong-secret, success-once, and reuse-denial tests in `apps/api/tests/integration/identity/test_bootstrap.py`
- [x] T099 [P] [US7] Add bootstrap concurrency race proving only one initialization transaction commits in `apps/api/tests/integration/identity/test_bootstrap_concurrency.py`
- [x] T100 [P] [US7] Add Playwright OIDC + first Organization/Owner bootstrap flow covering SC-011 in `tests/e2e/bootstrap-service-identity.spec.ts`

### Implementation

- [x] T101 [US7] Implement bootstrap state read/lock/update operations over the foundational InstallationState table in `apps/api/openvietgis_api/adapters/persistence/platform_repository.py` and `apps/api/openvietgis_api/domains/bootstrap/service.py`; schema/field implementation remains owned by T018
- [x] T102 [US7] Implement one-time bootstrap service requiring authenticated User + installation authority and atomically creating Organization/Owner/AuditEvent/initialized state in `apps/api/openvietgis_api/domains/bootstrap/service.py`
- [x] T103 [US7] Implement bootstrap status/initialize HTTP endpoints with session+bootstrap-secret AND semantics from `contracts/service-admin-api.yaml` in `apps/api/openvietgis_api/adapters/http/bootstrap.py`
- [x] T104 [US7] Implement minimal first-time bootstrap UI gated by bootstrap status and authenticated User in `apps/web/src/features/organizations/BootstrapPage.tsx`
- [x] T105 [US7] Add logical shared-vs-isolated configuration fixture parity tests for identity/membership/grant/invitation/service/audit semantics in `apps/api/tests/integration/tenancy/test_isolated_deployment_parity.py`

**Checkpoint**: Self-host initialization has no anonymous-first-caller backdoor and shares normal identity/authorization semantics.

---

## Phase 10: Polish, Performance, Foundation Retirement & Convergence Prep

**Purpose**: Cross-cutting hardening after all required user stories pass.

- [X] T106 [P] Add authorization benchmark fixture with >=50 mixed relevant/irrelevant grants and dynamic Workspace inheritance in `apps/api/tests/performance/test_authorization_benchmark.py`, enforcing the quickstart p95 <= 50 ms target
- [x] T107 [P] Add full security log/audit scan ensuring provider tokens, session secrets, invitation secrets, service secrets, and bootstrap secret never appear in logs/test artifacts in `tools/check_secret_surfaces.py` and `tools/tests/test_secret_surfaces.py`
- [X] T108 [P] Extend root CI to start Keycloak reference profile, use migration/runtime DB roles, validate OpenAPI/generated types, and run Spec 002 E2E in `.github/workflows/ci.yml`
- [x] T109 Remove disposable FoundationSampleRecord API/domain/repository/client/UI/tests and drop `foundation.sample_records` in `apps/api/migrations/versions/0005_retire_foundation_sample.py` only after the P1 E2E checkpoint is green
- [x] T110 Re-run historical Spec 001 foundation gates after T109 and update architecture/docs references from disposable sample to real tenant slice in `README.md` and `docs/architecture.md` without weakening Spec 001 acceptance
- [x] T111 [P] Add backup/migration downgrade/upgrade safety tests for all Spec 002 migrations and runtime-role grants in `apps/api/tests/integration/tenancy/test_identity_tenancy_migration_cycle.py`
- [x] T112 [P] Record browser timing measurements for SC-001/SC-004 and self-host bootstrap timing for SC-011 from existing measured E2E journeys; record the owner-approved internal acceptance exception for SC-013 in `specs/002-identity-organization-tenancy/checklists/unfamiliar-user-timing.md` (real human exercise deferred, not passed; mandatory before external acceptance/release)
- [x] T113 Record all automated scenario evidence in `specs/002-identity-organization-tenancy/quickstart.md` without weakening thresholds; product owner accepts internal R002 with the explicit SC-013 exception documented above (2026-11-18)
- [x] T114 Run Node 26 root `pnpm validate`, Gitleaks, scope guard, `git diff --check`, Graphify update, and verify all Spec 002 tasks/acceptance evidence before convergence (CI 44242387123 on 7edb4f4; SC-013 owner-approved deferral recorded)
- [x] T115 Run `/speckit-converge` for Spec 002 and append only evidence-driven convergence tasks if any spec/plan/code gap remains in `specs/002-identity-organization-tenancy/tasks.md`

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 Setup**: no dependency.
- **Phase 2 Foundational**: depends on Setup and blocks all user stories.
- **US1–US4 (P1 Tenant Core)**: depend on Foundational. They can use controlled fixtures independently, but final P1 acceptance order is US1/US2 → US3 → US4.
- **P1 Gate**: T080 must pass before P2 implementation begins.
- **US5–US7 (P2)**: depend on the P1 gate. US5 and US7 can proceed in parallel; US6 extends the already-existing P1 audit store/read surface and final actor-after-revoke coverage depends on US5.
- **Polish**: depends on all required stories; FoundationSampleRecord retirement specifically depends on P1 E2E success.
- **Convergence**: last.

### User-story dependency graph

```text
Setup
  |
Foundational
  |--------------------|--------------------|
  v                    v                    v
US1 Identity        US2 Hierarchy       US3 Access/Invite
  \                    |                   /
   \-------------------+------------------/
                       |
                       v
                  US4 Isolation
                       |
                    P1 GATE
                 /      |       \
                v       v        v
             US5      US6      US7
            Service   Audit   Bootstrap
                 \      |      /
                  \-----+-----/
                        |
                     Polish
                        |
                   Convergence
```

### Parallel opportunities

- T003-T007 can run in parallel after dependencies are selected.
- T009-T011 are parallel contract/architecture guards.
- T012-T017 are separable entity/model slices but share migration file coordination; use one migration owner when multiple agents work concurrently.
- T019-T022 can run in parallel.
- Test-first tasks inside every story marked [P] can run in parallel.
- US1 and US2 can be built concurrently after Foundational because US2 can use fixture actors.
- Parts of US3 authorization tests can be prepared while US1/US2 finish, but final dynamic inheritance depends on Project placement from US2.
- US5 and US7 can proceed in parallel after T080.
- T106-T108/T111-T112 are parallel cross-cutting hardening tasks.

### File-coordination hot spots

Do not assign concurrent writers without coordination to:
- `apps/api/migrations/versions/0002_identity_tenant_core.py`
- `apps/api/migrations/versions/0004_machine_identity.py`
- `apps/api/openvietgis_api/domains/tenancy/service.py`
- `apps/api/openvietgis_api/domains/authorization/service.py`
- root `package.json`
- `.github/workflows/ci.yml`

---

## Parallel Examples

### P1 example

```text
Agent A: T031-T043 — OIDC/User/session/multi-org
Agent B: T044-T054 — Workspace/Project hierarchy with fixture actor
Agent C: prepare T055-T062 tests — grants/invitations/revocation
Integration owner: T063-T080 — shared authorization + P1 isolation gate
```

### P2 example

```text
Agent A: T081-T090 — ServicePrincipal/credential
Agent B: T097-T105 — bootstrap and isolated-parity fixture
Agent C: T091-T096 — audit once shared event port is established
```

---

## Implementation Strategy

### MVP / security-first slice

The meaningful MVP is **P1 Tenant Core**, not US1 alone:

1. Complete Setup.
2. Complete Foundational.
3. Implement US1 human identity/multi-Organization.
4. Implement US2 Workspace/Project.
5. Implement US3 grants/invitations/revocation.
6. Execute US4 isolation matrix.
7. Stop at T080 and validate P1 independently.

Only then add machine identity/bootstrap P2.

### P1 completion criteria

P1 is not complete merely because screens work. T080 requires:
- real OIDC login;
- explicit Organization context;
- membership/Workspace/Project/grants/invites;
- Last Owner and invitation concurrency;
- immediate membership/grant revocation;
- API/repository/RLS cross-tenant tests as the actual runtime role;
- pooled-connection isolation;
- P1 browser acceptance.

### Incremental P2

After P1:
1. Add ServicePrincipal/ServiceCredential.
2. Complete audit-read and P2 actor-after-revocation coverage on the already-existing P1 AuditEvent store.
3. Add self-host bootstrap.
4. Run shared-vs-isolated logical parity.
5. Retire Spec 001 disposable sample only after real product slice is stable.

---

## Requirement Coverage Notes

- FR-001–006, 048, 052: T012-T014, T018, T031-T043; FR-003 link/unlink audit is explicit in T031/T036.
- FR-007–012: normal Organization creation in T032/T037/T039/T040/T042 plus Workspace/Project T015/T044-T054.
- FR-013–029, 031–032, 047, 049–051, 053: T016-T019, T055-T080.
- FR-030: serializable RequestedActorContext in T023 with P1 evidence in T080.
- FR-033–036, 054: T081-T090.
- FR-037–038, 045: foundational AuditEvent T018/T026/T027/T070/T072 plus P2 audit-read/actor completion T091-T096.
- FR-039–041: foundational InstallationState storage T018/T030 plus bootstrap behavior T097-T105.
- FR-042–044, 046: T007, minimal UI tasks, scope guard, T114.
- SC-001–014: covered by story integration/E2E tasks, T080, T105, T112-T114.

## Notes

- Tasks intentionally avoid a custom role builder, public sharing, cross-Organization Project transfer, GIS/Layer/Map behavior, or a production dedicated-enterprise deployment.
- Keep tests red before implementing their corresponding behavior.
- Do not mark a security-sensitive task complete solely from mocked-unit coverage when a real PostgreSQL/OIDC/browser acceptance path is specified.
- P1 and P2 boundaries are implementation sequencing, not separate product authorization models.

## Takeover implementation checkpoint — 2026-11-18

**Status: P1 implementation in progress, NOT P1 accepted; R002 NOT converged or integrated into main.** 69/115 implementation tasks checked, including the 54 carried forward from the original owner. This count is not acceptance or product completion.

- Preserved all 14 dirty files from original HEAD 31c180e in d6f10df; merged verified main ea6db79 in 654a01b. Original worktree unchanged.
- Integrated independent HTTP, client, security and invariants work: 550a05f, a4ea6e2, af55581, 8f8aced, 3bdee36, 9a76c05. Coordinator commits 17e6251, 52fc609, a54e004, 9ab2561, 3a74fa7 add restricted-role safety, cross-tenant denial, authenticated invitation binding, real concurrent races and durable FR-052 conflict audit.
- On code HEAD 3a74fa7: 104 unit/contract/tool/architecture tests passed; 39 backend integration tests passed against the dedicated local PostgreSQL test DB, with application connections using verified openvietgis_runtime (admin only for fixture setup/assertions and migrations). Ruff and mypy (60 source files) passed. Client agent independently ran 12 grant/invitation SDK tests and strict TypeScript compilation; E2E files typechecked only. See quickstart for scope and limits.
- T057 remains open for complete external-identity recipient integration coverage; T059 for full owner status/role race and lifecycle coverage; T070 for exhaustive audit evidence. T073/T074 have regression coverage combined in cross-tenant repository/API tests, but retain their unchecked status pending exact task scope/path reconciliation. T076/T078 require explicit context enforcement across protected repository interfaces and transactions.
- T062/T069/T079 browser journeys/UI implemented but execution not accepted. T080 remains blocked: Node 26 baseline unavailable on host (Node 24 detected), frozen pnpm install was denied by minimumReleaseAge policy for @tanstack dependencies, and real browser OIDC P1 suite is not yet run. Do not bypass policy. Do not implement P2 or retire FoundationSampleRecord before T080.
- Next: close remaining P1 task coverage, run reference-provider E2E on the supported runtime and dependency policy, independent review and T080 evidence; only then unlock P2. Do not promote to main before full T115 convergence.

## P1 backend verification checkpoint — 2026-11-18

Code HEAD **830dea5**; 76/115 implementation tasks checked (39 open). P1 is not yet accepted and R002 is not integrated.

- T057/T059/T070/T073/T074: dedicated restricted-runtime PostgreSQL integration regressions now cover recipient email/User/external identity, expiry/revoke/reuse, concurrent Owner role/status changes, Organization lifecycle and audit, repeated A/B/no-context connection reuse, and same-tenant 403 versus missing/foreign 404. Full suite: 58 passed.
- T076/T078: mandatory actor/tenant contexts across P1 protected repository calls; transaction-local context, membership proof and savepoint/commit invalidation. Invitation acceptance uses a narrow explicit pre-membership exception; all mutations require verified context. Independent review findings were addressed, with regression coverage.
- 121 backend unit/contract/tool/architecture tests pass; Ruff, mypy (60 files), contract/scope/architecture/docs guards pass. 20 SDK and protected-query tests pass in isolated Node 26 validation.
- T062/T069/T079 remain open pending real browser evidence; T080 remains open pending all P1 gates. Portable signed Node 26.13.1 resolves the previous runtime blocker, but frozen dependency minimumReleaseAge remains in force. See quickstart section 19 for resumption.
- Do not begin P2 or retire FoundationSampleRecord until T080 passes. Do not promote R002 to main before T115 convergence.

## P1 runtime and performance checkpoint — 2026-11-18

Code HEAD **872c4ad**, **77/115 tasks checked**, 38 remaining. T106 measured against restricted-runtime PostgreSQL: benchmark initially failed p95 80.235ms; after one live SQL snapshot optimization, passed 7.954ms and 5.225ms on unchanged 63-grant/150-sample benchmark. Full integration+performance rerun: 64 passed (63 integration and benchmark), one opt-in OIDC test skipped then separately passed using the live local provider. 134 unit/contract/tools/architecture tests, static and guard checks pass. See quickstart §20. No lower-level RLS optimization included; no authorization cache.

T062/T069/T079/T080 remain open until actual frontend/browser acceptance. Browser scripts and timings prepared, not executed. T080 P1 uses FR-051 preinitialized synthetic fixture; bootstrap-specific acceptance still P2. No P2 implementation, convergence or main merge performed.

## P1 independent hardening checkpoint — 2026-11-18

Code HEAD **61bacc6**; 77/115 checked (38 open). Full Python static/unit/contract/tool/architecture 173 passed, 1 Windows symlink skip; integration + performance 66 passed, 1 opt-in OIDC skipped (previously passed separately). Final audit regressions 2 passed. T107 secret scanner and P1 runtime evidence, T108 CI fixture preparation, T111 isolated P1 migration/backup evidence, and UI security regressions are implemented in part. T107/T108/T111 remain unchecked; migration loopback repeat timed out without confirmed result. UI helper 15 passed, four targeted E2E tests collected only. See quickstart §21 for exact limits and resumption. T062/T069/T079/T080, P2, T115 and main integration remain open.

## Phase 11: Convergence

- [x] T116 [HIGH] Prevent service credential resurrection and lock-order inversion when auth and revoke race; enforce monotonic revocation, safe last-used semantics, and real restricted-runtime concurrent regression per FR-036/SC-009 (contradicts).
- [x] T117 Freeze the historical 0004 permission-ceiling migration vocabulary and add a regression preventing historical migration imports of mutable application contracts; verify unchanged upgrade/downgrade/restore per FR-035/Constitution development and quality gates (partial).
- [x] T118 Implement explicit soft-delete recovery while retaining tenant isolation, appropriate permissions, lifecycle invariants and audit; add restricted-runtime regressions per FR-031/FR-032 and the project.delete permission contract (partial).
