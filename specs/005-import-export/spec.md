# Feature Specification: Import and Export

**Feature Branch**: `005-import-export`

**Created**: 2026-11-18

**Status**: Draft — scope approved; dependency and interoperability evidence gates open

**Input**: User-approved R005 first slice: bring GeoPackage, GeoJSON and ZIP Shapefile vector data into an authorized Project; validate all data before publishing a new project-owned source and Layer; preserve immutable input and attribution; export a specific revision to an interoperable file with explicit CRS and a comparison report. No append or overwrite. **Parent roadmap: [ROADMAP.md, entry R005](../../ROADMAP.md#r005)**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import a reference vector layer safely (Priority: P1)

An authorized GIS user uploads a supported dataset, identifies the intended layer and explicit source CRS/encoding, reviews schema, count, geometry and conversion information, then confirms import. A successful job creates one new source and Layer in the selected Project and makes it available for normal map viewing and inspection.

**Why this priority**: Bringing existing GIS data into a real Project is the essential M1 workflow.

**Independent Test**: Import a valid GeoPackage vector fixture into a fresh authorized Project, inspect all expected feature identities, attributes and CRS in the catalog and open the Layer in the map.

**Acceptance Scenarios**:

1. **Given** an authorized Project and supported GeoPackage with known CRS, **When** the user reviews and confirms a selected vector layer, **Then** the resulting source and Layer are ready together with expected count, schema, geometry and traceable imported revision.
2. **Given** a GeoPackage containing multiple members, **When** the dataset is inspected, **Then** the user can explicitly select an eligible vector member; no unrelated member is silently imported.
3. **Given** a supported RFC 7946 GeoJSON or ZIP Shapefile dataset, **When** the user completes the same flow, **Then** the resulting records satisfy the accepted format/CRS profile and all conversions are shown.
4. **Given** an existing Layer or source with the same display name, **When** the user confirms a new import, **Then** the previous source, Layer and revision remain unchanged and the new identity is distinct.

---

### User Story 2 - Discover errors before committing data (Priority: P1)

A user inspects a file containing unknown CRS, ambiguous text encoding, malformed geometry, unsupported fields or mismatched component files. The user sees an actionable report and cannot accidentally publish a partial or mislocated dataset.

**Why this priority**: Invisible loss or incorrect CRS is unacceptable in professional GIS.

**Independent Test**: Submit one invalid fixture and one supported fixture with an explicitly identified conversion; compare preview and final validation behavior and confirm no partial source is exposed.

**Acceptance Scenarios**:

1. **Given** an invalid geometry, unreadable record or unsupported type, **When** validation completes, **Then** the report identifies the failure and the entire publication is blocked; no ready partial Layer or partial record set is created.
2. **Given** a missing Shapefile CRS or uncertain encoding, **When** inspection completes, **Then** the user is required to resolve the ambiguity using an accepted profile before confirming; a guessed CRS or encoding is not silently applied.
3. **Given** a proposed conversion within the supported format matrix, **When** the user previews it, **Then** the affected field/geometry/coordinate semantics and known differences are shown; an unsupported unapproved loss blocks publication.
4. **Given** a hostile archive or file exceeding an advertised resource limit, **When** it is submitted or expanded, **Then** processing stops safely and shows a non-sensitive reason.

---

### User Story 3 - Export a known revision for interoperable use (Priority: P1)

An authorized user chooses a supported Layer, a complete source revision, output format and explicit compatible output CRS, previews any representational differences, and obtains an immutable export artifact that can be opened independently in another GIS application.

**Why this priority**: Data portability is a product obligation, not an optional convenience.

**Independent Test**: From an authorized pre-established fixture Layer, export to GeoPackage, independently reopen it, and compare count, field values, nulls, geometry and CRS with the declared source revision.

**Acceptance Scenarios**:

1. **Given** an unchanged authorized source at a specific revision, **When** the user chooses GeoPackage and a compatible output CRS, **Then** a successful export represents that revision and a separate comparison report identifies the source revision, format, CRS and result counts.
2. **Given** an authorized source with fields not faithfully representable in Shapefile or GeoJSON, **When** the user attempts export, **Then** the differences are explicit; export is blocked unless the accepted profile permits and the user approves the exact represented loss.
3. **Given** a source revision changes after the output request, **When** that request executes, **Then** the output either represents its originally requested revision consistently or fails as stale; no silent substitution with the new revision is allowed.
4. **Given** an actor no longer has the appropriate access, **When** they request or download an artifact, **Then** access is denied without protected source or artifact details being disclosed.

---

### User Story 4 - Track and safely recover interrupted jobs (Priority: P2)

An authorized user sees durable progress, final state, validation results and permitted outputs for their import/export jobs, cancels work before publication where safe, and recovers failed or interrupted work without duplicate sources or artifacts.

**Why this priority**: Spatial data jobs must not rely on an uninterrupted web session.

**Independent Test**: Interrupt a staged import before atomic publication, restart the application, then retry the same logical request; inspect the job and catalog for a single outcome.

**Acceptance Scenarios**:

1. **Given** a running import or export, **When** the user closes and reopens the application, **Then** the authorized job state remains inspectable and a successful result is not recreated.
2. **Given** a cancel request is accepted before publication, **When** processing stops, **Then** no ready source or downloadable result is published and temporary material is cleaned up or marked for bounded recovery.
3. **Given** publication already succeeded, **When** the user requests cancellation or repeats the same job confirmation, **Then** the original successful outcome remains intact and is not duplicated or silently reversed.
4. **Given** a job fails or loses its required authority, **When** recovery occurs, **Then** the visible state records the interruption/denial, staged partial output remains unavailable, and only a declared recoverable failure permits retry with fresh authorization. A denied outcome is terminal for that logical job.

---

### User Story 5 - Verify provenance and M1 interoperability (Priority: P2)

A Project owner can inspect who imported a source, what file was supplied, which CRS was declared and verified, when initial revision was created, and which revision produced an output, without exposing internal storage or another tenant's information.

**Why this priority**: Reliable migration, validation and later editing depend on identifying exactly what changed and why.

**Independent Test**: Import a reference dataset, view/select and save/reopen the Project map, export the same revision, and compare it independently against the source and documented tolerance.

**Acceptance Scenarios**:

1. **Given** a successful import, **When** an authorized user inspects provenance, **Then** the original immutable input identity/checksum, actor, selected layer/member, format, coordinate conventions and initial change evidence are traceable.
2. **Given** an authorized export generated from a particular source revision, **When** its provenance is inspected, **Then** output format, CRS transformation, conversion report and immutable artifact checksum identify the exact outcome.
3. **Given** an interrupted or denied import attempt, **When** the user inspects authorized history, **Then** it is distinguishable from a successful material change without pretending that partially validated data was accepted.

### Edge Cases

- Empty datasets, null geometry, multipart geometry, mixed families, dimensionality and geometry collections outside the supported profile.
- Corrupt archive members, path traversal, duplicate component names, archive expansion bombs, misleading file extension, mismatched Shapefile component sets, invalid UTF-8 or ambiguous legacy text encoding.
- Multi-layer GeoPackage selection; encrypted or unreadable data; unsupported types, duplicate field names, missing or invalid CRS and ambiguous axis convention.
- A coordinate transformation cannot be verified, is outside its applicable region, or would require unsupported precision/loss.
- Numeric overflow, long names and strings, Unicode, dates, null versus empty/zero, field name collision after format mapping, invalid geometry, no applicable output CRS.
- Import preview becomes stale because file identity, selected member, mapping or approved profile changed; repeated submit/confirm, concurrent cancel and publication, interruption immediately before or after publication.
- Source revision advances mid-export; downloadable artifact expires or is missing; attempted job retry after revocation or Project retirement.
- Wrong-tenant or wrong-Project identifiers, including same-Organization cross-Project references; private file paths/credentials in input or errors.

## Requirements *(mandatory)*

### Functional Requirements

#### Supported format and validation

- **FR-001**: System MUST support vector import and export for the accepted first-slice format profiles: GeoPackage, RFC 7946 GeoJSON and ZIP-packaged Shapefile. The published matrix MUST distinguish per-format read/write support, eligible geometry families/dimensions, attributes, null semantics, CRS operations, maximum sizes and known representational limitations.
- **FR-002**: GeoPackage MUST be the preferred interoperable output when source fields and geometry fall within its supported lossless profile. Dataset inspection MUST expose eligible vector members and require explicit selection where there is more than one; initial publication is one selected member per logical import.
- **FR-003**: GeoJSON MUST use the explicit RFC 7946 coordinate convention; unsupported legacy or contradictory CRS declarations MUST be rejected or require a separately supported explicit input profile, not silently accepted as WGS84.
- **FR-004**: Shapefile import MUST require a coherent selected set of supported archive components and explicit verified CRS and text-encoding semantics. A missing authoritative CRS/encoding declaration MUST be resolved using an accepted attributable choice or rejected.
- **FR-005**: Format detection MUST validate actual supported content and structure, rather than trust file names or extensions. Unsupported, malformed, or ambiguous input MUST produce actionable, non-sensitive errors.
- **FR-006**: Inspection MUST present eligible data members, supported typed field schema, geometry family/dimensions, record count status, extent status, source CRS/axis order, declared encoding, intended target CRS, validation findings and any proposed conversion before confirmation.
- **FR-007**: The system MUST validate all selected records before ready publication, including supported field values, geometry family/dimensions, finite coordinates, applicable bounds, geometry validity and declared schema. A preview sample MUST be identified as such and MUST NOT substitute for this full validation.
- **FR-008**: Unsupported records or data-semantic loss MUST NOT be silently discarded, repaired, truncated, misinterpreted or coerced. Non-representable input blocks publication unless the accepted profile specifies a meaning-preserving conversion. Fixing invalid source data occurs outside this import or a later explicit editing workflow.
- **FR-009**: Source, stored, display and exported coordinate conventions MUST remain distinguishable. Each coordinate-changing operation MUST use an accepted R003-compatible profile with documented applicable region, units, axis order, attributable operation and independently verified tolerance. Unknown or unsupported transformations MUST fail explicitly.
- **FR-010**: Every accepted preview and publication MUST be bound to the exact immutable input identity/checksum, selected member, format/CRS/encoding interpretation and transformation profile. Changed inputs or options MUST invalidate the old confirmation.
- **FR-011**: File processing MUST enforce documented limits on input size, archive expansion, entry count, processing time, memory and supported data complexity, safely reject traversal and other malformed content, and avoid executing bundled scripts or resolving external references.

#### New-source import and provenance

- **FR-012**: Import MUST require explicit selected Organization and Project and current import authority in that exact scope at submission, validation access, confirmation, execution and publication.
- **FR-013**: Only a successful confirmed import MAY create a ready new DataSource, a corresponding logical Layer, feature data, initial revision/change evidence and provenance. All of these MUST become consistently available as one material publication or remain unavailable on failure.
- **FR-014**: Import MUST NOT append to, overwrite, retire, mutate or reuse the identities of an existing source or its Layer. Re-import of a file as an intentional new action produces a distinct new source; a retry of the same logical action does not.
- **FR-015**: A successful source MUST preserve logical catalog identity, typed schema with stable field identities and an identifiable schema revision, supported geometry, explicit CRS, stable feature identities, count, extent and source-content revision consistent with the accepted R003 contracts; neither field label nor Layer display metadata substitutes for an identity. The new Layer MUST expose only actually supported capabilities.
- **FR-016**: The original selected upload MUST be preserved as an immutable SourceAsset with integrity checksum, selected member and owner links; the successful source revision MUST reference it, not claim a transformed record set is the original file.
- **FR-017**: The initial imported source-content revision/change unit MUST record attributable actor, time, operation, affected source and Layer identifiers, schema revision, original checksum, validation/conversion outcome and actual imported representation. Catalog metadata, source-content and shared Map configuration revision semantics MUST remain distinguishable; a presentation-only Layer change MUST NOT be represented as a new source-content state. Ordinary actors MUST NOT be able to alter this historical evidence.
- **FR-018**: Successful import MUST make the new Layer discoverable for authorized normal R004 add/view/select/inspect workflows. Adding a Layer reference to a shared Map MUST obey R004 authority and shared Save semantics; it MUST NOT silently mutate the existing Map configuration.
- **FR-019**: Failed validation, denied access, interruption before successful publication and accepted pre-publication cancellation MUST leave no visible ready source, orphan Layer reference, partial feature set or successful change record. A failure record may exist for recovery and audit, distinct from material success.

#### Fixed-revision export

- **FR-020**: Authorized users MUST be able to export the complete supported readable source behind a Layer at a specifically identified source-content revision and chosen supported output format/CRS, independent of incidental map viewport, style or selection. Selection/query-subset export is not a capability of this first slice and MUST remain unavailable unless separately accepted in scope and contract.
- **FR-021**: Before confirmation, export MUST present the selected revision, output profile, available expected count and expected semantic differences. Non-representable values MUST block output unless the accepted matrix expressly permits the conversion and the user confirms the disclosed difference.
- **FR-022**: An export MUST preserve the requested source-content/schema revision consistently across all records. If the requested revision cannot be provided a stale result MUST be reported; the system MUST NOT silently export a newer or mixed revision. A revision reference alone MUST NOT promise historical snapshot readability beyond the accepted retention/reconstruction contract.
- **FR-023**: Successful export MUST produce an immutable, integrity-checkable DerivedArtifact and a comparison report identifying source/Layer/revision, actor, format, coordinate convention, verified transformation operation, mapping/loss decisions, record counts, and supported schema/geometry/null comparison outcomes.
- **FR-024**: Result reports MUST state when comparison is not complete or a tolerance is not proven; they MUST NOT claim independent verification or lossless fidelity without corresponding evidence. Independent fixture verification remains mandatory before acceptance.
- **FR-025**: Export MUST NOT change source records, source revision, Layer identity or saved Map configuration.
- **FR-026**: Output access MUST require current scope, actor authority and artifact association at request, execution, publication and every protected retrieval. A download handle MUST be bounded and recheck current authority at protected retrieval; it MUST NOT provide usable enduring access after applicable authority or lifetime is lost, including by redemption of an otherwise unrevocable direct object-store link.
- **FR-027**: An expired, missing, corrupted or otherwise unavailable artifact MUST be distinguishable from a ready deliverable, and recovery MUST use an explicitly authorized re-export of an identified revision rather than substitute another result.

#### Durable jobs, lifecycle and recovery

- **FR-028**: Each import/export logical request MUST have a durable, inspectable identity, immutable request fingerprint, current state and, where attempts occur, distinguishable attempt history. The common job contract MUST distinguish accepted/queued, active, validation/confirmation phases where applicable, cancellation requested, successful, failed, denied and cancelled outcomes. Progress and known final outputs MUST be visible only to authorized actors. Terminal outcome, retry eligibility and permitted transitions MUST be consistent for later job consumers, including R008. A failed attempt MAY enter a recoverable state with an explicit retry transition; unrecoverable failure and denied outcomes MUST remain terminal for that logical job.
- **FR-029**: Retries, restarts and duplicate confirmations of the same scoped logical operation MUST reconcile to at most one successful material publication. A request fingerprint MUST cover the operation, exact immutable input/revision, interpretation and options; conflicting reuse of an identity MUST be rejected. Authorized bounded retry of a declared recoverable failure MUST reuse the logical identity and fingerprint but record a distinct attempt; changed inputs/options or a new action require a new logical identity. Replay MUST NOT bypass current authorization.
- **FR-030**: Users MUST be able to request cancellation before successful publication. The cancellation-versus-publication boundary MUST decide one consistent terminal outcome: cancellation accepted before publication prevents success; a completed publication remains successful and requires a separate authorized lifecycle action to retire or remove it. An effective denial/revocation before the authorized publication boundary likewise prevents output; if publication already won, its historical success is retained but protected access is governed by current authority.
- **FR-031**: Temporary staged data and failed output MUST be inaccessible as ordinary catalog sources or downloadable results. Ready result references, material provenance and terminal success MUST become consistently visible only after the required immutable objects and their integrity are verified and recoverable. A documented, bounded cleanup/reconciliation policy MUST reconcile object/metadata interruptions, cancellation, expiry and failed attempts without removing required immutable provenance or existing successful data.
- **FR-032**: Every background action MUST re-evaluate current actor, Organization, Project, relevant permission, resource capability and lifecycle; a previously valid request MUST NOT constitute enduring authority. Machine-actor reauthorization MUST resolve an accepted non-secret credential identity and current ceiling/revocation semantics without persisting raw credentials. Publication MUST enforce current authority at its success boundary and protected status/result/artifact access MUST recheck it.
- **FR-033**: Protected job status, validation details, artifacts, source or Layer identifiers MUST NOT be exposed across unauthorized Organization or Project scopes, including direct access and cached results. Shared storage addresses, internal paths, secrets and protected data from another scope MUST NOT appear in errors or reports.
- **FR-034**: The system MUST preserve successful publications and required attributable change/provenance evidence after interruption/restart, and make non-success outcomes safely recoverable or explicitly terminal according to documented limits.
- **FR-035**: Import/export MUST provide consistent capability-aware commands and authorization across supported entry points in accordance with accepted R004 semantics; no UI-only restriction grants or bypasses permission.
- **FR-036**: The feature MUST provide a documented end-to-end export/restore/interoperability workflow for supported user data without relying on a domain module or proprietary-only representation. The job and artifact semantics MUST be available for later R008 processing without implying that algorithms are delivered here.

### Key Entities

- **Import Request**: An attributable proposed action scoped to one Organization, Project, immutable input, selected vector member and confirmed interpretation.
- **SourceAsset**: Immutable original upload identity, integrity checksum, ownership, format and known provenance, distinct from the derived source and its feature data.
- **Inspection / Validation Report**: Input structure, member, schema, geometry, count, CRS/encoding and conversion findings, with sample/full distinction and actionable errors.
- **DataSource and Layer**: Separate catalog identities and capabilities linked to the Project and initial imported revision, not physical storage identities.
- **Source Revision / Initial Import Change Unit**: Attributable initial material state and change evidence linked to original input and validation results.
- **Export Request**: Explicit scoped authorization, source/Layer and fixed revision, output format, output CRS and approved mapping/loss decisions.
- **DerivedArtifact and Export Report**: Immutable output, integrity checksum, authorization scope, lifetime and documented comparison/provenance.
- **Job**: Durable logical operation identity, actor reference, scope, state, progress, validation/error result, and references to publication outcomes, with idempotency and recovery semantics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across 100% of accepted read/write format matrix fixture cases, an authorized user can import one selected member, inspect the resulting catalog metadata and feature contents, and export a supported output; each successful qualifying lossless round-trip preserves expected count, typed values including null distinctions, geometry and declared CRS within the independently agreed tolerance. Explicitly permitted lossy fixtures instead match the approved mapping/report exactly.
- **SC-002**: In 100% of invalid or unapproved unsupported/loss/CRS/encoding fixtures, validation or export confirmation prevents unsafe publication. No unreported loss, invalid ready Layer or silently guessed coordinate transformation occurs.
- **SC-003**: 100% of independent control-point checks for each coordinate-changing import/export operation meet the accepted profile's documented tolerance and applicability; negative fixtures fail or show explicit unsupported status.
- **SC-004**: In all tested successful imports, the original checksum, actor, selected member, source identity, Layer and initial revision/change evidence are consistent and traceable. Exports always identify the requested revision or fail explicitly.
- **SC-005**: 100% of agreed unauthorized cross-Organization, cross-Project, lifecycle, revoked-access, cached/direct-read, job and artifact tests disclose no protected data and produce no unauthorized result, including authority lost before the publication boundary and before each protected download redemption; a previously issued handle cannot bypass revocation.
- **SC-006**: Across all agreed interruption, object-store/metadata partial-failure, cancel/publication race, retry, same-identity conflicting replay, duplicate-confirm and restart trials, previous successful data remains intact, at most one successful outcome exists per logical request, and unpublished partial input/output is never exposed as a ready artifact or source. Attempt history and terminal outcome agree with the actual committed result.
- **SC-007**: On a documented reference-size 10,000-feature dataset profile, proposed initial p95 bounds are 60 seconds for confirmed import and 30 seconds for confirmed export (excluding file transfer and queue wait). Record file sizes, geometry complexity, CRS, environment, accepted formats and limits; run at least 30 trials per chosen profile/configuration after warm-up. Reference data and bounds are proposal gates to settle before planning, not performance guarantees or measured results.
- **SC-008**: In five observed first-time GIS-capable user attempts, at least four independently follow authorized upload/preview/confirm, add/view/select, save/reopen and download/export on the agreed fixture and can locate the CRS/provenance report; record task failures and timing as evidence.
- **SC-009**: The M1 end-to-end fixture demonstrates successful import, map selection and attribute inspection, save/reopen, fixed-revision output and independent comparison, with zero required domain modules or unapproved third-party access.

## Assumptions

- **Planning gate:** R005 depends on accepted and converged R003 spatial catalog/CRS/read/capability contracts and R004 map/command contracts; R002 tenancy and actor lifecycle are transitive prerequisites. R003 and R004 are currently isolated drafts, not runtime evidence. **Do not create plan, tasks or implementation until these contracts converge and are reconciled with this draft.**
- The initial users are GIS-capable individuals or teams in a chosen authorized Project. One selected vector member/source per logical import, and whole-source fixed-revision export, are the approved first-slice boundaries; multi-member batch import, selected subsets, query-based exports and appending/updating existing sources are deferred.
- Only explicitly supported geometry families, dimensions, attributes, format profiles and CRS/control-point operations are promised; the format-specific matrix, exact version/encoding/field/geometry support and known losses must be finalized against reproducible independent fixtures before planning. No generic VN-2000 label, inferred coordinate system, or unverified precision is accepted.
- Source protection, staging, reauthorization, atomic publication, durable job identity, idempotency, retention/recovery and immutable evidence are baseline behavior, not deferred to R008/R015. Exact job resource limits, file limits, artifact lifetime and cleanup policy require recorded benchmark/evidence review before plan acceptance.
- R005 does not include CAD/DWG/DXF (R012), raster or live external sources (R010), feature editing/undo (R006), advanced spatial queries (R007), spatial analysis algorithms (R008), output cartography (R009), offline sync (R013), or cloud commercial operations (R015).
- Constitution and Accepted ADRs constrain planning; see [research and dependency gates](research-preparation.md). Scope approval is not authorization to invent technical details or mark the feature accepted.
