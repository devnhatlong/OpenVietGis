# R018 row-level reconciliation — 2026-11-22

**Scope:** all 656 original requirements (520 FR + 136 SC, R001–R015) and separate 87 supplemental R016/R017 rows. Original [inventory](../evidence/requirements.md) and [historical reconciliation](requirement-evidence-reconciliation.md) remain unchanged. This new index documents engineering evidence and unresolved requirements; it is not a release certification, owner scope exception, or claim that any complete row is independently accepted.

Base source `9b1231020b91cfed94b815277b27d672f6136a02`. The seven linked audits name their actual historical or current test pins, test-specific oracles and residual clauses. Four targeted runtime/safety changes integrated at `fabd8c401c183d633e6ef83b39e76b7955b39c55`; test-only benchmark commit `7f8479e` and fifth CRS consumer guard integrated at runtime `a2fdb8d80ee0b435a369bec58f7e2dc72303c6ee`. Do not transfer a passing historical assertion to a new candidate as exact evidence.

## Mechanically checked inventory

The root verifier parsed every Markdown row beginning with the exact original `Rnnn/FR-nnn` or `Rnnn/SC-nnn` ID, compared the 656 Core identifier set with the frozen inventory, and checked uniqueness across all seven reports: 656 expected/656 found, 0 missing, 0 unexpected, 0 duplicate. 87 supplemental rows also unique. Source lines and source refs remain authoritative in the frozen inventory.

Cross-report normalization is conservative: **test** names an exercised row-relevant assertion (may be partial or historical; consult actual pin); **mixed** is partial observation or mapped source with explicit residual gap, not a guarantee of execution; **historical** is the R001/R002/R016 report's explicit historical-only class; **static** is source/oracle mapping; **gap** is a particular missing behavior or acceptance gate; **human** requires independent human observation. These are mutually exclusive *review dispositions*, not release acceptance percentages.

| Group | Test | Mixed | Historical | Static | Gap | Human | Total | Row oracle report |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| R001 | 8 | 0 | 13 | 6 | 1 | 0 | 28 | [identity/foundation](row-audit-r001-r002-r016.md) |
| R002 | 55 | 0 | 12 | 0 | 0 | 1 | 68 | [identity/foundation](row-audit-r001-r002-r016.md) |
| R003 | 45 | 2 | 0 | 0 | 0 | 0 | 47 | [spatial and transfer](row-audit-r003-r005-r007-r008-r009.md) |
| R004 | 43 | 0 | 0 | 1 | 3 | 1 | 48 | [map/workspace](row-audit-r004-r017.md) |
| R005 | 12 | 32 | 0 | 0 | 0 | 1 | 45 | [spatial and transfer](row-audit-r003-r005-r007-r008-r009.md) |
| R006 | 30 | 0 | 0 | 12 | 4 | 1 | 47 | [editing](row-audit-r006.md) |
| R007 | 17 | 28 | 0 | 0 | 1 | 0 | 46 | [query](row-audit-r003-r005-r007-r008-r009.md) |
| R008 | 6 | 33 | 0 | 0 | 4 | 0 | 43 | [processing](row-audit-r003-r005-r007-r008-r009.md) |
| R009 | 2 | 26 | 0 | 0 | 12 | 1 | 41 | [cartography](row-audit-r003-r005-r007-r008-r009.md) |
| R010 | 37 | 0 | 0 | 4 | 9 | 0 | 50 | [external/collaboration](row-audit-r010-r011.md) |
| R011 | 34 | 0 | 0 | 5 | 8 | 0 | 47 | [external/collaboration](row-audit-r010-r011.md) |
| R012 | 37 | 0 | 0 | 2 | 4 | 0 | 43 | [CAD/offline](row-audit-r012-r013.md) |
| R013 | 37 | 0 | 0 | 4 | 3 | 0 | 44 | [CAD/offline](row-audit-r012-r013.md) |
| R014 | 26 | 0 | 0 | 2 | 1 | 0 | 29 | [module/recovery](row-audit-r014-r015.md) |
| R015 | 30 | 0 | 0 | 0 | 0 | 0 | 30 | [module/recovery](row-audit-r014-r015.md) |
| **Core** | **419** | **121** | **25** | **36** | **50** | **5** | **656** | 0 accepted |
| R016 (supplemental) | 14 | 0 | 19 | 2 | 0 | 0 | 35 | [identity/foundation](row-audit-r001-r002-r016.md) |
| R017 (supplemental) | 47 | 0 | 0 | 1 | 3 | 1 | 52 | [map/workspace](row-audit-r004-r017.md) |

Dispositions were calculated from each report's row class, not a score or test coverage percentage; an observed row can still contain significant missing clauses. Gaps identified and remediated during this round remain visible as baseline findings. No row promoted to accepted.

## Targeted changes and verified evidence

- `32a7378` validates both independently configurable application and Alembic migration destinations before destructive reset; same host/port/db required, unsafe libpq redirect refused. 52/52 focused safety/config/docs tests on agent patch; no destructive operation performed.
- `b4ddb38` uses local grid regardless of protocol, disables unapproved online basemaps with explicit disclosure, rejects direct adapter selection; 56/56 focused map tests and web build/TypeScript/ESLint passed. This deliberately does not approve a third-party tile license or connect a provider. Old exact browser performance evidence remains pinned to pre-change runtime.
- `fd11e97` refuses no-material changesets (no new revision/history), authorizes snap against current edit permission, and serializes replay lookup with source mutation. Existing project mutation locking already serializes ordinary writers; the source lock is an additional explicit guarantee, not evidence of a demonstrated race in all paths. Real PostGIS M2 4/4, including no-op invariant, snap denial/grant/revocation and concurrent same-fingerprint one receipt/one publication. JUnit `dist/remediation-row-audit/r006-fixes.xml`.
- `fabd8c4` explicit source/layer snapshot locks and strict row revision/schema pins during offline package issuance, fail closed on inconsistency. Ordinary Core writers were already serialized by organization/project locks (first test's incorrect source-lock assumption failed; retained). Revised real PostgreSQL test observed actual blocker and correct old/new snapshots; two injected pin inconsistencies reject; original M3 passes: 4/4, no skips. `dist/remediation-row-audit/r013-pin-guards.xml`.

- `a2fdb8d` uses registry-approved explicit WGS84/Web Mercator operations for cross-CRS Buffer/Clip/print, with source/domain validation and print operation provenance; unapproved arbitrary VN2000 datum and polar Web Mercator transformations reject without publishing outputs. Existing same-native and registered supported paths preserved; 8/8 real PostgreSQL focused suite on isolated patch, no errors/failures/skips (`dist/remediation-row-audit/crs-guards/crs-guards.xml`). This is not a survey-distance accuracy guarantee or full processing/cartography profile acceptance.

## Combined verification

- Exact before CRS guard `fabd8c4` runtime: 782/782 Python unit/contract/tools tests, 4/4 architecture tests (separate JUnit), zero failures/errors/skips. Full TypeScript lint/typecheck, SDK 63/63 and web 139/139, production build and offline shell 572f6a0833b56c467742ef5f, generated SDK contract drift/scope/architecture/docs checks all passed. `dist/remediation-row-audit/{row-audit-static.xml,row-audit-static.log,row-audit-ts.log,architecture-fabd8c4.xml}`. No default opt-in benchmark was run in ordinary unit/contract suite.
- Exact combined `a2fdb8d` runtime: real dedicated PostgreSQL/PostGIS 14/14 (32.304s, 0 fail/error/skip) covering CRS consumer guards, processing integrity, cartography completeness, R006 replay/no-op/snap and offline package pin guards. JUnit/log `dist/remediation-row-audit/combined-a2fdb8d.{xml,log}`. Ruff, mypy 145 sources, scope and architecture guards pass. Owned 54334 stopped after tests. Independent server activity untouched.

## R002, R004, R005 technical and observation gates

- Baseline `9b12310`: 50/50 actual restricted PostgreSQL/PostGIS integration tests (87.274s, no skips) covering identity/tenancy bootstrap, grants/revocation, invitation binding, map saves/security, four transfers tests and editing/change evidence. JUnit `dist/remediation-row-audit/technical-9b12310.xml`. The full identity matrix and independently observed human flow are not inferred.
- R004 SC007 prior exact `d1c9c69` browser p95 2179.08ms open, 305.00ms selection with 100 measured each, five warmups each, no external requests. [Detailed prior evidence](r004-third-integration-evidence.md). No transfer of exact runtime acceptance following frontend basemap changes.
- R005 SC007 proposed GeoPackage point profile at `9b12310`: five warmups + 30 measured in-process confirmed HTTP POSTs, 10,000 2D EPSG:4326 points with typed text/integer fields, 618496-byte input, each output independently reopened with GDAL and exact count/CRS/hash checked. p95 import 2.945s (60s target), export 1.503s (30s target); all 35 successful. Excludes upload/inspection/preview/download and queue wait; actual host 2 vCPU, concurrent unrelated host activity, no production guarantee. Raw and JUnit + exact original probe retained in `dist/remediation-row-audit/r005-sc007-9b12310/`. This is observed compliance with proposed numerical thresholds only; owner profile approval and other format/geometry coverage remain open.
- R002 SC013, R004 SC009, R005 SC008 still require real independent humans. [Execution protocol](manual-acceptance-runbook.md) defines thresholds, fixtures, consent, timing, and no agent substitution. R006 SC008 and R009 SC008 are additional human dispositions; supplemental R017 SC002 separate. No recording of fictional observations.

## Prioritized remaining work

1. R002/R004/R005 exact combined functional security/browser and performance retest; record genuinely independent eligible attempts on a fixed candidate and synthetic fixture. Keep any failed attempt.
2. R010 approved external adapters and logical layer/Map integration, explicit provider rights/capability and partial/truncation semantics; no direct unapproved public tile calls.
3. R011 collaboration activity feed (committed edit events, stable bounded pagination and role/assignee lifecycle), idempotency and conflict/review matrix.
4. R006 draft/schema/history complete independent oracle, import-provenance/export roundtrip, accepted benchmark and manual workflow; R007 query full formal matrix.
5. R008/R009 approved CRS operation gates, analysis profile and submitted revision pins, approved common job/state/recovery and print/export artifact completeness/latency.
6. R012 survey-grade/reference/georeference and CAD job workflow; R013 offline classification/storage and per-operation identity, wider sync conflict scenarios.
7. R014 installation approval/dependencies/explicit namespaced module capability authorization; Core-only recoverability independently tested with modules absent.
8. R015 approved self-host operational profile TLS/OIDC, resource and reliability targets and complete recovery drill of schema 0019 including extension histories.

No production deployment, push, main promotion, independent service changes, fake human approval, or release-gate alteration authorized by this index.
