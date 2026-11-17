# Feature Specification: Identity, Organization & Tenancy

**Feature Branch**: `002-identity-organization-tenancy`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Establish the OpenVietGIS identity, organization, workspace, project, membership, permission, invitation, service-account, tenant-isolation, audit-actor, and self-host bootstrap foundation. A user may belong to multiple organizations. Organization is the highest tenant ownership boundary. Workspace is optional grouping, not mandatory ownership. Projects belong directly to an organization. Access is permission-driven, invitations are secure and revocable, cross-tenant access must never leak, service principals are distinct actors, and Cloud/Self-host/Enterprise share the same logical product model."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Work Across Multiple Organizations Safely (Priority: P1)

A user can belong to multiple organizations, switch the active organization for the current work
session, and see only resources that belong to the selected organization and that the user is
authorized to access.

**Why this priority**: Multi-organization identity and an explicit tenant boundary are foundational
to every later OpenVietGIS capability. A mistake here would allow users to see or change another
organization's data.

**Independent Test**: Create one user who belongs to two organizations with different roles, switch
between the two organizations, and verify that the visible organizations, workspaces, projects, and
allowed actions change correctly without exposing data from the other organization.

**Acceptance Scenarios**:

1. **Given** a user belongs to Organization A and Organization B, **When** the user switches the active
   organization from A to B, **Then** subsequent workspace/project access is evaluated within B and
   does not continue using A implicitly.
2. **Given** a user is active in Organization A, **When** the user attempts to access a resource owned
   by Organization B without a valid B membership or grant, **Then** access is denied and no protected
   resource data is returned.
3. **Given** a user's role differs between organizations, **When** the user switches organizations,
   **Then** the available actions reflect the role and scoped grants of the active organization.

---

### User Story 2 - Organize Workspaces and Projects (Priority: P1)

An authorized organization member can create workspaces and projects, group projects into workspaces,
move projects between workspaces within the same organization, archive projects, and restore normal
work without changing who owns the project.

**Why this priority**: Organization, workspace, and project are the primary product hierarchy used by
all later GIS data, collaboration, module, and processing features.

**Independent Test**: In one organization, create two workspaces and one project, move the project
between the workspaces, remove it from workspace grouping, archive it, and confirm that organization
ownership stays unchanged throughout.

**Acceptance Scenarios**:

1. **Given** an authorized member in an organization, **When** the member creates a workspace and
   project, **Then** both resources belong to that organization.
2. **Given** a project belongs to Organization A and Workspace A1, **When** an authorized member moves
   it to Workspace A2, **Then** only the grouping changes; the project remains owned by Organization A.
3. **Given** a project belongs to an organization, **When** its workspace grouping is removed,
   **Then** the project remains valid and directly owned by the organization.
4. **Given** an active project, **When** an authorized member archives it, **Then** normal mutations
   are restricted while permitted users can still inspect it.
5. **Given** a project in Organization A, **When** a normal move operation attempts to place it under
   Organization B, **Then** the operation is rejected and requires a separate organization-transfer
   workflow outside ordinary workspace movement.

---

### User Story 3 - Invite People and Grant Scoped Access (Priority: P1)

An organization owner or administrator can invite another person, assign an intended organization
role and optional narrower resource access, and later revoke or suspend that access without relying
on the person's email address as the permanent identity key.

**Why this priority**: Team collaboration depends on safe invitations, resource grants, and
membership lifecycle management.

**Independent Test**: Invite a new person to an organization, accept the invitation using a linked
identity, verify access to the intended resources only, and then revoke the membership and confirm
that access stops.

**Acceptance Scenarios**:

1. **Given** an authorized inviter, **When** an invitation is created, **Then** it records the target
   organization, intended role, optional resource scope, expiry, and invitation state without
   prematurely granting active membership.
2. **Given** a valid invitation, **When** the invited person accepts it using a verified identity,
   **Then** an active organization membership is created and the invitation becomes unusable.
3. **Given** an invitation has expired, been revoked, or already been accepted, **When** it is used
   again, **Then** acceptance is denied.
4. **Given** an active member with scoped project access, **When** the member is revoked or suspended,
   **Then** the next protected action is denied without waiting for a long-lived login session to
   expire.
5. **Given** the last active Owner of an organization, **When** an action would remove, revoke, or
   downgrade that Owner without first transferring ownership, **Then** the action is rejected.
6. **Given** an organization member has a general role plus a narrower resource grant, **When** an
   action is evaluated, **Then** permission is decided from the effective permissions for the
   organization/resource rather than from UI visibility or a hard-coded role name.

---

### User Story 4 - Prevent Cross-Tenant Data Leakage (Priority: P1)

An organization can rely on OpenVietGIS to prevent reads, edits, sharing, invitations, service
accounts, or background operations from crossing the organization boundary unless an explicit,
valid membership or transfer workflow authorizes it.

**Why this priority**: Tenant isolation is a platform security boundary and a failure would be more
severe than a normal feature defect.

**Independent Test**: Create two organizations with separate users, workspaces, projects,
invitations, grants, and service principals, then execute both normal and lower-level access paths
and verify that every unauthorized cross-organization attempt is denied.

**Acceptance Scenarios**:

1. **Given** Organization A and Organization B contain similarly named resources, **When** an A user
   requests a B project, **Then** no B project data is returned.
2. **Given** a user can administer Organization A, **When** the user attempts to modify a Workspace,
   Project, Invitation, Resource Grant, Service Principal, or credential owned by Organization B,
   **Then** the action is denied.
3. **Given** a protected resource lookup is performed through a lower-level data access path rather
   than a UI flow, **When** tenant context is not authorized, **Then** protected cross-tenant data is
   still inaccessible.
4. **Given** a background or automated action was requested in Organization A, **When** it executes,
   **Then** it retains the organization and actor context of the request and cannot operate on B
   resources by default.
5. **Given** a resource belongs to Organization A, **When** another tenant-owned resource in
   Organization B attempts to reference it directly, **Then** the cross-tenant ownership reference
   is rejected.

---

### User Story 5 - Use Service Principals for Automation (Priority: P2)

An organization administrator can create a non-human service principal for integrations or
automation, issue a scoped credential once, revoke it, and see the service principal represented as
a distinct actor rather than pretending that an automation is a human user.

**Why this priority**: API integrations and future automation/jobs need safe non-human identities,
but they are secondary to human membership and tenant isolation.

**Independent Test**: Create a service principal with limited organization/project scope, use its
credential for an allowed action, attempt a disallowed action, revoke the credential, and verify the
credential can no longer be used.

**Acceptance Scenarios**:

1. **Given** an authorized administrator, **When** a service principal is created, **Then** it belongs
   to exactly one organization and cannot log into the interactive user interface as a person.
2. **Given** a service principal, **When** a credential is issued, **Then** the raw secret is shown
   only during creation while future records retain only safe identifying/verification metadata.
3. **Given** a scoped service credential, **When** it attempts an allowed action, **Then** the action
   succeeds within its organization and resource scope.
4. **Given** the same credential, **When** it attempts an action outside its permissions or
   organization, **Then** the action is denied.
5. **Given** a revoked or expired credential, **When** it is used again, **Then** access is denied.

---

### User Story 6 - Trace Who Performed Sensitive Actions (Priority: P2)

An administrator or auditor can determine whether a sensitive action was performed by a human,
service principal, or system process, even after the actor's membership or credential is later
revoked.

**Why this priority**: Membership, ownership, invitations, credentials, and tenant administration
must remain accountable over time.

**Independent Test**: Perform sensitive actions as a human member and a service principal, revoke
both access paths, and verify that audit history still identifies the original actor and
organization context.

**Acceptance Scenarios**:

1. **Given** a human performs a protected action, **When** the event is audited, **Then** the audit
   record identifies the human actor and organization context.
2. **Given** a service principal performs a protected action, **When** the event is audited, **Then**
   the audit record identifies it as a service principal rather than a human.
3. **Given** the original actor is later revoked or removed, **When** historical audit is inspected,
   **Then** enough actor information remains to understand who or what performed the action.

---

### User Story 7 - Bootstrap a Fresh Self-Hosted Installation (Priority: P2)

An operator of a fresh self-hosted installation can perform a one-time setup to establish the first
organization and Owner, after which the bootstrap mechanism can no longer be reused and normal
identity/membership rules apply.

**Why this priority**: Self-host must be usable without introducing a second identity model or a
permanent privileged backdoor.

**Independent Test**: Start from a fresh installation, complete one-time bootstrap, confirm the first
Owner and organization exist, then attempt to reuse the bootstrap mechanism and verify it is denied.

**Acceptance Scenarios**:

1. **Given** a fresh installation with no organization or Owner, **When** the authorized one-time
   bootstrap is completed, **Then** the first organization and active Owner are created.
2. **Given** bootstrap has succeeded, **When** the bootstrap mechanism is used again, **Then** it is
   rejected.
3. **Given** the first Owner exists, **When** subsequent membership and organization actions occur,
   **Then** they use the same normal authorization model as other deployments.
4. **Given** an organization uses an isolated enterprise deployment, **When** the same identity,
   membership, workspace, project, grant, and audit flows are exercised, **Then** their product
   semantics match those of the shared deployment model.

### Edge Cases

- A user has several linked external identities, one of which changes email address.
- Two people attempt to accept the same invitation at nearly the same time.
- The intended invite email does not match the current email claim of the identity being used to
  accept it.
- An invitation expires while an acceptance request is in progress.
- The last Owner attempts to leave the organization, suspend themselves, or delete their account.
- Two Owners attempt conflicting ownership transfers simultaneously.
- A project is archived while another member is editing its settings.
- A workspace is archived or deleted while it still groups active projects.
- A project is removed from a workspace but remains directly owned by its organization.
- A project transfer is requested while it has active grants, invitations, or dependent resources.
- A user's membership is revoked while the user has an active browser session.
- A service credential is revoked while an automated request is in flight.
- A service principal or invitation identifier from Organization A is supplied while Organization B
  is active.
- An organization is soft-deleted while users still have active sessions.
- The same external identity is accidentally linked to multiple internal users.
- An external identity provider becomes temporarily unavailable after the user already has an
  OpenVietGIS account.
- A tenant-owned resource is queried without an explicit organization context.
- A resource identifier exists in one organization but not in the user's active organization.
- The bootstrap mechanism is invoked after the platform already contains an organization or active
  Owner.
- A dedicated enterprise deployment contains only one organization but still exercises the same
  organization-scoped permission rules.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST represent a person independently from any one organization membership
  and MUST allow one person to hold active memberships in multiple organizations.
- **FR-002**: The system MUST support linking one internal person to one or more verified external
  identities using a stable provider identity rather than email address as the permanent identity
  key.
- **FR-003**: Linking, unlinking, or merging identities MUST be explicit and auditable and MUST NOT
  silently merge people based only on matching email addresses.
- **FR-004**: Organization MUST be the highest ownership boundary for tenant-owned resources in this
  feature.
- **FR-005**: Each protected work request MUST have an explicit active organization context before
  tenant-owned access is evaluated.
- **FR-006**: The system MUST allow a user to switch between organizations in which the user has an
  active membership.
- **FR-007**: The system MUST create Organization, Workspace, and Project resources with stable
  identifiers and human-readable names/codes suitable for later references.
- **FR-008**: Every Workspace and Project MUST belong directly to exactly one Organization.
- **FR-009**: Workspace membership in the hierarchy MUST be optional for a Project; removing or
  changing Workspace grouping MUST NOT change Project organization ownership.
- **FR-010**: Moving a Project between Workspaces MUST be limited to Workspaces owned by the same
  Organization.
- **FR-011**: Moving a Project to a different Organization MUST NOT be treated as an ordinary
  Workspace move and MUST require a separate controlled transfer workflow.
- **FR-012**: Tenant-owned resources from different Organizations MUST NOT form direct ownership
  references that bypass the Organization boundary.
- **FR-013**: Organization access lifecycle MUST distinguish invited access through the
  Invitation entity from active, suspended, and revoked Organization Membership states; accepting a
  valid invitation is what creates or activates membership.
- **FR-014**: The system MUST preserve at least one active Owner for every active Organization and
  MUST reject operations that would leave an Organization without an active Owner.
- **FR-015**: Owner-only destructive or ownership-transfer operations MUST remain distinct from normal
  administrator permissions.
- **FR-016**: The feature MUST provide fixed initial organization roles of Owner, Admin, Member, and
  Guest, with authorization based on the permissions granted by those roles rather than scattered
  role-name checks.
- **FR-017**: The feature MUST provide fixed initial project roles of Manager, Editor, Contributor,
  and Viewer.
- **FR-018**: Roles MUST act as bundles of permission actions; authorization decisions MUST evaluate
  permissions and resource scope rather than UI visibility alone.
- **FR-019**: The initial permission vocabulary MUST cover at least organization reading/member
  management, workspace reading/management, project reading/editing/management/archive/delete/
  transfer/share, invitation management, and service-principal management.
- **FR-020**: Permission grants MUST be able to scope a membership or service principal to a specific
  organization, workspace, or project without requiring a separate membership-table design for
  every resource type.
- **FR-021**: The initial authorization model MUST be grant-based and MUST NOT require a general
  configurable deny-policy language.
- **FR-022**: Guest membership MUST provide no implicit organization-wide resource visibility beyond
  the resources and actions explicitly granted.
- **FR-023**: Invitation MUST be a distinct entity from active membership and MUST record its target
  organization, intended role, optional resource scope, lifecycle state, and expiry.
- **FR-024**: Invitation acceptance MUST be one-time, revocable before acceptance, and rejected after
  expiry, revocation, or successful use.
- **FR-025**: Accepting an invitation MUST create or activate membership for the verified internal
  user and MUST NOT make the invite email the permanent identity key.
- **FR-026**: Invitation secrets MUST NOT remain recoverable from stored invitation records after
  creation.
- **FR-027**: Revoking or suspending a membership MUST prevent the member's next protected action
  without relying solely on a long remaining login-session lifetime.
- **FR-028**: Authorization MUST be evaluated through one consistent product authorization boundary
  that can be reused by interactive users, automated actions, background work, and future modules.
- **FR-029**: The system MUST prevent unauthorized cross-organization reads and mutations even when
  access is attempted through lower-level data access paths rather than normal UI flows.
- **FR-030**: Automated/background work MUST retain the requesting organization and actor context
  needed to apply the same authorization boundary.
- **FR-031**: Organization, Workspace, and Project deletion MUST use recoverable lifecycle states;
  permanent purge MUST remain a separate controlled operation.
- **FR-032**: Project lifecycle MUST distinguish at least active, archived, and deleted states, and
  archived projects MUST remain inspectable by authorized users while normal mutations are
  restricted.
- **FR-033**: The system MUST support Service Principals as non-human organization actors that cannot
  use the interactive human login experience.
- **FR-034**: Each Service Principal MUST belong to exactly one Organization and MUST receive only
  explicitly granted permissions/scopes.
- **FR-035**: Service credentials MUST reveal their usable secret only at creation time and MUST
  thereafter retain only the information needed to identify, verify, expire, revoke, and audit the
  credential.
- **FR-036**: Service credentials MUST support explicit expiry and revocation, and revoked/expired
  credentials MUST be denied on subsequent use.
- **FR-037**: Audit records for sensitive administration and access-control actions MUST identify the
  actor type, stable actor reference, organization context, and enough actor display information to
  remain understandable after access is revoked.
- **FR-038**: Audit records MUST distinguish human users, service principals, and system actions.
- **FR-039**: A fresh self-hosted installation MUST provide a one-time bootstrap flow that can create
  the first Organization and its first active Owner without creating a separate permanent identity
  model.
- **FR-040**: The self-host bootstrap mechanism MUST become unusable after successful initial setup
  and MUST reject reuse when the platform already contains initialized ownership.
- **FR-041**: Shared and isolated enterprise deployment modes MUST preserve the same logical identity,
  organization, membership, workspace, project, permission, invitation, service-principal, and
  audit semantics.
- **FR-042**: The feature MUST provide only the minimum user interface needed to prove organization
  switching, membership visibility, workspace/project creation, invitation acceptance, and
  membership revocation; a full administration console is out of scope.
- **FR-043**: Public or anonymous share links MUST NOT be introduced in this feature.
- **FR-044**: User-defined/custom role creation MUST NOT be introduced in this feature.
- **FR-045**: Tenant ownership, authorization, invitation, service credential, ownership transfer,
  bootstrap, and membership lifecycle changes MUST be auditable where they affect protected access.
- **FR-046**: The feature MUST preserve a clear future boundary for later Layer, Spatial Catalog,
  Map, Editing, Processing, Field, and Module features without adding those capabilities to this
  feature.

### Key Entities

- **User**: The internal representation of a human person, independent from any one organization or
  external identity provider.
- **Identity Link**: A verified external identity associated with a User through a stable provider
  identity reference; email may be descriptive but is not the permanent identity key.
- **Organization**: The highest tenant ownership boundary in this feature.
- **Organization Membership**: The active or previously active relationship between a User and an
  Organization, including role and active/suspended/revoked lifecycle; pending invitation state is
  represented separately by Invitation.
- **Workspace**: An optional grouping container inside an Organization for organizing Projects.
- **Project**: A durable organization-owned work container that may optionally belong to a
  Workspace and has active/archived/deleted lifecycle states.
- **Resource Grant**: A scoped authorization grant that associates a User membership or Service
  Principal with a resource scope, role, and effective permissions.
- **Invitation**: A temporary, expiring, revocable invitation to join an Organization with an
  intended role and optional narrower resource scope.
- **Service Principal**: A non-human actor belonging to one Organization for integrations and
  automation.
- **Service Credential**: A revocable/expiring secret credential associated with a Service
  Principal; the usable secret is not recoverable after issuance.
- **Audit Actor**: The representation of the human, service principal, or system actor captured for
  an auditable action, including organization context and a historical display snapshot.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who belongs to at least three Organizations can switch the active Organization
  and reach the correct Organization workspace/project context in under 10 seconds without logging
  out or creating another account.
- **SC-002**: In automated isolation tests covering protected resources introduced by this feature,
  100% of unauthorized cross-Organization read and mutation attempts are denied without returning
  protected data.
- **SC-003**: Revoking or suspending a membership causes the next protected action by that membership
  to be denied in 100% of automated revocation tests.
- **SC-004**: An invited user can accept a valid invitation and reach the intended Organization and
  scoped resource access in under 3 minutes using only the documented user flow.
- **SC-005**: Expired, revoked, and already-used invitations are rejected in 100% of automated
  invitation lifecycle tests.
- **SC-006**: No tested operation can remove, suspend, revoke, or downgrade the final active Owner of
  an active Organization without first establishing another active Owner.
- **SC-007**: A Project can be moved between two Workspaces in the same Organization and removed from
  Workspace grouping while preserving the same Organization owner and Project identifier in 100% of
  lifecycle tests.
- **SC-008**: Ordinary workspace/project operations cannot move a Project into another Organization
  in 100% of transfer-boundary tests.
- **SC-009**: A scoped Service Principal can successfully perform all actions granted to it, is denied
  all tested out-of-scope actions, and loses access immediately after its credential is revoked.
- **SC-010**: For every audited sensitive flow exercised by this feature, reviewers can identify
  whether the actor was a human, service principal, or system action and identify the Organization
  context after the actor's access has been revoked.
- **SC-011**: A fresh self-hosted installation can complete first-Organization/first-Owner bootstrap
  in under 5 minutes using documented setup steps, and every subsequent bootstrap reuse attempt is
  rejected.
- **SC-012**: The same feature acceptance suite for identity, membership, organization ownership,
  workspace/project lifecycle, grants, invitations, service principals, and audit semantics can be
  exercised without changing product behavior assumptions between shared and isolated deployment
  modes.
- **SC-013**: A user with no prior product orientation can complete the minimum flow of switching
  Organization, creating a Workspace, creating a Project, and viewing their membership in under
  5 minutes using the feature's minimal interface.
- **SC-014**: The feature introduces zero public/anonymous sharing flows, zero custom-role builder,
  and zero GIS/Layer/Map/Editing/Processing/Field/vertical-module behavior.

## Assumptions

- The platform foundation from Spec 001 is already available and remains the base development and
  validation environment.
- Organization is the tenant boundary; Workspace is a grouping construct and may additionally be
  used as a permission scope without becoming mandatory ownership ancestry.
- A Project always belongs directly to an Organization even when grouped in a Workspace.
- Cross-Organization project transfer is intentionally not implemented as an ordinary move; this
  feature only establishes the boundary and rejects accidental transfer through normal operations.
- Fixed roles are sufficient for the initial release. Custom role creation is deferred until the
  permission vocabulary has been validated by real workflows.
- Authorization is grant-based for this feature. A general configurable deny-policy language is
  deferred.
- Public/anonymous share links are deferred to a separate feature because they have a different
  security model.
- External identity providers are responsible for authenticating the external identity; OpenVietGIS
  owns the internal User, organization memberships, roles, grants, service principals, and
  authorization semantics.
- A person may link multiple verified external identities, but identity merging/linking is explicit
  and auditable.
- The self-host bootstrap path is a one-time initialization mechanism, not a permanent alternative
  to normal identity and authorization.
- Enterprise/dedicated deployment may isolate an Organization physically, but it does not create a
  different product-domain model.
- Full visual administration dashboards, billing, public sharing, GIS data, layer catalogs, map
  rendering, editing, processing, field/offline behavior, and vertical modules are outside Spec 002.
