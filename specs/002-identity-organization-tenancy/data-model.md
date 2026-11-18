# Data Model: Identity, Organization & Tenancy

**Feature**: 002-identity-organization-tenancy
**Date**: 2026-11-18

This model extends the Spec 001 PostgreSQL foundation. It introduces product entities that replace
the disposable FoundationSampleRecord vertical slice.

## Schema ownership

| Schema | Ownership |
| --- | --- |
| `identity` | User, external identities, application sessions |
| `org` | Organization, membership, grants, invitations, service principals/credentials |
| `workspace` | Workspace and Project hierarchy |
| `audit` | append-only tenant security/audit events |
| `platform` | installation/bootstrap state |

The schema names are organizational boundaries, not separate databases.

---

## Persistence conventions

- Product UUIDs remain UUID values; business slugs/codes are separate.
- Roles/status/discriminators are persisted as text values with named CHECK constraints rather than
  PostgreSQL ENUM types so future compatible additions do not require type-rewrite migrations.
- Secret/token digests are stored as `bytea`.
- Permission ceilings use PostgreSQL `text[]`.
- Audit metadata uses `jsonb`; arbitrary business state is not moved into JSONB.

---

## User

Represents one internal human person independent from any Organization or external provider.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | system identifier |
| `display_name` | text | yes | non-empty |
| `email_snapshot` | text | no | descriptive only; never identity key |
| `status` | enum | yes | `active`, `disabled` |
| `created_at` | timestamptz | yes | immutable creation time |
| `updated_at` | timestamptz | yes | current profile update time |

### Invariants

- One User may have zero or many IdentityLinks.
- A disabled User cannot create a new authenticated application session.
- User does not store active Organization state.

---

## IdentityLink

Maps a verified external OIDC identity to exactly one User.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | system identifier |
| `user_id` | UUID | yes | FK → User |
| `issuer` | text | yes | normalized OIDC issuer |
| `subject` | text | yes | provider subject |
| `email_snapshot` | text | no | provider claim snapshot |
| `email_verified` | boolean | yes | claim at last verified login/link |
| `display_name_snapshot` | text | no | provider display snapshot |
| `created_at` | timestamptz | yes | |
| `last_login_at` | timestamptz | no | |

### Constraints

- UNIQUE(`issuer`, `subject`).
- Linking an existing issuer+subject to a different User is rejected and audited.
- Email changes do not move the IdentityLink to another User.

---

## WebSession

Opaque first-party application session for a human User.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | non-secret public/internal reference |
| `user_id` | UUID | yes | FK → User |
| `identity_link_id` | UUID | yes | FK → IdentityLink used to authenticate |
| `secret_hash` | bytea | yes | SHA-256 digest of random session secret; raw secret never stored |
| `issued_at` | timestamptz | yes | |
| `expires_at` | timestamptz | yes | absolute expiry |
| `last_seen_at` | timestamptz | no | operational metadata |
| `revoked_at` | timestamptz | no | null while usable |

### State

```text
ACTIVE -> REVOKED
   \----> EXPIRED (derived by time)
```

Session authenticates User only. It does not persist role, Organization, or permission snapshots.

---

## Organization

Top-level tenant ownership boundary.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | system identifier |
| `name` | text | yes | non-empty |
| `slug` | text | yes | globally unique normalized slug |
| `status` | enum | yes | `active`, `suspended`, `deleted` |
| `created_by_actor_type` | enum | yes | `human`, `service_principal`, `system` |
| `created_by_actor_id` | UUID | no | null only for system |
| `created_at` | timestamptz | yes | |
| `updated_at` | timestamptz | yes | |
| `deleted_at` | timestamptz | no | required when deleted |

### Invariants

- Normal authenticated Organization creation atomically creates the Organization and the creator's
  active Owner membership.
- Every active Organization has at least one active Owner membership.
- Last-Owner mutations serialize on the Organization before changing ownership/membership state.
- Deleted/suspended Organizations reject normal tenant mutations.
- Physical purge is outside Spec 002.

---

## OrganizationMembership

Relationship between a human User and one Organization.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | yes | FK → Organization |
| `user_id` | UUID | yes | FK → User |
| `role` | enum | yes | `owner`, `admin`, `member`, `guest` |
| `status` | enum | yes | `active`, `suspended`, `revoked` |
| `created_at` | timestamptz | yes | |
| `activated_at` | timestamptz | no | |
| `suspended_at` | timestamptz | no | |
| `revoked_at` | timestamptz | no | |

### Constraints

- UNIQUE(`organization_id`, `user_id`).
- Provide UNIQUE(`organization_id`, `id`) to support organization-safe composite references.
- Pending invitation is not a Membership state.
- Only active memberships contribute permissions.

---

## Workspace

Optional grouping/resource scope inside one Organization.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | yes | FK → Organization |
| `name` | text | yes | |
| `slug` | text | yes | unique within Organization |
| `status` | enum | yes | `active`, `archived`, `deleted` |
| `created_by_actor_type` | enum | yes | `human`, `service_principal`, `system` |
| `created_by_actor_id` | UUID | no | null only for system |
| `created_at` | timestamptz | yes | |
| `updated_at` | timestamptz | yes | |
| `archived_at` | timestamptz | no | |
| `deleted_at` | timestamptz | no | |

### Constraints / invariants

- UNIQUE(`organization_id`, `slug`).
- UNIQUE(`organization_id`, `id`) for composite references.
- A Workspace cannot enter deleted state while active Projects still reference it.
- Archiving/deleting Workspace never changes Project.organization_id.
- Recover a deleted Workspace by an authorized status-only transition to `active`; its identity,
  organization ownership, references and audit history are retained.

---

## Project

Durable work container directly owned by Organization and optionally grouped by Workspace.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | yes | FK → Organization |
| `workspace_id` | UUID | no | optional grouping |
| `name` | text | yes | |
| `slug` | text | yes | unique within Organization so Workspace moves do not change identity |
| `status` | enum | yes | `active`, `archived`, `deleted` |
| `created_by_actor_type` | enum | yes | `human`, `service_principal`, `system` |
| `created_by_actor_id` | UUID | no | null only for system |
| `created_at` | timestamptz | yes | |
| `updated_at` | timestamptz | yes | |
| `archived_at` | timestamptz | no | |
| `deleted_at` | timestamptz | no | |

### Constraints

- UNIQUE(`organization_id`, `slug`).
- UNIQUE(`organization_id`, `id`).
- Composite FK (`organization_id`, `workspace_id`) →
  Workspace(`organization_id`, `id`) when workspace_id is non-null.
- Ordinary update cannot change organization_id.
- Archived Project remains readable for authorized users; normal content/settings mutations are
  rejected except explicit restore/management operations.

### State

```text
ACTIVE <-> ARCHIVED -> DELETED
  \-----------------> DELETED
DELETED --explicit status-only restore--> ACTIVE
```

Deleted Projects are excluded from ordinary lists and detail reads. Recovery requires the
appropriate archive and delete permissions, keeps the current grouping unchanged, and clears
archival/deletion timestamps; if grouped, the original Workspace must already be active.
Physical purge is outside Spec 002.

---

## ResourceGrant

Additive scoped resource-role grant for a human Membership or ServicePrincipal.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | yes | tenant owner |
| `subject_kind` | enum | yes | `membership`, `service_principal` |
| `membership_id` | UUID | conditional | set only for membership subject |
| `service_principal_id` | UUID | conditional | set only for service subject |
| `scope_kind` | enum | yes | `organization`, `workspace`, `project` |
| `workspace_id` | UUID | conditional | set only for Workspace scope |
| `project_id` | UUID | conditional | set only for Project scope |
| `role` | enum | yes | `manager`, `editor`, `contributor`, `viewer` |
| `created_at` | timestamptz | yes | |
| `created_by_actor_type` | enum | yes | human/service/system |
| `created_by_actor_id` | UUID | no | null only for system |
| `revoked_at` | timestamptz | no | null while active |

### Constraints

- Exactly one subject FK is populated and matches subject_kind.
- Composite subject FK includes organization_id to prevent cross-tenant subject references.
- For scope_kind=organization, workspace_id/project_id are null.
- For scope_kind=workspace, workspace_id is set and project_id is null.
- For scope_kind=project, project_id is set and workspace_id is null.
- Composite Workspace/Project FKs include organization_id.
- Revoked grants do not contribute permissions.
- Duplicate simultaneously-active grant for the same subject/scope/role is rejected.

### Dynamic inheritance

```text
Organization grant
  -> all resource operations in Organization

Workspace grant
  -> Workspace
  -> Projects where project.workspace_id == grant.workspace_id NOW

Project grant
  -> Project only
```

Inherited access is computed, not copied. Moving a Project changes inheritance immediately.

---

## Invitation

One-time invitation to create/activate Organization membership and optionally one resource grant.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | yes | |
| `status` | enum | yes | `pending`, `accepted`, `revoked`, `expired` |
| `target_kind` | enum | yes | `email`, `user`, `external_identity` |
| `target_email_normalized` | text | conditional | verified-email target |
| `target_user_id` | UUID | conditional | internal User target |
| `target_issuer` | text | conditional | external identity target |
| `target_subject` | text | conditional | external identity target |
| `organization_role` | enum | yes | owner/admin/member/guest; owner invitation requires Owner authority |
| `resource_scope_kind` | enum | no | organization/workspace/project |
| `resource_workspace_id` | UUID | no | |
| `resource_project_id` | UUID | no | |
| `resource_role` | enum | no | manager/editor/contributor/viewer |
| `token_hash` | bytea | yes | SHA-256 digest only |
| `token_prefix` | text | yes | safe display/support prefix |
| `expires_at` | timestamptz | yes | |
| `created_at` | timestamptz | yes | |
| `created_by_actor_type` | enum | yes | |
| `created_by_actor_id` | UUID | no | |
| `accepted_at` | timestamptz | no | |
| `accepted_by_user_id` | UUID | no | |
| `revoked_at` | timestamptz | no | |

### Constraints / transition

Exactly one target form is valid.

```text
PENDING -> ACCEPTED
   |-----> REVOKED
   \-----> EXPIRED
```

Acceptance transaction:
1. establish organization context from invitation link identifiers;
2. lock pending invitation;
3. verify secret hash and expiry;
4. verify authenticated User/IdentityLink matches target;
5. create or reactivate Membership without violating Last Owner invariant;
6. create optional ResourceGrant;
7. mark invitation accepted;
8. append AuditEvent;
9. commit atomically.

---

## ServicePrincipal

Non-human actor owned by one Organization.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | yes | |
| `name` | text | yes | unique within Organization |
| `description` | text | no | |
| `status` | enum | yes | `active`, `revoked` |
| `created_at` | timestamptz | yes | |
| `created_by_actor_type` | enum | yes | `human`, `service_principal`, `system` |
| `created_by_actor_id` | UUID | no | null only for system |
| `revoked_at` | timestamptz | no | |

### Invariants

- Cannot authenticate through interactive human login.
- Permissions come from active ResourceGrants.
- Revoked principal invalidates all credentials for authorization.

---

## ServiceCredential

Bearer credential for one ServicePrincipal.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | yes | composite tenant reference |
| `service_principal_id` | UUID | yes | |
| `name` | text | yes | operator-visible label |
| `prefix` | text | yes | safe display/lookup prefix |
| `secret_hash` | bytea | yes | SHA-256 digest; raw secret shown once only |
| `permission_ceiling` | text[] | no | optional subset of stable permission codes |
| `created_at` | timestamptz | yes | |
| `expires_at` | timestamptz | no | |
| `last_used_at` | timestamptz | no | |
| `revoked_at` | timestamptz | no | |

### Effective authorization

```text
effective_service_permissions =
  union(active ServicePrincipal ResourceGrants)
  INTERSECT credential.permission_ceiling (if present)
```

Credential ceiling can only restrict, never add permission.

---

## AuditEvent

Foundational P1 append-only security/audit record. The table and its tenant RLS exist before the P1
security gate; P2 adds richer audit read/actor-after-revocation acceptance rather than introducing
the table for the first time.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `id` | UUID | yes | |
| `organization_id` | UUID | no | null only for global pre-tenant/system event |
| `actor_type` | enum | yes | `human`, `service_principal`, `system` |
| `actor_id` | UUID | no | null for system |
| `actor_display_snapshot` | text | yes | historical readability |
| `action` | text | yes | stable audit action code |
| `resource_type` | text | no | |
| `resource_id` | UUID | no | |
| `outcome` | enum | yes | `success`, `denied`, `failure` |
| `metadata` | JSONB object | yes | safe structured metadata only |
| `created_at` | timestamptz | yes | immutable |

### Invariants

- Runtime application has append/read paths only; no user edit/delete path.
- Never record raw session, invitation, service credential, provider token, or bootstrap secrets.
- Tenant events are RLS protected.

---

## InstallationState

Foundational global installation state stored from P1 so normal Organization creation can reject an
uninitialized self-host deployment. P2 bootstrap owns the one-time transition from uninitialized to
initialized; the table itself is not a P2 dependency.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `singleton_key` | fixed key | yes | exactly one logical row |
| `initialized_at` | timestamptz | no | null before bootstrap |
| `initial_organization_id` | UUID | no | set on initialization |
| `initialized_by_user_id` | UUID | no | authenticated bootstrap User |
| `updated_at` | timestamptz | yes | |

Bootstrap secret itself is deployment configuration and is never persisted in this table.

---

## Permission registry

Permissions are code/contracts, not tenant-editable rows in Spec 002.

### Organization membership roles

| Role | Permission semantics |
| --- | --- |
| Owner | organization admin + organization-wide resource management + Owner-only invariants |
| Admin | organization/member admin + organization-wide resource management except Owner-only invariants |
| Member | basic organization/self-membership access; no implicit Workspace/Project access |
| Guest | no implicit organization directory/resource access; explicit ResourceGrant only |

### Resource roles

| Role | Permission bundle |
| --- | --- |
| Manager | resource read/edit/manage/share/archive/delete within valid scope |
| Editor | resource read/edit/share within valid scope |
| Contributor | resource read/edit without management authority |
| Viewer | resource read only |

Concrete stable permission codes are defined in the API contract/permission registry and are returned
to the client as effective permissions.

---

## RLS coverage

RLS is required on at least:

- `org.organization_memberships`
- `workspace.workspaces`
- `workspace.projects`
- `org.resource_grants`
- `org.invitations`
- `org.service_principals`
- `org.service_credentials`
- `audit.audit_events`

Global identity tables are protected by narrowly-scoped repositories/authentication flow rather than
tenant RLS because they exist before an active Organization is selected.

### Runtime DB contexts

- `openvietgis.actor_user_id`: current human User for self-membership discovery; empty for service actor.
- `openvietgis.organization_id`: active Organization for tenant operations.
- additional actor/service identifiers may be carried in application AuthorizationContext but RLS
  policy should remain simple and tenant-owned whenever possible.

The API runtime database role must not be superuser and must not hold BYPASSRLS.

---

## RequestedActorContext

Serializable non-persistent value object for future background handoff. Spec 002 does not add a job
table, queue, worker, retry state, or scheduler.

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `actor_type` | text | yes | `human`, `service_principal`, or `system` |
| `actor_id` | UUID | conditional | null only for system |
| `organization_id` | UUID | yes | explicit tenant boundary |
| `workspace_id` | UUID | no | optional requested resource scope |
| `project_id` | UUID | no | optional requested resource scope |

### Invariants

- The value round-trips to/from a plain serialization payload without permission snapshots.
- Restoring the envelope never restores cached permissions; current membership/grants/credential
  state must be re-evaluated when authorization actually occurs.
- Workspace/Project scope, when present, must belong to `organization_id`.