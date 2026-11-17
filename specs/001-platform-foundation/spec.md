# Feature Specification: Platform Foundation

**Feature Branch**: `001-platform-foundation`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: "Establish the OpenVietGIS platform foundation before building GIS features: a clean architecture runway, explicit dependency boundaries, reproducible development setup, architecture decision records, baseline quality gates, and one minimal end-to-end vertical slice proving the product layers work together. Do not implement map, full identity, house numbering, or domain-specific GIS capability in this feature."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a Consistent Development Environment (Priority: P1)

A contributor can obtain the repository, follow the documented setup, and start the minimum
OpenVietGIS development environment without needing undocumented machine-specific knowledge.

**Why this priority**: Every later feature depends on contributors being able to reproduce the same
foundation. If setup is inconsistent, architecture and test results cannot be trusted.

**Independent Test**: A contributor on a clean supported development environment follows only the
repository documentation, starts the foundation, and reaches the baseline product shell and its
foundation health check successfully.

**Acceptance Scenarios**:

1. **Given** a clean supported development environment, **When** a contributor follows the documented
   bootstrap procedure, **Then** all required foundation components start without manual source edits.
2. **Given** the foundation is running, **When** the contributor opens the product shell,
   **Then** the shell reports that the core application path is available and can reach its persisted
   foundation data.
3. **Given** a required local dependency is unavailable or misconfigured, **When** startup is
   attempted, **Then** the contributor receives a clear failure identifying the missing prerequisite
   instead of a partially working environment.

---

### User Story 2 - Prove One Complete Vertical Slice (Priority: P1)

A product maintainer can demonstrate one intentionally small, non-GIS vertical slice that crosses
the product shell, application boundary, domain behavior, persistence boundary, and back again,
without bypassing the architectural layers.

**Why this priority**: The foundation is valuable only if the selected boundaries work together in
practice. A vertical slice exposes integration mistakes before real GIS features multiply them.

**Independent Test**: Create a minimal foundation-owned record through the product shell, confirm it
is persisted, reload the product, and confirm the same record is returned through the supported
application path.

**Acceptance Scenarios**:

1. **Given** the foundation is running with empty sample data, **When** a maintainer creates a
   foundation-owned sample record through the supported product flow, **Then** the record is stored
   and returned with a stable identifier.
2. **Given** a sample record was created, **When** the application is restarted and the record is
   requested again, **Then** the same persisted value is returned.
3. **Given** the vertical slice implementation, **When** it is reviewed, **Then** it does not require
   any domain-specific module such as house numbering, drainage, or planning.

---

### User Story 3 - Preserve Architectural Boundaries (Priority: P1)

A contributor adding code can determine where it belongs and receives an automated failure when a
known forbidden dependency direction is introduced.

**Why this priority**: OpenVietGIS is intended to become a platform. Boundary drift at the beginning
would recreate the coupling problems the new repository was created to avoid.

**Independent Test**: Introduce a controlled test violation in a fixture or test scenario and verify
that the architecture quality gate rejects it while valid dependencies continue to pass.

**Acceptance Scenarios**:

1. **Given** the documented product boundaries, **When** a contributor checks the architecture guide,
   **Then** the ownership and allowed dependency direction of applications, platform packages,
   services, and domain modules are unambiguous.
2. **Given** a forbidden dependency from Core into a vertical domain module, **When** quality checks
   run, **Then** the violation is detected before the change can be accepted.
3. **Given** a vertical module using a published platform contract, **When** quality checks run,
   **Then** the valid dependency is accepted.

---

### User Story 4 - Understand and Change Architecture Deliberately (Priority: P2)

A maintainer can find the project's governing principles and consequential architecture decisions,
understand why each decision exists, and identify the process for replacing a decision later.

**Why this priority**: The platform is expected to evolve for years. Decisions must remain explicit
without turning replaceable technology into permanent constitutional law.

**Independent Test**: A reviewer unfamiliar with the repository can locate the governance document
and architecture decisions and correctly answer why the repository is a platform, why modules
cannot be imported by Core, and where a replaceable technical decision is recorded.

**Acceptance Scenarios**:

1. **Given** a new maintainer, **When** they review project documentation, **Then** they can distinguish
   non-negotiable constitutional principles from replaceable architecture decisions.
2. **Given** a proposed replacement for an accepted technical choice, **When** the maintainer follows
   the documented decision process, **Then** the old decision can be superseded without modifying
   unrelated constitutional principles.

---

### User Story 5 - Run Baseline Quality Gates Before Feature Work (Priority: P2)

A contributor can run one documented quality workflow that validates formatting or static quality,
automated tests, architectural boundaries, and the minimal vertical slice before further platform
features are accepted.

**Why this priority**: A deployable default branch requires a known minimum quality bar from the
first feature onward.

**Independent Test**: Execute the documented baseline validation on an unchanged checkout and see
all required checks pass; introduce one known failing condition and see the workflow fail.

**Acceptance Scenarios**:

1. **Given** a valid foundation checkout, **When** baseline validation runs, **Then** all mandatory
   checks complete successfully.
2. **Given** a failing test or forbidden architecture dependency, **When** baseline validation runs,
   **Then** the workflow fails and identifies the failing category.
3. **Given** a change that only updates documentation, **When** validation runs, **Then** the workflow
   remains deterministic and does not require production credentials.

### Edge Cases

- A contributor already has conflicting services or ports in use when starting the local foundation.
- A required configuration value is omitted, empty, or uses a production-only secret locally.
- The persisted foundation data exists from an older local schema or incompatible development run.
- A quality check is executed from a subdirectory instead of the repository root.
- A domain module is absent entirely; the Core foundation must still start and pass its baseline checks.
- A provider-specific adapter is unavailable; the failure must not silently change platform behavior.
- The vertical-slice sample data is recreated or the environment is reset; reset behavior must be
  documented and deterministic.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST provide a documented, reproducible bootstrap path for the minimum
  OpenVietGIS development foundation.
- **FR-002**: The foundation MUST expose a product shell that can confirm the supported application
  path is available without requiring any vertical domain module.
- **FR-003**: The foundation MUST include one minimal persisted vertical slice that crosses the
  supported user interface, application, domain, and persistence boundaries.
- **FR-004**: The vertical slice MUST use a foundation-owned sample concept and MUST NOT prematurely
  define final Organization, Workspace, Project, Layer, identity, or GIS business semantics that
  belong to later features.
- **FR-005**: Restarting the application MUST preserve and return data created through the vertical
  slice until the documented development reset procedure is invoked.
- **FR-006**: The repository MUST document the top-level architectural boundaries and allowed
  dependency direction between applications, platform packages, specialized services, and domain
  modules.
- **FR-007**: Core platform code MUST be able to build and run with all vertical domain modules
  absent.
- **FR-008**: Core platform code MUST NOT depend on or special-case any vertical domain module.
- **FR-009**: The foundation MUST provide an automated check for at least the critical dependency
  rule that prohibits Core from depending on vertical modules.
- **FR-010**: The repository MUST distinguish governing project principles from replaceable
  architecture decisions and provide a discoverable record of accepted foundational decisions.
- **FR-011**: Consequential architecture decisions MUST record context, decision, status, date, and
  consequences so that a later decision can explicitly supersede them.
- **FR-012**: The foundation MUST define a single documented baseline validation workflow that covers
  static quality checks, automated tests, architectural boundary checks, and the vertical-slice
  integration path.
- **FR-013**: Baseline validation MUST run without production credentials or production data.
- **FR-014**: Local development configuration MUST fail clearly when a required prerequisite is
  missing rather than continuing in an unknown partial state.
- **FR-015**: Development secrets and local private configuration MUST be excluded from versioned
  source control.
- **FR-016**: The foundation MUST provide a deterministic way to initialize and reset development
  data without destructive access to any non-development environment.
- **FR-017**: The default branch MUST remain suitable for deployment after accepted foundation work;
  incomplete experimental work MUST remain isolated from it.
- **FR-018**: The feature MUST NOT implement map rendering, GIS editing, production authentication,
  tenant billing, offline field workflows, spatial processing, or the House Numbering module.
- **FR-019**: The feature MUST leave explicit extension points or documented future boundaries for
  later Identity/Tenancy, Spatial Catalog, Map, Editing, Processing, Field, and Module features
  without requiring those capabilities to be implemented now.
- **FR-020**: All foundation documentation and sample behavior MUST use product-neutral terminology
  and MUST NOT make House Numbering or Bình Hưng a Core concept.

### Key Entities

- **Foundation Sample Record**: A deliberately minimal persisted record used only to prove the
  end-to-end application path. It carries a stable identifier and a small user-visible value but
  does not model a future business entity.
- **Architecture Decision**: A versioned record of a consequential technical choice, including its
  context, status, decision, date, and consequences.
- **Architecture Boundary**: A documented ownership/dependency rule between major product areas that
  can be validated by review or automated checks.
- **Foundation Validation Result**: The observable outcome of running the baseline quality workflow,
  showing whether each mandatory category passed or failed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A contributor unfamiliar with the repository can follow the documented bootstrap on a
  clean supported environment and reach the working foundation in no more than 20 minutes,
  excluding dependency download time.
- **SC-002**: 100% of documented mandatory foundation checks pass on an unchanged accepted checkout.
- **SC-003**: The minimal vertical slice can create, persist, restart, and retrieve its sample record
  successfully in 10 consecutive automated integration runs.
- **SC-004**: A controlled forbidden Core-to-domain-module dependency is rejected by the architecture
  quality gate in 100% of validation runs.
- **SC-005**: Removing all vertical domain modules does not prevent the Core foundation from starting
  or passing its baseline validation.
- **SC-006**: A reviewer unfamiliar with the repository can identify the location and purpose of the
  Constitution, architecture decisions, dependency rules, and baseline validation procedure in
  under 10 minutes using repository documentation only.
- **SC-007**: No baseline test, bootstrap step, or validation workflow requires production secrets,
  production data, or access to a production environment.
- **SC-008**: The feature introduces zero end-user GIS tools and zero House Numbering-specific Core
  concepts, keeping the scope limited to the architecture runway.

## Assumptions

- The purpose of this feature is to establish a trustworthy foundation, not to deliver user-facing
  GIS capability.
- Organization, Workspace, Project, identity, tenancy semantics, spatial catalog, map rendering,
  editing, processing, collaboration, field/offline behavior, and module SDK stabilization are
  intentionally deferred to later specifications.
- The vertical slice is disposable proof of architecture and may be removed or replaced once real
  product entities arrive.
- Development setup targets the project's documented supported developer environment; broad
  production deployment compatibility is handled by later operations specifications.
- Architecture decisions may be superseded through new ADRs without amending the Constitution when
  the governing principles remain unchanged.
