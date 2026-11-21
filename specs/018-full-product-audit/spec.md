# Feature Specification: Full Product Audit R001–R015

**Feature Branch**: `audit/018-full-product-audit`
**Created**: 2026-11-21
**Status**: Draft — audit gate; not release acceptance
**Input**: Product owner requests an evidence-led audit and remediation of all existing R001–R015 capabilities before declaring OpenVietGIS complete. Parent roadmap: [ROADMAP.md](../../ROADMAP.md), R001–R015; audit is cross-cutting governance, not a new capability ID. Coordinate with frontend child specs 016–017.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know the actual baseline (Priority: P1)
The owner can identify exactly which release candidate, requirements, and evidence are being audited, rather than rely on a static 15/15 indicator.
**Why this priority**: Conflicting Windows/main and VPS branches can cause false acceptance and duplicate work.
**Independent Test**: Compare immutable candidate identity, prior approved requirements, roadmap, and evidence register.
**Acceptance Scenarios**:
1. Given different branches, when the audit starts, then each candidate and scope is recorded separately; no dirty work or main is overwritten.
2. Given missing detailed specs or stale status, when a capability is inventoried, then its status is unverified or partial, not accepted.

### User Story 2 - Prove the core GIS workflow (Priority: P1)
A GIS user imports, inspects, saves and reopens a project, exports data, and independently verifies geometry, attributes and CRS.
**Why this priority**: M1 is prerequisite to useful team workflows.
**Independent Test**: Use an isolated synthetic project with point, line and polygon fixtures and independent GIS round-trip checks.
**Acceptance Scenarios**:
1. Given an authorized user and valid files, when importing, viewing, selecting and exporting, then recorded artifacts match accepted format/CRS tolerances.
2. Given malformed input, wrong tenant, revoked permission or interrupted job, then nothing leaks or publishes partially.

### User Story 3 - Prove workbench capabilities (Priority: P1)
A user edits geometries and attributes, queries data, processes analytical results and exports a map without hand-crafting API requests.
**Why this priority**: Visible workflow completion matters more than backend route existence.
**Independent Test**: Complete M2 against an isolated project and independently compare output.
**Acceptance Scenarios**:
1. Given a feature revision, when using supported graphical and attribute controls, then a persisted change is attributable, conflicts are rejected and revert is demonstrable.
2. Given known geometry and predicates, when running supported queries and algorithms, then counts and geometry match independent oracle and resulting layer is accessible.
3. Given a saved map layout, when exporting, then actual PNG/PDF opens and layout is checked for content, labels, legend and CRS/scale.

### User Story 4 - Prove advanced and team workflows (Priority: P2)
A user evaluates each declared external data, collaboration, CAD, field, module and operations capability, with unsupported functions explicit.
**Why this priority**: Prevents metadata-only systems from masquerading as production workflows.
**Independent Test**: Run separate benign external service fixtures, two-user, DXF, offline/reconnect, module and isolated restore scenarios.
**Acceptance Scenarios**:
1. Given a supported protocol, when connecting and reading a controlled source, then actual data renders/queries; a saved connection record alone is insufficient.
2. Given two authorized users, when conflicting edits and review occur, then accepted revision and permission are enforced.
3. Given supported CAD/field/module workflows, when exchanging or synchronizing artifacts, then the real artifacts and data prove the outcome; unsupported DWG, offline UI or module behavior must not be advertised.
4. Given a release profile, when failure, backup and restore are exercised on disposable data, then recovery and actual capability availability are evidenced, not inferred from a static list.

### User Story 5 - Close gaps and sign off honestly (Priority: P1)
The owner views a prioritized gap backlog and trustworthy acceptance decision for each roadmap item.
**Why this priority**: Prevents claiming a whole feature based on a smoke test.
**Independent Test**: Review the traceability register and reproducible evidence against the frozen candidate.
**Acceptance Scenarios**:
1. Given a gap, then it has a requirement reference, severity, reproduction, owner, remediation child spec and retest criterion.
2. Given a final candidate, then every declared accepted requirement has real evidence on that exact revision; remaining unsupported/deferred items are visible and acceptance remains open where required.

### Edge Cases
- Divergent branches and concurrent frontend work: isolate audit, do not merge or deploy automatically.
- Static capability flags, placeholder UI, fake success, skipped tests, missing logs or stale results: never count as verified evidence.
- External provider unavailable, credentials absent, manual observation pending: record blocked, use safe controlled fixtures where appropriate.
- Unsupported formats/CRS, invalid topology, permission revocation, concurrent save, job interruption, offline conflict: record negative outcome and preservation.
- Production data, credentials and current user sessions are out of scope for destructive tests.

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: Audit MUST pin exact candidate commit, tree, environment and previous accepted baseline, preserving existing dirty work.
- **FR-002**: Audit MUST inventory all R001–R015 requirements using the original approved specs/decision register, distinguishing approved, draft, missing and out-of-scope requirements; never weaken requirements to match code.
- **FR-003**: Every requirement MUST have status, concrete evidence references and applicable interface, persistence, negative and independent-output verification.
- **FR-004**: M1 MUST prove real authentication, tenant isolation, file import, explicit CRS, map interaction, save/reopen and export round-trip.
- **FR-005**: M2 MUST prove real graphical editing and validation, revision/revert/conflict, query correctness, processing outputs and usable cartographic export.
- **FR-006**: External-source tests MUST distinguish register/probe/read/render/query; only actually tested supported operations may be declared available.
- **FR-007**: CAD MUST verify DXF input/output and declared precision/geometry limitations; no unsupported format claim.
- **FR-008**: Field offline MUST verify local work without network, reconnect and conflict/revocation behavior where declared; a downloadable package or API alone is partial.
- **FR-009**: Team collaboration MUST exercise two independent authorized user contexts, history/review and stale/conflicting changes.
- **FR-010**: Module extension and operations MUST prove independent modules, capability/entitlement enforcement where declared, health checks and isolated recovery.
- **FR-011**: Evidence MUST use isolated synthetic data, record exact versions, commands, independent expected outcomes and redacted logs; no production credentials or destructive test activity.
- **FR-012**: Gaps MUST be classified critical/high/medium/low, with reproduction and explicit retest; remediation MUST use scoped child Spec Kit work after required decisions.
- **FR-013**: Final roadmap status MUST distinguish code present, automated verified, manual verified, partial, blocked, unsupported and accepted; static flags are not an acceptance source.
- **FR-014**: Promotion or release MUST require exact-candidate full validation, independent review, convergence, required manual gates and owner-approved release scope; audit alone does not authorize production deployment.
- **FR-015**: Auditors MUST distinguish R016/R017 UX work from the frozen R001–R015 baseline and retest integration without overwriting active work.

### Key Entities
- Candidate: frozen source and environment identity.
- RequirementEvidence: roadmap requirement, declared scope, test outcome and evidence pointers.
- Gap: requirement-linked defect and severity, reproduction, planned child scope and retest.
- AcceptanceDecision: candidate-specific gate decision with review and manual evidence.

## Success Criteria *(mandatory)*
### Measurable Outcomes
- **SC-001**: 15/15 roadmap groups inventoried; all known approved requirements mapped or explicitly marked missing/blocked.
- **SC-002**: 100% accepted requirements have reproducible evidence; zero accepted rows based solely on a static flag or route existence.
- **SC-003**: M1, M2 and M3 scenarios each yield recorded pass/fail/blocked, with independent output checks and tenant negative cases.
- **SC-004**: All critical/high gaps recorded with reproduction and retest; no unresolved critical/high blocker in an accepted release scope.
- **SC-005**: Independent review and convergence on exact candidate; required human observations completed before external release, or explicitly blocked with no external acceptance.
- **SC-006**: Zero production mutation, secret exposure or unapproved promotion during audit.

## Assumptions
- Existing VPS branch is the audit target, not verified main; freeze its committed revision.
- Use synthetic datasets and dedicated disposable test database/artifact storage. No production tests or live provider credentials needed.
- Audit does not expand initial slices to full QGIS/AutoCAD parity, change accepted scope, or automatically deploy.
- User-visible frontend flow is required wherever declared; feature requests beyond accepted scope need child specs and owner decisions.
