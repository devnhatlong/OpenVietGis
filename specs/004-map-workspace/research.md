# R004 resolved design decisions

Date: 2026-11-19. Baseline: verified main c5cc5a9, main regression CI 44341205122 success. Independent prerequisite/design review approved these choices with the constraints below. Historical draft dependency descriptions are superseded by this record.

## Authorization and identity
Decision: reuse SqlSpatialRepository.prepare_scope, transaction-bound project proof, existing project.read/project.edit permissions, service credential ceilings and CSRF. One logical map is UUID5(project UUID, "openvietgis:map"), revision zero until explicit first save. Reads never create tenant rows.
Rationale: preserve accepted R002/R003 lifecycle and RLS. No new role bundle or parallel ACL.
Alternatives: implicit write on open and role-name checks rejected.

## Durable configuration
Decision: ordered logical Layer references, bounded simple styles, grid basemap, and designated geographic viewpoint. A complete layer arrangement save carries separate viewpoint intent preserve/set/clear. Save operation identity is actor-bound; canonical fingerprint includes expected revision, arrangement and viewpoint intent. Check existing operation before CAS/no-op, under fresh authorization. Minimal receipts are available under current edit authority, including edit-only service credentials. Lifecycle loss, including archive, denies edit reconciliation; read configuration/history independently uses read authority.
Rationale: lost acknowledgements must not create new revisions, and incidental camera movement must never become shared state.
Alternative: last-write-wins/autosave rejected. First explicit empty save may commit revision1; subsequent equal configuration returns NO_CHANGES.

## Rendering and CRS
Decision: separate bounded viewport and display-extent reads, pinned to source content/schema, returning explicit EPSG:4326 XY geometry. Reuse only approved direct native→4326 operations and trusted provenance. MapLibre internal Mercator presentation is not a stored/exported CRS transformation. No 5899→3857 chaining.
Rationale: R003 native wire is not GeoJSON. Adapter converts geometry at MapEngine boundary. Core UI holds no renderer objects.
Alternatives: loading every feature page, native bbox-corner-only transforms and arbitrary reprojection rejected.
Capabilities render/style remain false until implemented for ready supported geometry/CRS; R004 updates accepted contract/tests explicitly.

## Response/work budgets
Decision: at most 32 map references; viewport limit 1..1000 (default500), 20000 positions and 2MiB serialized output; deterministic feature ID order with lookahead. Any limiting budget returns complete=false and bounded reason. No skipped oversized geometry can produce complete=true. Set transaction-local statement timeout 2000ms; supported first-slice sources are finite trusted R003 fixtures, max10000 records; no unbounded generic source scan. Extent uses actual transformed vertices with same pins, not corner guesses. Query/filter work and bytes must be verified in integration tests.
Rationale: truthful partial view and bounded service work.

## Basemap and renderer dependency
Decision: grid-only for this slice because no external provider is approved/configured. No hidden network requests. Optional external mode remains explicitly unavailable. MapLibre is already mandated by accepted ADR006, with exact eligible dependency version selected under normal frozen pnpm policy. Official documentation checked: https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/ and https://maplibre.org/maplibre-gl-js/docs/API/classes/GeoJSONSource/ . API implementation must be checked against installed declarations.
Alternatives: provider URLs or CDN runtime imports rejected.

## Evidence profile
Decision: existing GitHub Actions isolated PostGIS/Keycloak/Node26/Chromium profile is authoritative automated reference environment (accepted upstream). Synthetic point/line/polygon fixtures, 10000 feature source, desktop1280×900, grid/no external network, 5 warmups and100 trials each for open and select. p95 budgets3s/1s. Record runner/browser/pins/viewport and exact SHA.
SC009 requires five actual first-time GIS-capable participants. Keep human observation outstanding; never substitute agents. Internal implementation can be reviewed independently without claiming external acceptance.
