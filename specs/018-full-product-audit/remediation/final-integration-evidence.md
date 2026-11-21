# Integrated remediation checkpoint — 2026-11-21 (Asia/Saigon)

## Runtime candidate

- Branch `fix/018-confirmed-blockers`, runtime source SHA `9af7ba71a2d21104d9a54a66d22a049ada8d6d1d`.
- Earlier common candidate `d9096fe7a04104cc1f28048b06fa68a0764778ed` differs by only a cartography local variable rename and processing/query typing/narrowing corrections. The latter have 52 passing focused domain tests, and final source has passing Ruff and mypy (143 API files).
- Six isolated agent tracks converged with R016/R017 UX source history preserved, not by promoting a frozen audit branch. No production service, remote push, main promotion or release certification was performed.
- Synthetic, dedicated loopback Postgres/PostGIS and Keycloak, bounded local provider fixtures. No real tenant data.

## Actual work and evidence

| Area | Implemented and exercised | Remaining limitation |
| --- | --- | --- |
| R004 | Clear retained renderer data during protected viewport revalidation; unit invariant and map editing runs | 3 large world-reference layers still failed the 5-second renderer-ready checkpoint; partial response is not proof of renderer readiness. Human gate remains. |
| R006/R007 | Graphical points, lines, polygons, snap, vertex modifications, undo, version conflict, saved typed AST filters and revision-bound query replay | Focused workflows, not every geometry/edit/query requirement. |
| R008/R009 | Pinned durable processing jobs, atomic verified outputs, true buffer/clip/dissolve, complete-or-reject print, actual scale/holes/limits and PNG | Do not extrapolate bounded operations to unlimited data or every cartographic product. |
| R010 | Approved WMS/WFS, XYZ/WMTS real sample pixels and bounded uncompressed tiled GeoTIFF HTTP ranges; default deny, verified freshness | Advanced compressed COG window/overview reading, general provider viewport integration, approved real external endpoints. |
| R011/R012/R014 | Authorized review disposition, active assignees, bounded COGO, safer CRS/units DXF, scoped module lifecycle | Survey-grade accuracy, unsupported CAD curves, portable full history/migration, final installation policy/approval not certified. |
| R013 | IndexedDB durable scoped package, disconnected work, replay-safe queue, expiry/revocation lock; real synthetic offline Chromium and separate real API/PostGIS | Full joint offline-browser/real API acceptance, broader security/persistence policy. |
| R015 | Real backup/restore drills, recovered data and authority reconciliation, interrupted jobs quarantined; dependency readiness distinguished from certification | Authenticated/protected backup provenance, approved install/upgrade/RPO/RTO and deployment profile. No production-grade recovery acceptance. |
| R016/R017 | Current UX source integrated; static checks and focused real browser tests | Exact full 016/017 human/benchmark gates not exhausted; R017 T054/T056/T057 remain open. |

## Common-candidate validation

- `d9096fe`: 23/23 M2/M3 database integration checks, no failures/skips/errors (JUnit `dist/remediation018/final-m2-m3.xml`). SDK and web lint, TypeScript and unit suites passed in sequential chain; production Vite build plus offline shell generation passed. Scope, architecture, documentation and patch checks passed. RPC stdout timed out during this chain; do not claim an exact static test count for that run.
- `9af7ba7`: Ruff and mypy clean (143 source files); 3/3 Playwright Chromium focused tests passed with actual isolated OIDC/API/PostGIS and web build, zero flaky/skipped/unexpected. Point snapping/CRUD/revert/stale revision; line/polygon geometry original CRS; typed saved query/replay, processing output independent readback, PNG dimensions and platform hub. Log/JSON in separate detached verification checkout `/opt/openvietgis-agent-browser-final/dist/remediation-browser/focused-browser-9af7ba7.{log,json}`. Isolated API/web and Keycloak stopped after run.
- `9af7ba7`: final common M2/M3 integration 23/23, no failures/skips/errors, exit 0 (`dist/remediation018/final-m2-m3-9af7ba7.xml` and log). Full unit/contract/tools/architecture/modules expanded collection ran 691 tests: 690 passed, 1 reference-modules test failed with a NOT NULL column (`extensions.records.updated_by_actor_id`) present in the default loopback test database but not in the candidate's extension migration. No production database was targeted. The same test passed independently against the explicitly guarded, dedicated migrated `openvietgis_test` instance on 54332 (`dist/remediation018/final-reference-modules-9af7ba7.xml`). Thus 691 distinct checks passed across the two invocations; do not describe the first combined invocation as all-green or treat the old test database drift as a product fix. JUnit/log preserve the initial failure evidence.

## Release decision

NOT CERTIFIED. Release preflight on common candidate explicitly refuses because no accepted deployment profile, exact independent verification record or mandatory release certification. Human acceptance R002 SC-013, R004 SC-009, R005 SC-008 and the 656-requirement evidence reconciliation remain open. Automated focused evidence is not equivalent to 656 accepted requirements. No bypass, production deployment or promotion is authorized by this checkpoint.

See per-track evidence under the remediation and release specifications for isolated recovery, provider, processing and offline results; do not add their counts to the integrated suite as if disjoint.
