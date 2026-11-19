# R004 Map Workspace contract v1

Base /api/v1. Prefix P=/organizations/{organization_id}/projects/{project_id}. IDs logical; current R002 authority required. All responses no-store. Existing source/layer/feature R003 APIs remain authoritative for catalog, table and typed detail.

## Map persistence
- GET P/map: project.read, returns {map_id,organization_id,project_id,configuration_revision,configuration}. Virtual default revision0: {layers:[],basemap:"grid",default_viewpoint:null}. Deterministic map UUID5(projectUUID,"openvietgis:map"), no write.
- PUT P/map: project.edit+CSRF for cookie; body {operation_id:UUID,expected_revision:integer>=0,layers:[{layer_id,visible,style:{color,opacity,width,radius}}],basemap:"grid",default_viewpoint:{mode:"preserve"|"clear"}|{mode:"set",value:Viewpoint}}. No transient fields; unknown fields forbidden. Bounds per [data model](../data-model.md).
- Success200 receipt {map_id,operation_id,configuration_revision}. Minimal receipt discloses no complete configuration, so edit-only actors work.
- GET P/map/operations/{operation_id}: same actor and current project.edit (including current credential ceiling), returns receipt or generic404. Existing lifecycle denies archived edit reconciliation. Never use prepare_scope(edit,mutation=false).
- GET P/map/history?limit=1..100&after_revision=N: project.read, descending deterministic revision keyset; {items:[{map_id,operation_id,configuration_revision,prior_revision,actor_type,actor_id,actor_display_snapshot,created_at,before_configuration,after_configuration}],next_after_revision:null|N}.

Save lock/auth order Org→Project→map; operation hash binds expected_revision and entire canonical intent. Check existing operation+actor+hash BEFORE stale CAS/no-op. Same intent returns original receipt even after later saves, with no extra history/audit; other intent409 OPERATION_INTENT_CONFLICT, another actor generic conflict. Then validate scope/references and revision; stale409 STALE_MAP_REVISION; equal persisted intent409 NO_CHANGES; first explicit default save creates1. Commit state+immutable before/after revision+operation+audit atomically. No partial revision. Read current config separately to display committedN/currentM after recovered ack. Never silently retry as a new operation.

## Viewport and extent
- GET P/layers/{layer_id}/viewport?content_revision=...&schema_revision=...&west=...&south=...&east=...&north=...&limit=...
- GET P/layers/{layer_id}/display-extent?content_revision=...&schema_revision=...
Both project.read and fresh scoped pinned R003 snapshot, active readable compatible Layer/source. Bbox is explicit EPSG4326 XY, nonwrap[-180,180]×[-85.05112878,85.05112878]. Viewport limit default500,max1000; response {context:R003FeatureReadContext,items:[{feature_id,geometry}],complete:boolean,limitation:null|"feature_limit"|"position_limit"|"byte_limit"}. Geometry carries explicit4326 coordinate_reference, converted to GeoJSON only at engine boundary; no protected attributes sent to renderer.
Exact geometry intersection in display space with only approved direct operation/provenance. No bbox-corner-only approximations or full-source page traversal. Deterministic feature IDs,lookahead; cap20000positions/2MiB,2s SQL timeout and finite source work≤10000 trusted records. A limiting/oversized feature makes incomplete; never skip and claim full view. Unsupported data422 structured error; stale409 STALE_READ_PIN; denied follows existing nondisclosure.
Extent {context,state:"available"|"empty"|"unavailable",bounds:null|[west,south,east,north]}; approved transformed actual vertices; no guessed or partial full extent.

## Budget and selection clarifications
Bbox west<east and south<north, finite non-boolean inputs. History after_revision returns strictly smaller revision keys. All revision persistence uses BIGINT constrained to0..2^53-1. Position/byte limits return deterministic prefix with complete=false; count entire serialized response envelope. Database streams/caps output before materializing large geometry sets. SQL timeout rolls transaction back and returns sanitized503 MAP_READ_UNAVAILABLE, never a successful empty view.
Selection max100 stable IDs; zoom-to-selection resolves at most100 current pinned details with concurrency4 and an aggregate20000position/2MiB budget; exceedance makes action explicitly unavailable, never substitutes whole-Layer extent. Selection cap is a technical UI budget, not a claim source has only100features.
Render/style capabilities require active ready supported XY Point/LineString/Polygon and approved direct native→4326 profile/provenance, current project.read; style is local preview, shared save separately project.edit.
Mandatory contract/schema generation must include new map DTOs and reject drift.

## MapEngine
Renderer-neutral TypeScript contract: attach/destroy; set ordered logical render layers (IDs,styles,4326 geometry,pins); set camera/fit bounds; set selected logical IDs; clear; subscribe to settled viewport,pick,error. MapLibre isolated in adapter. Active visible Layer hit testing only; deterministic IDs de-duplicated. Renderer error => unavailable; incomplete viewport visibly partial. New context/denial clears retained renderer data and all pending generations.

## Commands and UI
Stable IDs map.fit-layer/map.fit-all/map.fit-selection/map.select/map.clear-selection/map.toggle-layer/map.move-layer/map.save/map.set-default-viewpoint. Shared registry resolves toolbar/context/search/shortcuts and explicit capability+current permission/lifecycle conditions. No role shortcuts. Local preview allowed for reader,shared save only editor.
Table uses existing keyset features100 maximum and typed fields; inspector uses stable-ID detail incl out-of-viewport features. Revision/context mismatch invalidates selection; page change retains same pinned identities. Hidden layers not canvas-selectable. Saving arrangement preserves designated view unless separate explicit set/clear. Unresolved Save keeps original operation identity and exposes reconcile. Grid-only,no implicit external URLs or fake basemap availability.
