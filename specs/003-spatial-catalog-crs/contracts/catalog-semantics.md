# R003 Spatial Catalog API semantics

The normative HTTP schema is [spatial-catalog-api.yaml](spatial-catalog-api.yaml), OpenAPI 3.1. The [data model](../data-model.md) defines persistence, lifecycle and revision constraints. This text specifies cross-field and transactional semantics that JSON Schema alone cannot enforce. R003 is a synthetic, allowlisted reference-fixture capability only; no runtime is implied by this design.

## Route and access contract

All paths below are relative to `/api/v1/organizations/{organization_id}/projects/{project_id}`. Explicit UUID scope parameters are mandatory even when IDs are globally unique. No implicit tenant selection. All operations accept current R002 human cookie or service bearer; mutations require `X-OpenVietGIS-CSRF` for cookie authentication, not bearer.

| Method + path | R002 action | Success |
|---|---|---|
| GET /spatial/sources | project.read | 200 SourceList |
| POST /spatial/sources | project.edit | 201 SourceMutation |
| GET /spatial/sources/{source_id} | project.read | 200 Source |
| PATCH /spatial/sources/{source_id} | project.edit | 200 SourceMutation |
| POST /spatial/sources/{source_id}/retire | project.manage | 200 SourceMutation |
| GET /layers | project.read | 200 LayerList |
| POST /layers | project.edit | 201 LayerMutation |
| GET /layers/{layer_id} | project.read | 200 Layer |
| PATCH /layers/{layer_id} | project.edit | 200 LayerMutation |
| POST /layers/{layer_id}/retire | project.edit | 200 LayerMutation |
| GET /layers/{layer_id}/features | project.read | 200 FeaturePage |
| GET /layers/{layer_id}/features/{feature_id} | project.read | 200 FeatureDetail |
| GET /spatial/crs-profiles | project.read | 200 CRSRegistry |
| GET /spatial/changes | project.read | 200 ChangeList |

Use existing R002 current auth/permission evaluation, not new permission aliases, role names, or merely a capability boolean. Scope/auth checks precede resolving target resource IDs and validating data-dependent errors. An active Organization with active Project can be read/mutated according to effective action + service credential ceiling. Archived Project: allowed reads only, mutations 409 PROJECT_NOT_WRITABLE after authorization. Deleted Project, mismatched owner or inaccessible organization/resource: generic R002 404; same-scope missing permission: generic R002 403 (evaluate before target existence). Revoked/expired credential and suspension obey current R002 auth/lifecycle semantics. A credential ceiling with project.edit but without project.read is not implicitly granted metadata/pages/history. Mutation results therefore expose only affected ID, scope, change ID, revisions and lifecycle/validation result, not full source schema/extent/data. All resource reads resolve current Project grants (including changed inherited Workspace access) every time, regardless of valid pins. After scoped authorization, repository operations require transaction-local organization AND project GUCs (`openvietgis.organization_id`, `openvietgis.project_id`) for all five spatial tables; absent or mismatched context fails closed. Reset on transaction/savepoint boundaries, preserve R002 policies.

## Registration and catalog state

POST source JSON only `{"reference_key":"reference_points_4326","name":"Reference points"}`. A reference key selects a checked-in immutable platform registry manifest, not a physical table/path. All extra properties rejected without reflecting input (including passwords/DSN/URL/file/SQL). Unknown key 422 UNKNOWN_REFERENCE_KEY. Same scoped key already registered (including retired) is 409 SOURCE_ALREADY_REGISTERED, even with different display name; same key in another Project is independent and never disclosed. A source can be shared by Layers within this Project only. An interrupted request rolls back everything; retry registration or retrieve the existing authorized source from a list after ambiguous transport outcome. Names trim whitespace; blank/redundant no-op update rejected. No import, external connection, source rebind, arbitrary content/schema changes, file credentials, delete, restore or purge.

A valid key registers either a ready source or truthful invalid/not-ready state with stable `validation_reason.code` and non-secret actionable message. Examples: missing CRS → MISSING_CRS; conflicting declaration → CRS_MISMATCH; unsupported family/dimension → UNSUPPORTED_GEOMETRY/UNSUPPORTED_DIMENSIONS; explicit negative geometry states → NULL_GEOMETRY/EMPTY_GEOMETRY/INVALID_GEOMETRY; inconsistent axis control → AXIS_CONFLICT. No negative case is made ready just to support a read. Invalid fixtures may have known count/schema, but coordinate extent is unavailable and no feature page/detail is served. No count inferred from failure. Ready empty source has `feature_count_state:"known",feature_count:0,extent_state:"empty",extent:null`; no fabricated bbox. For ready nonempty source count known and extent available in verified native CRS, min/max X/Y of valid positions. No antimeridian wrap inferred: reject unsupported wrapping extent. Unavailable state requires null, available/known state requires value. Unknown source/stored CRS null (with reason), known definition-only profile can be reported as such but never ready. Known schema with zero fields differs from unavailable schema; unavailable has empty list and explicit state. Schema revision appears in the schema object and source root identically.

POST Layer only `{"source_id":"<UUID>","name":"Layer name"}`. Active ready same-scope source required; wrong scope/nonexistent/retired 404 (even if actor can access both Projects); known same-scope active non-ready 409 SOURCE_NOT_READY. No source field/geometry mutation. Each Layer has its own identity, name, timestamps, revision. Current Source embeds independently named source metadata. Both source/layer ordinary list and detail omit retired records. Capabilities are an explicit exhaustive fixed list: metadata_read, feature_read, render, edit, style, export, analysis, offline, query. Only metadata_read and feature_read technically supported, requiring project.read. metadata_read available for active Layer; feature_read available only for active/ready Layer+source. Other names have technical_supported=false, available=false, required_permission=null, actor_authorized=false; do not enable based on source name. actor_authorized checks current effective permission, never implies readiness. No map renderer, spatial query, feature editing, export, offline or style implementation.

Catalog list and change list `limit` defaults 100, 1..100, reject >100; optional `after_id` ascending canonical UUID key exclusive (equivalent UUID byte ordering). Return up to limit results and next_after_id equal last returned ID when additional result exists, otherwise null. No offset/unbounded list. Source/Layer lists include current full bounded metadata; `items:[]` for no active matches. Catalog/history pagination is current state, not a pinned snapshot; re-list if concurrent changes are relevant. Retired resources visible only via scoped immutable change evidence, not ordinary list/detail. Changes sorted UUID, not chronology; created_at denotes time.

## Mutation, revision and evidence

PATCH source `{"expected_revision":1,"name":"Renamed"}` and/or explicit `"declared_crs":{"authority":"EPSG","code":4326,"coordinate_order":"xy"}`. Correctable manifest: independent trusted registry evidence must confirm the proposed declaration and actual native geometry/SRID, exact X/Y and supported profile; revalidate full source. If evidence absent, wrong or remaining validation prevents ready, fail 422 CRS_CORRECTION_UNVERIFIED, no changes. Do not set/guess SRID, change coordinates, or accept arbitrary CRS parameters. Successful CRS correction records old/new declared identity, validation state/reason and affected revision tokens; content token changes if coordinate interpretation changes, schema token changes only if geometry/schema definition changes. Names only preserve both read pins. Correction is distinct operation correct_source_crs (including optional accompanying name change).

PATCH Layer `{"expected_revision":1,"name":"Renamed layer"}`. Retire source/layer POST `{"expected_revision":1}` only. Require current positive revision, atomic compare/update once; stale source catalog vs Layer use 409 STALE_CATALOG_REVISION or STALE_LAYER_REVISION. Stale check before no-op; unchanged input is 422 NO_CHANGES, no evidence. Retiring a source with active Layers 409 ACTIVE_LAYER_DEPENDENCIES, safe guidance “Retire active Layers before retiring the source”; no physical deletion, and no cross-project counts or IDs. Source retire increments catalog only; Layer retire increments layer only and does not affect source or sibling. Successfully committed retirement response indicates retired; subsequent ordinary direct read/mutation 404. No restore/purge.

Each successful material mutation returns change_id, prior_revision (null for creation), new_revision and new lifecycle, plus safe validation state/reason for source. Source revision object has catalog_revision/content_revision/schema_revision; Layer revision object layer_revision. No-op/failure leaves no successful event, partial resource or changed pin. Change rows atomically recorded with R002 success audit; GET /spatial/changes bounded current-authority Project list supplies resource/actor/safe display, operation, timestamp, prior/current typed revision objects, safe actual changed field old/new values. Register evidence includes name, reference_key/manifest digest, declared/stored CRS, lifecycle, state/count and identities, not raw source data. Field names and revision tokens are safe scalar old/new changes; no paths, credentials, raw features, geospatial payloads, SQL, or hidden locators. Actor is current human/service principal ID + safe snapshot, not presented credential. Recovery from interrupted mutation is retry with expected revision after authorized inspection; stale response demands reread, never auto-merge. An allowed, successful registration of intentionally invalid source is distinguishable from a failed registration: 201 invalid state and evidence, never ready data.

## Feature consumer and wire types

Obtain current content_revision/schema_revision from Layer or Source metadata. First and every page:
```text
GET /layers/{layer_id}/features?content_revision=<64-lowercase-hex>&schema_revision=<64-lowercase-hex>&limit=100
```
Continuation uses `after_feature_id=<previous next_after_feature_id>` with identical scope/layer, both pins and geometry options. The raw cursor is not opaque or a cross-layer credential; callers preserve context. Detail:
```text
GET /layers/{layer_id}/features/{feature_id}?content_revision=<same>&schema_revision=<same>
```
Both pins required; mismatch (either domain) 409 STALE_READ_PIN before any feature output. No historical fallback. Validate active/ready resource and current authority even for unchanged pins. Missing/retired/wrong-scope feature or Layer 404; non-ready active source 409 SOURCE_NOT_READY. Cursor is a stable source feature ID (not index); reject nonexisting scoped feature cursor 422 INVALID_CURSOR if pins match. Sort ascending ASCII C collation; limit default 100, 1..100 hard cap, fetch limit+1, next_after_feature_id = last returned only if another record exists, otherwise null. Empty page has items=[] and next null. For unchanged revisions and valid continuation, expected IDs exactly once; stable detail equals page data for same pins and geometry params, never substitute an ID. Use bounded consistent transaction/snapshot as data model defines.

All page/detail responses use identical `context` containing owner IDs, layer_id/source_id, content/schema revisions, geometry_included, response_crs and transformation. Feature entry `feature_id` stable, `attributes` exact key set from pinned schema, `geometry_state` explicit. Text JSON string (including empty string), integer JSON signed 32-bit, decimal base-10 canonical string with precision <=38 and scale <=18 (no exponent/trailing fractional zero except value zero encoded "0"; no negative zero), boolean JSON true/false, timestamp UTC RFC3339 string, null only nullable; missing entries invalid, zero not null. Field type determines string interpretation; clients never infer field identity/type from order or display name. Coordinate positions exactly two finite JSON numbers; total <=4096 positions per geometry; no truncation. Geometry omitted as a property when `include_geometry=false`; context geometry_included=false and response_crs/transformation=null. Supplying response_crs with include_geometry=false is 422 invalid request (do not silently ignore). With include_geometry=true (default), geometry included and explicitly references CRS (null only if a future readable source admits non-present geometry; R003 disallows non-present geometry for ready nonempty fixtures). geometry_state always present regardless of request. No geometry/CRS inference from generic VN-2000 labels.

Example ready native projected feature geometry (illustrative coordinate values):
```json
{
  "type": "Point",
  "coordinates": [438442.69, 2291039.83],
  "coordinate_reference": {
    "authority": "EPSG", "code": 5899, "coordinate_order": "xy",
    "x_axis": "easting", "y_axis": "northing", "unit": "metre"
  }
}
```
This is not GeoJSON. Source/source-schema CRS metadata reports separate EPSG-native axis order; geographic coordinates use X longitude Y latitude (degree); projected X easting Y northing (metre). Lines are ordered positions; polygons outer ring then inner rings, closed, valid, no rewriting to fit different convention. All geometries in each response agree with context.response_crs, native extent unaffected. No geometry coordinates stored in change evidence.

## Finite CRS definition and transformation registry

GET /spatial/crs-profiles returns 6 immutable definitions and 8 approved ordered edges; source/stored CRS metadata uses same definition object. EPSG:4326 WGS 84 (native lat/long, degree), 3857 WGS 84 / Pseudo-Mercator (east/north, metre), 4756 VN-2000 geographical (native lat/long, degree), 5899 VN-2000 / TM-3 107-45 (east/north metre; central meridian 107°45′, scale 0.9999, false easting 500000 m, false northing 0 m), 3405/3406 known-definition-only zone 48N/49N (east/north metre); exact datum/projection parameters and region from accepted EPSG [matrix](../crs-support-matrix.md). Registry advertises explicit support disposition, native and application axes, units, area and projection. Definitions 3405/3406 are distinguishable but never approved stored/response reads. No arbitrary definitions.

With geometry requested, optional `response_crs` is EPSG code; default native stored CRS. Identity in accepted readable CRS returns context.response_crs, transformation=null, same coordinates. For coordinate-changing request require direct validated edge and exact operation; no automatic chaining or library fallback. Frozen profiles:

| Directed edge | Stable operation_id | Method | Tolerance |
|---|---|---|---|
| 4326→3857 | epsg-1024-forward | analytic Pseudo-Mercator | <=0.001 m |
| 3857→4326 | epsg-1024-inverse | analytic Pseudo-Mercator inverse | <=1e-8 degree |
| 4756→4326 | epsg-6960-forward | VN-2000 to WGS 84 (2) | <=3 m |
| 4326→4756 | epsg-6960-inverse | inverse EPSG:6960 | <=3 m |
| 5899→4756 | epsg-5899-inverse-tm3 | inverse native EPSG TM-3 107-45 projection | <=1 m |
| 4756→5899 | epsg-5899-forward-tm3 | native EPSG TM-3 107-45 projection | <=1 m |
| 5899→4326 | epsg-5899-to-4326-via-6960 | explicit inverse TM-3 then EPSG:6960 approved as one registry edge | <=1 m |
| 4326→5899 | epsg-4326-to-5899-via-6960 | explicit inverse EPSG:6960 then TM-3 approved as one registry edge | <=1 m |

The composite approved edges are explicit frozen operations, not general graph-chaining. Every successful transformed context carries source/target codes, operation_id, exact method, validated_area, tolerance/unit and evidence_id. Analytic evidence uses independent formulas; VN edges point to the paired published control data in [vn2000-control-evidence.md](../vn2000-control-evidence.md) (Quang Ninh EIA Table 1.4 p45 and QH-04 drawing) and explicit runtime versions. Metre tolerances for geographic outputs evaluated using independent metre residual conversion as research documents. PostgreSQL 18 / PostGIS 3.7.0 / PROJ 9.9.0 with network grids disabled; runtime version or pipeline/control change requires revalidation before acceptance.

Applicability: 4326↔3857 longitudes [-180,180], latitudes [-85.0511287798066,85.0511287798066], appropriate canonical projected X/Y bounds ±20037508.342789244 m. 4756↔4326 R003 product rectangle lon [106.88,108.07], lat [20.70,21.42]. All 5899 edges use narrower rectangle lon [107.15,107.18], lat [20.70,20.73]. For VN edges, require trusted allowlisted fixture provenance and all geometry vertices inside appropriate geographic bounds, checked input and output (convert projected coordinates to geographic with approved inverse projection for area check). Applicability rectangle is conservative product acceptance for tested fixture/control area, not independent proof of nationwide accuracy or an EPSG onshore survey claim; public paired controls include port/anchorage waters. All coordinate values finite; known declared domain/axis contradiction rejects; plausible ambiguous coordinates alone are not proof. Projected storage check is based on verified native definition and provenance, not blindly treating metre coordinates as degree. No arbitrary source coordinate input.

Fail all requested geometry output if any required edge is not approved, operation unavailable, or any coordinate falls outside validated domain/area; no partial transformed page, no skipped features, no identity fallback or mislabeled native geometry. Return 422 UNSUPPORTED_CRS, UNSUPPORTED_TRANSFORMATION, TRANSFORMATION_OUT_OF_AREA, TRANSFORMATION_UNAVAILABLE, INVALID_GEOMETRY, or BOUNDS_EXCEEDED as applicable. In particular 5899↔3857 not accepted, despite possible composition, and no 3405/3406 response or arbitrary CRS. A metadata-only/attribute-only read does not authorize a coordinate-changing operation. Preserve source geometry/SRID on every read and correction.

## Error contract

- 401/403/404 use R002 generic `{"detail":"..."}` format; never disclose existence/revisions/extent/metadata of inaccessible target IDs. Same denial for guessed wrong scope vs absent target. R002 generic 422 validation uses `{"detail":[{"loc":[],"msg":"invalid request payload","type":"value_error"}]}`; no echo of raw payload.
- Spatial 409/422 use `{"code":"STABLE_REASON","detail":"safe useful guidance"}`. 409: stale catalog/layer/read pin, active dependencies, duplicate reference key, source not ready, authorized archived-Project mutation. 422: unknown fixture alias, no-op, unverified correction, unsupported CRS/operation or out of area, unavailable transformation, invalid cursor/geometry/bounds. Domain checks return safe reason; malformed primitive/extra request fields use R002 sanitized generic 422. Never emit payload fragments, raw SQL, internal paths, credential values, or foreign metadata.
- Re-read authorized current catalog on stale pin/revision and start a fresh traversal; retry interrupted request according to mutation contract. No transient failure is fabricated as successful registration/read.

OpenAPI syntax/contract validation is necessary but not runtime/acceptance evidence. Independent consumer should exercise current authorization, source/Layers, schema stable IDs, pinned pages/detail and explicit native/transformed CRS from these definitions, without SQL or renderer dependency.
