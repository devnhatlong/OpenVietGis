# Feature specification: R010 truthful external-source capability

**Status**: Draft child remediation; scope/branch coordination pending.

**Parent**: 018 G004, original R010 FR-001–006, FR-008–019, FR-022–023, FR-038, SC-001/008. [Reproduction](../../evidence/r010.md).

## User scenarios (P1)

An authorized GIS user can distinguish registered metadata from a verified, available external source. A nonexistent, malformed, unauthorized or unsupported provider must not appear usable. An administrator can configure an approved source without exposing credentials, internal geography or unsafe network access.

Independent acceptance: replay the four deliberately unavailable-provider probes. For each separately approved adapter slice, use an isolated controlled provider fixture and verify actual metadata, imagery/features, map alignment/reopen, permitted operations, and denial of forbidden/unsupported operations. No provider capabilities enabled before its slice passes.

## Requirements
- FR-001 Separate configured/unverified, available, unavailable, disabled and revoked states; unknown metadata/rights remain explicit.
- FR-002 Deny or safely register metadata-only for unavailable or unsupported provider; never infer render/read/query/style from protocol name.
- FR-003 Provider retrieval uses bounded operator-approved destinations, actual connected-IP/redirect/TLS validation, no cross-origin credential forwarding, finite resource and parser limits; no unapproved geography/data egress.
- FR-004 Validate each enabled slice's actual service metadata, layer, CRS/axis/profile, rights and response bytes; disable unproved operations. WMS render-only unless separately proven.
- FR-005 Wire effective capability and availability to Core map/layer references, reopen and protected commands; re-evaluate auth/rights/cache revocation and never report stale success.
- FR-006 Prioritize fail-closed truth gate before any new provider adapter; migrate existing metadata-only records non-destructively to unverified when proof absent.

## Success criteria
- SC-001 Four .invalid tests pass; no unvalidated connection advertises active render/read/query/style.
- SC-002 For every enabled adapter, actual controlled fixture response and user workflow pass independently, including negative SSRF/rights/unsupported operations and map reopen.
- SC-003 No authorization bypass, secret leakage, uncontrolled network request or false active capability. Unsupported slices explicitly disabled.
- SC-004 Existing security tests remain passing, complete exact-candidate review and independent evidence before G004 closure.

Non-goals: arbitrary proxy; production provider credentials; unapproved adapters, intranet exceptions or live user-geography testing; claiming all four adapters complete from registration alone.
