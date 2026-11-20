# R005 research, dependency and clarification gates

**Status:** Draft coordination input — scope approved 2026-11-18; unresolved technical/profile evidence below is not accepted implementation.
**Parent:** [R005](../../ROADMAP.md#r005).
**Branch base:** verified main `ea6db7974f8ee9820904909a3853e3a09d560920`; scope register `f86c64f` on `docs/r005-r015-grill`.

## Confirmed first-slice scope

The product owner approved an R005 slice for vector GeoPackage, GeoJSON and ZIP Shapefile with validation, immutable input and provenance, new DataSource/Layer only, durable jobs and fixed-revision export. GeoPackage is the preferred lossless exchange profile. No existing source overwrite/append; no CAD/raster/external adapters. Job infrastructure is required now and may be reused by R008; R008 algorithms are not part of R005.

## Prerequisites before plan/tasks/implementation

| Gate | Evidence required | Status at draft |
| --- | --- | --- |
| R002 Identity/Organization/Tenancy | Accepted explicit actor + selected Organization + Project authorization, lifecycle/invitation/revocation, machine credential identity/ceiling for durable background actions; safe errors. | Dependency; not converged at this base |
| R003 Spatial Catalog & CRS | Accepted DataSource/Layer/feature identity and ownership, revision semantics, schema/geometry/CRS profile metadata, supported read and capability contracts, independent VN-2000 control points. | Isolated draft branch `003-spatial-catalog-crs` at `3b8781c` |
| R004 Map Workspace | Accepted Map/Layer reference, add/view/select/table/inspect, shared Save authority and command/capability contracts. | Isolated draft branch `004-map-workspace` at `4c32816` |
| R005 interoperability evidence | Approved finite read/write matrix, reference fixtures, resource budgets, CRS tolerances, independent comparison and initial change/recovery rules. | Open; proposal below |

Synchronize the branch with current verified main at a clean checkpoint, then reconcile affected requirements. R003 and R004 draft references are evidence of intended boundaries, not accepted contracts. Main's roadmap will be linked to the actual spec by the integration owner, not edited concurrently by this feature agent.

## Candidate format matrix for review (not acceptance evidence)

| Format | Candidate import/export contract | Evidence / open boundaries |
| --- | --- | --- |
| GeoPackage | Preferred vector exchange; inspect listed eligible vector members, one selected member per initial import; supported typed fields, geometry and explicit native/approved transformed CRS. | Select supported specification/reader versions, geometry families/dimensions and field types, null handling, field naming, nonspatial members, restrictions; verify lossless profile independently. |
| GeoJSON | RFC 7946 FeatureCollection as candidate initial read/write profile; explicit longitude/latitude convention; compatible WGS84 output. | Validate exact object/property/type/null/geometry profiles, date/precision mapping, anti-meridian handling, unsupported legacy CRS declarations. |
| ZIP Shapefile | Selected coherent .shp/.shx/.dbf components; .prj or explicit validated CRS choice; .cpg or explicit/verified text encoding. Explicit schema and representational loss preview for export. | Select precise parser/format version, support/limit for components and geometry, code pages, field name/width/null/date/numeric mapping, collisions and permitted export-loss policy. Reject unknown/ambiguous input and archive traversal/bombs. |

No invisible coercion, dropped record, guessed CRS, guessed text decoding, or hidden field truncation. Exact allowed export loss mappings must be disclosed and expressly approved by the user; irrecoverable/unsupported inputs are rejected. One selected vector member per logical import and whole-source fixed-revision export are the approved first-slice boundaries. A broader export or import workflow requires separately accepted scope.

## Candidate research sources and validation plan

- [OGC GeoPackage](https://www.geopackage.org/spec/) and [GDAL GeoPackage driver](https://gdal.org/en/stable/drivers/vector/gpkg.html): review the accepted version/feature scope before selecting an adapter; standards/driver claims alone are not fixture results.
- [RFC 7946](https://www.rfc-editor.org/rfc/rfc7946), [GDAL GeoJSON driver](https://gdal.org/en/stable/drivers/vector/geojson.html): investigate coordinate convention, supported feature and property representations, round-trip semantics.
- [GDAL Shapefile driver](https://gdal.org/en/stable/drivers/vector/shapefile.html): investigate sidecar, encoding, schema/field, geometry and format limitations.
- Follow the Accepted [ADR-005](../../docs/adr/ADR-005-postgis.md), [ADR-006](../../docs/adr/ADR-006-layer-capabilities.md), [ADR-007](../../docs/adr/ADR-007-changeset.md), [ADR-010](../../docs/adr/ADR-010-object-storage.md) and [ADR-011](../../docs/adr/ADR-011-processing-jobs.md). Verify exact selected library versions and contracts during planning; no implementation choice beyond Accepted ADRs is decided here.

## Pre-plan decision/evidence register

1. **Fixture/CRS:** reconcile source, stored and export CRS with accepted R003. Choose specific Vietnam-first VN-2000 profiles, parameter definitions, applicable regions, independent control points and declared transform tolerance. No generic CRS labels or same-engine round-trip-only validation.
2. **Matrix/loss:** settle finite per-format/per-version read/write support, geometry and feature type, null/empty/zero and mapping policy; define allowed loss and preview/confirmation gate. Fixture set includes Vietnamese Unicode, legacy encoded text, nulls, empty data, coordinate dimension/invalid cases and mismatches.
3. **Reference performance and limits:** confirm reference hardware, dataset sizes/complexities, formats and transformation profile, proposed 10,000-feature profile with p95 import <=60s, export <=30s (exclude transfer/queue wait), at least 30 repeated trials. Set explicit maximum file bytes, archive expansion, entry count, job size/CPU/time/memory, artifact lifetime, retention/cleanup and bounded recovery targets. Targets are proposals requiring approval and measurement.
4. **Publication/changes:** settle durable initial import revision and required actual-change evidence, idempotent logical operation key, authorization on submit/run/publish/download and failure reconciliation. Require all-or-none ready publication and failure cleanup; avoid exposing stage records to catalog/query/download.
5. **Verification:** fixture-based independent comparison using a separate GIS reader such as QGIS/OGR; compare count, schema, typed attributes, null semantics, geometry/CRS and approved tolerance. For CRS changes use independent control points, not merely a reverse transformation with the same implementation. Run real database/runtime and browser/worker integration tests across tenant access, revocation, stale revisions, archive hostility, crash/cancel/retry/restart. M1 completes import → view/select → save/reopen → export → independent compare.


## Cross-feature contract alignment — audit 2026-11-18

Before plan acceptance reconcile the following gates with the converged upstream contracts. These are contract requirements and test proposals, not evidence that runtime has passed.

- **Revision/schema:** distinguish catalog/Layer metadata revisions, source-content revisions, stable schema/field identities and shared Map configuration revisions (R003/R004). Establish whether schema revision is embedded in, or separately referenced by, content revision. Specify available historical-revision retention/reconstruction and explicit stale failure; an identifier is not a promise of indefinite historical snapshots. Test the same source in two Layers: rename one Layer without falsely advancing content, change content with a stale reader/export, and reject an unavailable/replaced field with the same display label.
- **Common logical job contract (R005 owner, R008 consumer):** document permitted state transitions (accepted, queued, active, validation/confirmation where applicable, cancel-requested, recoverable failed attempt with explicit retry, success/unrecoverable failure/denied/cancelled terminal logical outcomes), recoverable vs denied outcomes, scoped logical identity + immutable fingerprint and distinct attempts, authorization on replay, and exactly-once visible publication. Pin preview/confirmation to input hash/member/CRS/encoding/options. A changed fingerprint requires a new logical action. Test same/different fingerprints, repeat confirmation, cancel-versus-publish race, retry and crash-after-success before acknowledgment.
- **Publication and artifacts (ADR-005/010/011):** select the failure-safe mechanism during planning. A candidate is verified immutable object staging/promotion followed by one short metadata transaction recording ready reference, revision/provenance and terminal job result; reconcile orphan objects or missing/corrupt references instead of assuming object-store and database writes share a transaction. Test failures after object write before metadata commit and after commit before response, and verify cleanup never removes a referenced successful object. Exact storage adapter, transaction/outbox technique, retention and cleanup policy remain research decisions.
- **Current authority:** require a non-secret credential identity and current grant/ceiling on submission, protected worker reads, publication and each protected result retrieval. Define an authorization success boundary such that revocation before publication wins against publication; historical committed success may remain but protected access is then denied. Evaluate an authorization-gated download delivery/handle; a direct unrevocable presigned URL cannot satisfy the revocation requirement by expiry alone. Test revoke in queue, mid-job/pre-publish and after issuance before handle redemption (including current scoped user/service identities and cross-tenant substitution).
- **Export boundary:** first-slice R005 exports the entire supported readable source at a specific revision, not a viewport/query selection. Do not expose subset export to R007 until a separately accepted contract and scope change. Test that a selection cannot narrow the exported whole-source result silently.

## Clarification status

No user-blocking question is needed to describe the approved first-slice behavior now. The above are explicit research/profile and dependency gates, not silently approved technical defaults. Review before accepting planning readiness. If any decision changes the approved scope, use separate product-owner clarification before revising the draft.
