# G004 — restricted live-provider sample slice

Branch `fix/018-r010-provider-adapters` based on `596fb13`.
This is a deliberately narrow working sample adapter, not acceptance of all R010.
No production deployment, live customer endpoint, external Internet request or
credential extraction was performed.

## Supported and denied operations

- WMS 1.1.1: GET Capabilities, validate expected named Layer, inherited SRS,
  bounding box and PNG support; GET Map 256×256 in EPSG:4326 (x/y) or
  EPSG:3857. Validate and re-encode actual PNG bytes; only `render` is enabled
  in a successful sample response. No GetFeatureInfo, style or edit.
- WFS 1.0.0: GET Capabilities, validate named feature type, EPSG:4326,
  advertised Query and JSON/GeoJSON extension plus geographic extent; GET
  Feature in an approved fixed bounding box, at most 100 features and
  512 KiB. Strict 2D GeoJSON lon/lat coordinate, count, property and subset
  geometry validation. Only `feature_read` and `query` (fixed bbox sample) are
  enabled in a successful sample response. No WFS-T, style, export, analysis,
  offline, page traversal, arbitrary query, filter expression or full layer.
- WMTS/XYZ, COG/GeoTIFF, generic OGC API Features, authenticated provider,
  WMS/WFS other version families, non-PNG maps, complex WFS geometry or
  responses requiring DTD/foreign members remain unsupported. The registration
  record's optimistic flags are never trusted.
- The platform UI can explicitly check and show the approved WMS sample image
  or the WFS sample GeoJSON. Reopen is a new request. No Core map catalog
  reference, arbitrary viewport integration, or data import is claimed.

## Operator approval boundary

Default configuration contains **no approved provider**, and therefore no
network call is permitted. The optional process environment variable
`OPENVIETGIS_EXTERNAL_PROVIDER_PROFILES` is a JSON list of exact operator
attestations. Example syntax using a deliberately non-live fixture only:

```json
[
  {
    "endpoint": "https://provider.example.org/wms",
    "protocol": "wms",
    "layer": "fixtures:parcels",
    "crs": 4326,
    "bbox": [105.5, 20.5, 106.5, 21.5],
    "attribution": "Controlled fixture",
    "license_text": "CC-BY-4.0"
  }
]
```

Each profile must match tenant registration endpoint, protocol, layer,
supported CRS and exact non-placeholder attribution/license, and an enabled
tenant allowlist. Ambiguous matches or malformed policy disable all applicable
operations. The profile is operator-owned process configuration, not writable
through the API. The operator must approve the geography/bounds and rights
before adding a real endpoint; no user viewport, features, tokens or other
data are forwarded. For WFS the only allowed CRS is EPSG:4326. Each operation
synthesizes its own fixed query parameters; the registration rejects arbitrary
URL query strings/fragments and embedded credentials. Legacy URLs are
display-redacted; secret reference text is not echoed in the API.

## Security and workflow

- Explicit POST with CSRF and live project-read permission, tenant/project
  row-scoped lookup; recheck authorization and profile after retrieval.
  Shared connection/allowlist locks prevent revocation/cache mutation during
  its bounded request. Allowlist registration now requires organization
  manage-settings permission. Revoked, disabled or unsupported connections
  and wrong-tenant/member-only callers do not egress.
- HTTPS only, port 443, exact canonical endpoint; validate **all** DNS answers
  as public, select and directly pin a numeric IPv4 address, verify the actual
  connected peer, verify system trust chain and hostname with TLS SNI. No
  proxies, redirects, credential forwarding, or alternate/retry destinations.
  DNS queue and concurrent request slots bounded, deadline 5 seconds/request
  (up to two requests/sample), absolute read shutdown timer.
- Strict HTTP media type/encoding/length; XML <=512 KiB, depth/element limits,
  no declarations/entities/DTD; PNG <=2 MiB exact dimensions/checksums and
  restrictive chunk set (no compressed textual metadata, extra frames or
  trailing data); output pixels re-encoded. GeoJSON <=512 KiB, <=100 features,
  no duplicate keys/nonfinite numbers, no CRS overrides or nested properties,
  coordinates wholly within approved extent. No external XML includes or
  follow-advertised service URL.
- Registration remains unverified or revoked. Successful preview has
  `availability=available`, no-store, and capabilities scoped explicitly to
  the verified sample only. Failure distinguishes disabled/revoked (403)
  and unavailable (502); no persisted positive flag survives a provider or
  policy failure. Cache generation is returned; UI state is keyed by
  project/connection/generation/lifecycle and does not preserve a stale
  preview on another record.

## Evidence

- Controlled raw HTTP fixture uses the actual stdlib HTTPConnection request
  serialization and response parser, with DNS/connect/TLS stubbed at the
  transport boundary (no live Internet). Request oracle checks host/SNI,
  exact pinned IP, operation, BBOX/CRS and no authorization/cookie headers.
  WMS verified independent decoded pixel values and dimensions; WFS verified
  exact returned feature and attribute values.
- 2026-11-21 integration run on dedicated synthetic existing PostgreSQL
  `127.0.0.1:54332/openvietgis_test`, unique artifact root. Three tests pass
  (new real HTTP API + RLS workflow with controlled provider bytes, existing
  R010 SSRF registration test, existing R011–R013 integration test), 52.96 s
  under concurrent workload. New workflow covers both WMS and WFS,
  owner allowed; other tenant and ungranted member denied; organization
  member cannot create an allowlist; exact profile rights; fresh reopen,
  failure after prior success; cache-generation increment, revoke and no
  post-revocation egress; unsupported profile and embedded URL denied.
  Original 4 `.invalid` audit probes passed on the inherited parent fix
  `596fb13`; not rerun in this isolated DB slot. The new exact candidate
  must rerun them before acceptance.
- Unit fixture and transport safety cases include mixed public/private DNS
  answers, DNS deadline, connected peer mismatch, TLS certificate error,
  redirects, content types/size/encoding, malformed XML/DTD/layer/CRS/extent,
  malformed PNG/dimensions/checksum, wrong WFS axis, count, nonfinite,
  nested property/CRS/duplicate keys, operator-policy mismatch/invalid
  configuration, revoked or credentialed connection and display redaction.
- Unit fixture/transport suite: 19 passed; targeted Ruff and strict mypy
  pass. Client SDK and web typecheck pass with Node 26/pnpm 12 (offline
  frozen lock, no new dependency). Browser integration remains pending.

## Remaining gates

No general R010 acceptance. Need separately approved WMTS/XYZ and COG slices;
verified Core map references and actual map viewport/zoom alignment/reopen;
complete provider/license/CRS matrix beyond narrow samples; controlled real
TLS/HTTP fixture or authorized deployed provider evidence independent of DNS/
socket stubs; browser acceptance for new preview UI; full exact-candidate
security regression and audit negative probes. Keep these unsupported and
do not advertise them until those gates pass.
