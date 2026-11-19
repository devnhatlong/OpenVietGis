# Feature Specification: Map Workspace

**Feature Branch**: `004-map-workspace`

**Created**: 2026-11-18

**Status**: Implementation in progress on verified R003 main c5cc5a9; independently reviewed R004 design. Historical dependency notes below are superseded by upstream-contract-reconciliation.md. No implementation acceptance yet.

**Input**: Parent roadmap: [ROADMAP.md, R004](../../ROADMAP.md#r004). Provide a desktop-class GIS workspace where an authorized user opens one Map per Project, organizes available Layers, navigates and inspects real spatial features, and explicitly saves the shared map configuration. Keep the user's transient exploration separate from shared configuration. Do not implement import, geometry editing, advanced spatial query, cartography outputs, or vertical modules in this slice.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open and navigate the project's Map (Priority: P1)

A GIS professional opens an authorized active or archived Project and sees its map, layer list, command entry points, inspector, attribute table and current map status in one desktop workspace. They can pan, zoom and fit the map to readable data without requiring a domain module, external internet service or imported data beyond the supported reference source.

**Why this priority**: R004 is the first usable visual GIS workspace, not merely a map component or administration dashboard.

**Independent Test**: Open a Project containing a supported reference Layer and one fresh empty Project. Navigate between them, pan/zoom/fit available data and verify visible map status and correct geometry/CRS; repeat with the external internet unavailable.

**Acceptance Scenarios**:

1. **Given** an authorized Project has a saved map configuration, **When** the user opens it, **Then** the correct Project and Map configuration load and its toolbar, layer tree, map canvas, inspector and attribute table are accessible.
2. **Given** a newly created Project has no saved configuration or readable Layers, **When** it is opened, **Then** exactly one logical Map is available with a local blank/grid background and a useful empty-state instruction; no fake data or dummy extent is displayed.
3. **Given** supported visible Layers have nonempty known extents, **When** the user fits the Map to the selected Layer or all readable visible Layers, **Then** the displayed viewport contains the applicable extents and the display coordinate reference is identifiable.
4. **Given** a Layer cannot be rendered reliably, **When** the map is opened or the Layer is enabled, **Then** its unavailable, unsupported, stale, empty or partial state is clearly distinguished and no unsupported geometry is silently presented as a complete result.
5. **Given** an approved optional basemap service is configured, **When** the user switches to it and the service fails, **Then** the authorized internal Layers and workspace controls remain usable on the local blank/grid background without falsely showing the basemap as available.

---

### User Story 2 - Organize map Layers and control presentation (Priority: P1)

A GIS user chooses authorized catalog Layers for their project's Map, arranges their render order, turns visibility on or off, applies simple presentation settings and inspects whether the Layer can be rendered or queried. Map arrangement does not mutate or duplicate the underlying spatial source.

**Why this priority**: Users must organize the same underlying data into a readable working map before analyzing and editing it.

**Independent Test**: Use two distinct Layers that reference one source, add them to a Map, rearrange and hide one, adjust a supported simple presentation property and remove one reference; verify the other Layer and source still exist and their feature data is unchanged.

**Acceptance Scenarios**:

1. **Given** a Project has authorized render-compatible Layers, **When** the user adds each to the Map, **Then** the layer tree and canvas reflect each stable Layer identity with an explicit order and visibility.
2. **Given** overlapping visible layers, **When** the user changes their order or visibility, **Then** their visible rendering follows the requested order and hidden Layers are no longer rendered or directly selectable through the canvas.
3. **Given** a supported point, line or polygon Layer, **When** the user adjusts an applicable simple appearance setting, **Then** the Map reflects it without changing the underlying feature data.
4. **Given** a Layer is referenced by the Map, **When** it is removed from the Map arrangement, **Then** the catalog Layer, source and other references remain unaffected.
5. **Given** a Layer is not render-compatible, is retired, loses access or has incompatible geometry/CRS, **When** the user encounters it, **Then** no unauthorized metadata or falsely available operation is displayed and the remaining authorized Map can still be used.

---

### User Story 3 - Select a spatial feature and inspect attributes (Priority: P1)

A GIS user makes an authorized readable Layer active, selects one or multiple features on the map or in the attribute table, and inspects their stable identities, typed attribute values and applicable CRS information. Map highlighting, row selection and inspector state remain synchronized.

**Why this priority**: Reliable correspondence between map geometry and actual source records is the core value of visual GIS inspection.

**Independent Test**: Open a supported sample containing overlapping geometry, typed attributes, empty/null values and more than one page of records. Select individual and multiple features from both the canvas and the table; verify the same identities, map highlights and inspector facts.

**Acceptance Scenarios**:

1. **Given** a readable, visible active Layer, **When** the user clicks a selectable geometry in that Layer, **Then** its exact stable feature identity appears selected on the map and in the attribute table, and its attributes appear in the inspector.
2. **Given** an active Layer contains multiple eligible features, **When** the user toggles additional features using a selection modifier or table controls, **Then** the selected set and count agree across the map and table; the inspector shows the focused feature or explicit multiple-selection state.
3. **Given** a user selects a feature via its table row outside the current viewport, **When** selection changes or the user requests Zoom to Selection, **Then** the synchronized selection remains valid and the Map can fit the geometry when available.
4. **Given** a selected feature includes typed values, absent geometry, null or empty values, **When** its properties are inspected, **Then** the displayed facts retain their meaning and non-renderable features are not given invented geometry.
5. **Given** pagination, source revision or active Layer changes, **When** the selection can no longer be resolved under the current read authority, **Then** stale selections are invalidated or clearly marked for retry; no stale feature is identified as a current record.

---

### User Story 4 - Save and reopen a shared map configuration (Priority: P1)

A Project collaborator with the applicable edit permission explicitly saves their Map arrangement, supported simple appearance, selected allowed basemap and intentionally chosen default viewing position. Other authorized users reopen that revision while retaining their own temporary exploration and selection independently.

**Why this priority**: A usable Project has durable, shareable map presentation without one person's incidental navigation silently changing another's workspace.

**Independent Test**: In an active Project, save a configuration, close or restart the session and reopen it as two distinct authorized users. Verify the shared state matches the saved revision, the transient state is not shared, and an unauthorized or stale save is rejected.

**Acceptance Scenarios**:

1. **Given** a Project editor has unsaved map changes, **When** they explicitly Save, **Then** the shared arrangement, presentation, approved basemap and intentionally chosen default viewpoint are durably committed together and the new revision is shown.
2. **Given** a Project viewer opens that same Map, **When** they pan, zoom, inspect or temporarily change their local view, **Then** their exploration works without altering the shared saved revision; a shared Save is unavailable and unauthorized direct mutation is denied.
3. **Given** a user reopens a saved map in a new session, **When** the workspace loads, **Then** its supported saved properties are restored while another user's selected features, active Layer or incidental navigation are not inherited.
4. **Given** two editors open the same saved revision, **When** the first saves and the second attempts to save stale changes, **Then** the second receives a conflict with recovery guidance and cannot silently overwrite the intervening save.
5. **Given** a failure before commit, an archived/deleted Project or a revoked actor, **When** a shared map mutation is attempted, **Then** no new revision commits and the user is not falsely shown a successful Save.
6. **Given** a shared save commits but its response is lost, **When** the user reopens or retries the same save operation, **Then** the authoritative committed revision and outcome are reconciled without creating a duplicate revision or silently overwriting a later one; until resolved the client does not claim success.
7. **Given** an existing saved default viewpoint, **When** an editor pans or zooms and then saves only arrangement or style changes without explicitly choosing a new default viewpoint, **Then** the existing saved viewpoint remains unchanged.

---

### User Story 5 - Use consistent capability-aware commands (Priority: P2)

A GIS user uses the toolbar, layer context actions, keyboard shortcuts and command search to invoke the same available basic operations. They can understand why an operation is disabled and cannot accidentally invoke unsupported or unauthorized commands through another entry point.

**Why this priority**: A coherent desktop-class command experience is the foundation that later editing, analysis and module workflows extend.

**Independent Test**: Use the toolbar and command search to fit a Layer, clear selection and save when permitted; verify equivalent behavior and availability across authorized viewer, editor, absent selection, unavailable Layer and archived Project conditions.

**Acceptance Scenarios**:

1. **Given** a command is applicable to the active context, **When** the user invokes it from two supported entry points, **Then** it has the same observable result and checks the same authority and capability conditions.
2. **Given** a required capability or permission is absent, **When** the command is inspected or attempted via any entry point, **Then** it is disabled or denied with a non-sensitive reason.
3. **Given** the user selects another Organization or Project, **When** the context changes, **Then** old commands, details, map layers, selection and pending data are not shown or actionable in the new context.

### Edge Cases

- Fresh Project without a saved Map, no Layers, or no visible/render-compatible Layers.
- Empty/unknown extent, invalid or unsupported geometry, outside validated CRS transformation area, loading and partial results; do not assign invented geometry or imply full coverage.
- Multiple Layers referencing one source; overlapping features in active Layer; deterministic selection of one eligible feature per click.
- Hidden, retired, stale, unavailable or no-longer-authorized Layer; saved references resolve only where currently allowed.
- A table selection outside the viewport, null geometry, more rows than a page, duplicate display values, and null versus zero/empty string.
- Fast pan/zoom or rapid Project/Organization changes causing delayed/out-of-order results; stale results must not replace current content.
- Unauthorized Project/Layer/feature identifiers, tenant switching, Workspace reassignment, grant or account revocation, archived or deleted Projects.
- Stale map save, browser/tab closes before save, interrupted/retried saves, and configurations that no longer match catalog revisions.
- Optional basemap outage, expired credentials, invalid basemap configuration or blocked outbound network; no private source or feature data is sent to a third-party basemap provider.
- A Layer exceeds the supported rendering budget; disclose incomplete or generalized display rather than deceptively presenting it as complete.

## Requirements *(mandatory)*

### Functional Requirements

#### Project Map and workspace

- **FR-001**: The system MUST provide exactly one logical Map for each authorized Project in R004. Creating independent Maps, multi-map tabs and print layouts are excluded.
- **FR-002**: The desktop workspace MUST expose the current Organization/Project, central map, layer tree, toolbar and command search, inspector, and attribute table without a vertical module.
- **FR-003**: Opening an authorized Project MUST resolve its saved map configuration, or show a deterministic, usable unsaved default when none exists, including a useful no-data state.
- **FR-004**: Users MUST be able to pan, zoom, fit a selected readable Layer and fit all readable visible Layers; an empty/unavailable extent MUST not be replaced with an invented extent.
- **FR-005**: Coordinate-bearing view, extent, selection and detail information MUST use explicit, validated coordinate reference semantics from the accepted catalog contract. Source, stored and display CRS MUST remain distinguishable; ambiguous or unsupported transformations MUST not silently succeed.
- **FR-006**: A local blank/grid basemap MUST be available by default and require no third-party network access; authorized internal map viewing MUST remain usable when an optional external basemap is unavailable.
- **FR-007**: Optional online basemaps MUST be limited to explicitly configured and licensed providers with required attribution. No third-party request may contain tenant/resource identifiers, protected feature payloads, attributes or credentials for internal data; any viewport-location disclosure intrinsic to an enabled external basemap MUST be made clear before enabling it. Profiles that prohibit disclosure of viewed geography MUST remain on the local background and MUST NOT issue external basemap requests.
- **FR-008**: The workspace MUST identify loading, usable, empty, unsupported, unavailable, stale and budget-limited rendering states where applicable; it MUST NOT silently label incomplete/generalized display as full unmodified data.

#### Layer arrangement and rendering

- **FR-009**: Users MUST be able to add and remove references to authorized catalog Layers in their current Map, independently of DataSource identity and without deleting or duplicating source/Layer data.
- **FR-010**: The map layer tree MUST identify the active Layer, display order, visibility, and applicable rendering/read capability and availability; stable Layer identity MUST be preserved regardless of display name.
- **FR-011**: Changing layer order and visibility MUST change map presentation deterministically. A hidden Layer MUST no longer be rendered or directly selectable through the canvas until made visible.
- **FR-012**: Supported point, line and polygon Layers MUST have predictable default presentation and allow applicable basic settings, such as color, line width, symbol size or opacity, without changing source feature data. Advanced styling, labeling, classification, legend production and page layout are deferred.
- **FR-013**: The system MUST obtain renderable data through a bounded, authorized viewport-aware read contract extending accepted R003 basic reads. Each request MUST identify the current Organization, Project, Layer/source context, content/schema revision, bounded viewport and explicit CRS; response budgets and completeness/limited/generalized status MUST be explicit. Render reads MUST NOT be represented as general spatial queries, require R007, or rely on fetching unbounded complete datasets or provider-private storage.
- **FR-014**: Any rendering limits, truncation or generalization MUST be distinguishable from authoritative source completeness. The user MUST be able to inspect the actual supported feature attributes independently of rendering simplification.
- **FR-015**: A missing, retired, invalid, stale or no-longer-authorized Layer reference MUST be handled without invalidating all remaining authorized layers; unavailable and unauthorized references MUST be described only to the extent currently permitted.
- **FR-016**: Rendering, presentation and selection MUST preserve the accepted R003 stable Layer, source and source-scoped feature/field identities and published capability semantics. Renderability, resource lifecycle and actor authorization MUST be evaluated distinctly; read/selection semantics must not be inferred merely from display state. The saved Map configuration MUST not depend on private rendering-engine object identity.

#### Feature selection and inspection

- **FR-017**: Users MUST be able to choose one active authorized Layer and inspect its readable attribute schema (stable fields under its schema revision) and a bounded, deterministic page of rows pinned to the relevant content/schema revisions; browsing attributes is available for a readable layer even if some features lack renderable geometry.
- **FR-018**: The map MUST support selecting one eligible feature with a click and toggling additional eligible features using a clear selection modifier; overlapping eligible features MUST resolve deterministically. Advanced area/lasso/spatial selection remains outside this slice.
- **FR-019**: Users MUST be able to select one or multiple rows in the active Layer's attribute table and clear the selection; selection MUST remain stable across pagination within the same valid context and pinned content/schema revisions.
- **FR-020**: The canvas, table and inspector MUST use the same logical selection set and focused feature, scoped by Organization, Project, Layer, source and stable source feature identity under the relevant content/schema revision pins. An authorized stable-ID detail read MUST be usable for an eligible out-of-view or non-renderable feature, independently of render geometry. Highlighting applies to selected visible renderable geometry and selection remains clear in the table for non-renderable/out-of-view features.
- **FR-021**: The inspector MUST present available typed attributes under their declared stable field identities/schema revision, meaningful null/empty/zero distinctions, feature identity, the observed content revision and relevant coordinate reference facts without inventing values or geometry.
- **FR-022**: A user MUST be able to fit the view to selected readable geometry when nonempty valid bounds are available through an authorized bounded read in the current selection context, including for a selection outside the viewport; the action MUST respect CRS and explain unavailable, stale or empty geometry rather than fabricating location.
- **FR-023**: Switching active Layer or replacing the pinned source content/schema revision MUST clear, invalidate or explicitly re-establish selection under the new authorized context and revision. Stale, missing or revoked features MUST not remain represented as valid selected records or be silently substituted with another feature.
- **FR-024**: Changes or delayed results that no longer match the current authorized context, viewport, logical Layer/source or content/schema revision pins MUST not restore stale map or attribute content. A catalog/Layer metadata change and shared Map configuration change MUST be reconciled in their own revision domains, not treated as a substitute for data revision.

#### Durable configuration and permission

- **FR-025**: The shared Map configuration MUST contain the ordered logical Layer references, visibility, supported appearance settings, configured basemap choice and explicitly chosen default viewpoint with declared CRS semantics, and an identifiable committed configuration revision distinct from catalog metadata, Layer metadata, source content and schema revisions.
- **FR-026**: Shared configuration MUST be saved only through an explicit user-confirmed Save using the applicable Project edit authority. Temporary selection, active Layer, incidental viewport navigation and inspector/table exploration MUST remain separate from shared saved state. Changing the saved default viewpoint requires the user's explicit choice; saving other properties MUST preserve the existing designated viewpoint.
- **FR-027**: Authorized users MUST be able to reopen the most recent valid shared configuration across sessions/application restarts without inheriting another user's transient workspace state.
- **FR-028**: A shared save MUST commit all configuration changes and attributable revision information atomically. A failure before commit MUST preserve the prior committed revision; a lost acknowledgement after commit MUST be reconciled with authoritative persisted state and the identity of the same save operation. Retries with the same save-operation identity and equivalent save intent MUST NOT create duplicate revisions; reuse of that identity for a different save intent MUST be rejected. Reconciliation MUST re-evaluate current authority; no failed or interrupted save may leave a partial revision or claim success before confirmation.
- **FR-029**: A new save operation based on a stale shared configuration revision MUST be rejected with understandable recovery instructions. An existing newer committed revision MUST NOT be silently overwritten. Reconciling an already committed operation after a lost acknowledgement is not an unsolicited retry against a newer revision.
- **FR-030**: Users without shared configuration write authority MAY navigate and preview local arrangement/presentation changes within authorized data; they MUST NOT mutate the shared Map through the UI or other entry points.
- **FR-031**: Shared mutations of archived/deleted Projects, suspended Organizations or revoked actors MUST obey the accepted tenant lifecycle. Authorized archived Projects remain inspectable where allowed but cannot accept ordinary shared saves.
- **FR-032**: Every protected Map, catalog, render, feature, extent, detail and configuration operation MUST enforce explicit current Organization, Project, actor and resource authority. Inaccessible resources MUST not expose identity, metadata, geometry, counts or other protected details.
- **FR-033**: On Organization/Project change or an authoritative denial/revocation result, obsolete map, table, inspector, commands, temporary state and pending results MUST be cleared or safely isolated; already rendered data MUST NOT be replayed through another context. Cached tenant data MUST not bypass current authorization.
- **FR-034**: Material shared configuration changes MUST record actor, time, affected Map identity, prior/new configuration revision and inspectable safe evidence of what changed (old/new configuration values, a diff or equivalent retrievable historical representation) with attributable consistency. Evidence MUST respect current authority and omit secrets; these changes MUST NOT be represented as geometry/attribute edits.

#### Command and capability experience

- **FR-035**: Basic applicable map commands MUST be registered with stable operation identity separate from individual UI entry points and use consistent context, named technical capability, lifecycle and current accepted permission-action conditions. Technical capacity and actor authorization MUST remain distinct; the mapping MUST reuse accepted R002/R003 contracts and must not hard-code role-name shortcuts.
- **FR-036**: The toolbar, context actions, command search and applicable keyboard shortcuts MUST resolve equivalent operations consistently; unavailable operations MUST communicate a non-sensitive reason and server-side protected mutations MUST remain authorized.
- **FR-037**: The command and map contracts MUST support Core behavior without a domain module; unsupported operations MUST remain unavailable and no advanced GIS capability may be falsely advertised.
- **FR-038**: Authorized map viewing and shared save MUST have documented recovery from temporary failures, restart, stale revisions, lost acknowledgement and unavailable data; the user MUST be able to distinguish persisted state, unresolved save outcome and unsaved local changes, and safely reconcile the same operation without duplicate save.

### Key Entities

- **Project Map**: The single logical map within a Project and its durable identity, organization ownership and current saved configuration revision.
- **Map Configuration Revision**: The complete saved arrangement, simple presentation, basemap choice and explicitly designated viewpoint, with prior configuration revision, attributable safe changed-value evidence and save operation identity. Distinct from catalog/Layer and source content/schema revisions.
- **Map Layer Reference**: A reference to an authorized catalog Layer with Map-specific order, visibility and basic presentation properties; not a source, physical table or new duplicate Layer.
- **Viewpoint**: A bounded map viewing state expressed in explicit display CRS semantics, distinct from source data and the user's incidental navigation.
- **Workspace Session**: A user's temporary Project-scoped map exploration, active Layer, presentation preview, selection and focused row/feature; not a shared Map revision.
- **Feature Selection**: A context-bound set of logical Layer/source/feature identities scoped to Organization/Project, pinned to known source content/schema revisions and with an optional focus, used consistently by canvas, table and inspector.
- **Basemap**: Local blank/grid or an explicitly configured approved external background, including required attribution; never an implicit tenant source.
- **Command and Capability**: A stable supported operation with context, applicable capability, lifecycle and authority conditions, independent of individual UI control.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all agreed authorized fresh/saved Project fixtures, opening the workspace yields a correct map or explicit empty state, desktop working surfaces, and the correct configuration; the default map remains usable in 100% of disabled-external-network trials.
- **SC-002**: Across all supported point, line and polygon reference fixtures, the agreed layer-order, visibility, fit-extent and basic-style checks match expected presentation and leave source feature counts, schema, identities and coordinates unchanged.
- **SC-003**: In 100% of agreed map-to-table and table-to-map selection scenarios, scoped stable selected identities under pinned content/schema revisions, selection count, focused feature and available typed attributes agree with authorized detail reads; pagination does not silently lose or substitute selection. In agreed incompatible revision fixtures, stale selections or results are invalidated or explicitly re-established, not silently substituted.
- **SC-004**: In all tested successful shared saves/reopen/restart cases, the saved layer arrangement, styling, allowed basemap and explicitly designated viewpoint are restored, attributable prior/new configuration revisions and safe changed-value evidence are available, and transient navigation/selection never changes shared state. All stale or denied operations and pre-commit failures preserve the previous committed revision; all post-commit lost acknowledgements reconcile with the authoritative revision without duplicate saves or silent overwrite.
- **SC-005**: 100% of agreed unauthorized cross-Organization, cross-Project, revoked-access and archived/deleted-mutation scenarios disclose no protected current data or allow unauthorized mutation, including direct access, delayed results, cache/reopen and selection/attribute routes.
- **SC-006**: 100% of agreed rendering/coordinate error and incomplete-display scenarios expose correct unavailable or incomplete states instead of presenting unvalidated or incomplete data as authoritative; the accepted R003 reference control cases render and inspect consistently with their declared display CRS.
- **SC-007**: On the agreed local reference environment, with an initial reference dataset target of 10,000 features across supported geometry families and the recorded test viewport, 95% of authorized map openings with expected renderable data reach a usable view within 3 seconds and 95% of eligible feature selections show correct inspector properties within 1 second. Measure at least 100 trials per workflow after warm-up, record hardware, browser, dataset, viewport and external-network state. Finalize the reference profile against accepted R003 before planning; these are proposed measurable targets, not performance evidence.
- **SC-008**: In all agreed equivalent-command scenarios, toolbar/context/search/shortcut invocations have consistent results and unavailable or unauthorized commands cannot bypass restrictions.
- **SC-009**: In five observed first-time GIS-capable user attempts, at least four independently open a prepared Project, inspect an expected feature and reopen a saved map configuration within five minutes using provided authorized credentials and a one-sentence task; record failures without treating training as implementation evidence.
- **SC-010**: A clean Core-only installation with an accepted tenant/catalog fixture passes the open, navigate, select, inspect, save and reopen workflow without any vertical module, import/export implementation, or online basemap dependency.

## Assumptions

- **Planning gate:** R004 depends on R003 (Spatial Catalog & CRS), which in turn depends on R002 (Identity, Organization & Tenancy). The branch base contains the R002 planning baseline, not accepted runtime contracts. The R003 draft is a coordination input from an isolated branch, not merged or accepted. **Do not create the R004 plan, tasks or implementation until R002 and R003 have converged, been promoted to verified main and the relevant ownership, capability, feature read, revision and CRS contracts have been reconciled.** The integrating owner must transplant only this feature's specification documents onto the verified main baseline; this historical branch includes older shared/R002 planning history and is not eligible for wholesale merge.
- Scope is the initial local desktop-professional GIS experience, one Map per Project, with users who are GIS-capable. The Core remains independent from field/mobile/offline and domain modules.
- The first render profile uses supported reference spatial records from R003. R004 does not create ingestion or promise arbitrary file/database/OGC/render-source support.
- A logically shared map arrangement and explicitly selected default viewing position are durable; temporary user exploration is not a public sharing or collaboration feature. A viewer may preview authorized local presentation; Save requires applicable Project edit permission.
- A local blank/grid background is the default; online basemaps are optional, configured, licensed and separately opt-in with attribution and viewport privacy notice.
- Single/multi feature selection uses the active Layer and row selection; general spatial filters, advanced query, classification, drawing, editing, import/export, cartography outputs, processing, arbitrary external sources, CAD and offline are excluded in R004.
- Detailed contract/representation, rendering budgets and independent benchmark fixture/environment must be confirmed during planning against the accepted R003 data, geometry and CRS profile; no result is considered measured merely because a target is stated.
- Accepted architecture and governance constrain later planning: Constitution, ADR-003, ADR-005, ADR-006, ADR-007, ADR-008 and ADR-014; see [clarification and research preparation](research-preparation.md) for non-normative coordination detail.
