# OpenVietGIS Constitution

## Core Principles

### I. Platform-First, Module-Isolated

OpenVietGIS MUST be designed as a reusable spatial platform rather than as a single
vertical application. The Core MUST provide only capabilities that are broadly reusable
across spatial workflows. Domain-specific products such as house numbering, drainage,
planning, cadastral workflows, agriculture, or utilities MUST be implemented as modules.

Modules MAY depend on public Core contracts and SDKs. Core MUST NOT depend on,
special-case, import, or require any domain module. A clean installation without domain
modules MUST still support creating projects, working with spatial layers, editing data,
querying data, processing data, and exporting data.

Rationale: this boundary prevents a successful vertical use case from becoming hidden
platform architecture and keeps OpenVietGIS extensible across industries.

### II. Open Data and Interoperability

User data MUST remain portable. OpenVietGIS MUST provide documented paths to export
project data and derived results through open, widely supported spatial or tabular formats
and/or documented APIs. A module becoming unavailable MUST NOT make the user's
underlying data inaccessible.

Interoperability with established GIS, CAD, database, analytical, and OGC ecosystems
MUST be treated as a first-class product capability. Proprietary integration MAY be
supported, but it MUST NOT become the only practical route to access user data.

Rationale: "Open" means users retain practical control of their data, not merely that the
product uses open-source components.

### III. Tenant Isolation Is a Security Boundary

Organization ownership MUST be explicit for tenant-owned resources. Authorization MUST
be enforced on the server and, where appropriate, reinforced at the data layer. Frontend
visibility, disabled controls, or hidden routes MUST NOT be treated as authorization.

Any path that reads, edits, exports, renders, processes, synchronizes, or derives tenant
data MUST preserve tenant and resource scope. Background jobs, tile delivery, imports,
exports, modules, and administrative tooling are subject to the same rule.

Rationale: OpenVietGIS is intended for multi-tenant team use; one cross-tenant data leak
is a platform-level failure.

### IV. Spatial Correctness and Explicit CRS

Spatial reference systems MUST be explicit, traceable, and testable. Source CRS,
storage CRS, transformations, and display CRS MUST NOT be inferred silently when the
choice could change coordinates or geometry meaning.

OpenVietGIS MUST be Vietnam-first but not Vietnam-only: VN-2000 and common Vietnamese
spatial workflows MUST be first-class, while standards-based CRS support MUST remain
general enough for international datasets. Coordinate transformations that affect stored
or exported data MUST be validated with reproducible tests or control points.

Rationale: spatial software that renders correctly but stores or transforms coordinates
incorrectly is functionally unsafe.

### V. Changes Are Versioned and Auditable

Material data changes MUST be represented as explicit, attributable changes rather than
untraceable row mutations. Editing, bulk updates, imports, schema changes, approvals,
offline synchronization, and other significant mutations MUST preserve enough history to
answer who changed what, when, and from which prior state.

The platform MUST use a common change/revision concept for workflows that require
history, undo/redo, conflict detection, or audit. Audit records MUST be logically
immutable to ordinary users and MUST be distinct from diagnostic application logs.

Rationale: collaboration, offline work, recovery, accountability, and trustworthy GIS
editing all depend on traceable change history.

### VI. Capability-Driven Architecture

The platform MUST model what a source, layer, module, or tool can actually do instead of
assuming all spatial resources support the same operations. Rendering, querying,
editing, styling, exporting, analysis, offline use, and other behaviors MUST be expressed
through explicit capabilities.

User-facing commands MUST be registered independently from any single UI entry point.
Ribbon actions, command search, context menus, shortcuts, APIs, workflows, and modules
SHOULD converge on the same underlying command or service where they represent the same
operation.

Rationale: capability-driven design allows heterogeneous sources and professional
workflows to coexist without fragile type checks or duplicated behavior.

### VII. Web-Native, Engine-Agnostic

OpenVietGIS MUST exploit web-native strengths such as shared workspaces, collaboration,
centralized processing, multi-device access, and deployment flexibility. It MUST NOT
attempt to reproduce desktop software merely by copying its screens.

Replaceable technical engines MUST sit behind stable contracts at meaningful boundaries,
including map rendering, editing, tile delivery, identity, object storage, queueing, and
processing where substitution is plausible. Abstraction MUST NOT be introduced without a
real boundary or change risk.

Rationale: the product should learn from QGIS, ArcGIS, MapInfo, AutoCAD, and other
systems without becoming permanently coupled to any single implementation.

### VIII. Workflow Value Before Feature Count

OpenVietGIS MUST prioritize complete, reliable user workflows over feature parity with
existing GIS or CAD products. A capability belongs in Core only when it serves a real
workflow or is a proven reusable prerequisite for multiple modules.

The project MUST NOT add features solely because another GIS/CAD product has them.
Scope proposals MUST identify the workflow, user value, reuse case, and measurable
acceptance criteria.

Rationale: disciplined scope is required for a small team to build a coherent
professional platform instead of an incomplete collection of tools.

## Architectural Boundaries

- The product hierarchy is Organization -> Workspace -> Project, while organization
  ownership remains explicit and MUST NOT depend solely on workspace nesting.
- Workspace is primarily an organizational/grouping construct unless a specification
  explicitly defines additional security semantics.
- Layer is an abstraction over a spatial/data source, not a synonym for a database table.
- Long-lived editing UX MUST NOT require long-lived database transactions. Persistence
  MUST use short transactions with revision/change semantics and conflict detection where
  concurrent work is possible.
- A shared database MAY serve multiple organizations, but tenant isolation MUST be
  designed from the beginning. Dedicated deployments/databases MAY be used for enterprise
  isolation without creating a separate product codebase.
- Heavy processing MAY execute outside the main request process, but job state and user
  outcomes MUST remain observable and recoverable.
- Official modules and future third-party modules MAY have different trust models.
  Untrusted module code MUST NOT receive unrestricted server or tenant access by default.
- Cloud, self-hosted, and enterprise deployments MUST share the same logical product
  architecture. Provider-specific infrastructure MUST remain an adapter concern.

## Development and Quality Gates

- Every substantial capability MUST follow Spec Kit from specification through
  implementation and convergence. A feature is not complete while convergence reports a
  blocking requirement gap.
- Specifications define WHAT and WHY. Architecture Decision Records (ADRs) define
  consequential HOW decisions and their trade-offs. The Constitution MUST NOT be used to
  freeze replaceable framework or vendor choices.
- Irreversible or expensive-to-reverse architecture choices MUST have an ADR.
- Feature branches MUST be scoped and reviewable; the default branch MUST remain in a
  deployable state.
- Integration tests MUST exercise real spatial/database behavior for correctness rules
  that mocks cannot validate, including CRS transformation, tenant isolation, spatial
  operations, migrations, and change history.
- Critical user workflows MUST have end-to-end tests on real browser/runtime boundaries.
- Performance-sensitive capabilities MUST define measurable budgets or benchmark
  scenarios before optimization work is accepted as complete.
- Security-sensitive changes, data migrations, imports, destructive actions, and
  deployment changes MUST include explicit rollback/recovery considerations.
- Source code, committed documentation, and test fixtures MUST NOT contain production
  secrets or private credentials.

## Governance

This Constitution supersedes project conventions, implementation convenience, and
individual module preferences when they conflict.

Amendments require:
1. A written rationale describing the problem and impact.
2. Review of affected specs, ADRs, modules, contracts, and migration obligations.
3. Explicit approval by the project owner.
4. A semantic version change:
   - MAJOR for incompatible redefinition/removal of a governing principle.
   - MINOR for a new principle or materially expanded governance.
   - PATCH for clarification that does not change obligations.

Each implementation plan MUST include a Constitution Check. Any intentional deviation
MUST be documented with scope, rationale, risk, and a plan to remove or ratify it.

Architecture choices that can reasonably change without violating these principles MUST
live in ADRs rather than in this Constitution.

**Version**: 1.0.0 | **Ratified**: 2026-11-17 | **Last Amended**: 2026-11-17
