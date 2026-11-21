# Frontend remediation implementation evidence (2026-11-21)

## Boundary and candidate

Isolated branch `fix/018-fe-acceptance`, baseline `596fb13`. The focused real-browser candidate was `49371d3`, including `c3285b6` (isolated test harness and localized selectors), `56a0afa` (R006 graphical editor and exact attribute validation), `d076c82` (R007 typed filters, saved replay and revision-aware paging), and the one-line release-certification label correction. No production or house-numbering deployment, data, tenant, URL or service was modified.

Playwright drove local Chromium with one worker, a real isolated API, synthetic OIDC realm and local PostGIS test database via the repository's database wrapper; loopback API/web/OIDC ports 18083/5178/18084 and test DB 54332. Test artifacts were isolated. R006 tests explicitly blocked external HTTP. No screenshot, trace or credentials are attached. Own API/web/OIDC stopped after the run; no OOM. Raw local reports are untracked at `dist/fe-acceptance/focused-browser.json` and `interrupted-eight-case.json`; they are evidence for this checkout only, not release certification.

## Observed real-browser results

| Scope | Result | Independent evidence |
|---|---|---|
| R006 point graphical editing | PASS, 12.7 s | Mouse pointer snaps within 3 CSS pixels to an exact existing vertex. Draft point created at [105.84, 21.02], decimal input "2.00" re-read as canonical "2" from pinned feature API. Native vertex move, undo/redo, update, delete, revert verified by direct read. Independent update during staged draft rejected rather than rebased; stale draft cannot commit. |
| R006 line and polygon graphical editing | PASS, 6.9 s | Draw each geometry on native coordinate canvas, explicitly complete the sketch, commit, and re-read exact geometry coordinates and EPSG:4326 original CRS. |
| R007 typed attribute filter/save/replay | PASS within 6.2 s M2/M3 flow | Two independent point records, OR returns two; AND/NOT saved definition is persisted, page reloaded, stored query replay returns exactly the expected original feature ID. |
| R008 processing | PASS within that flow | Buffer of two point records; independent pinned feature reads show two Polygon results and canonical decimal buffer_meters "500". |
| R009 print | PASS within that flow | UI saves layer style and layout, exports PNG; authorized download actual PNG magic bytes and IHDR dimensions 1754 × 1240, A4 landscape 150 DPI. |
| M3 baseline hub/COGO | PASS within that flow | Visible readiness and R015 row, coordinate computation (500100, 2300000); dependency readiness is not release certification. |
| R005/M1 independent flow (earlier run) | PASS | Real import GeoJSON, map render/select/save, fixed-revision GeoPackage export/download. |
| R004 full reference-layer view | FAIL / unresolved | In earlier eight-case suite, first R004 map-workspace test received real viewport HTTP 200 and all three layer payloads were visibly feature-limit partial; renderer-ready attribute remained false at 5-second assertion. No rendering conclusion beyond that timeout. Run interrupted to prioritize focused cases, not suppressed. Other three legacy R004 cases were not run; the two native cases and M2/M3 were then executed in a separate focused run above. |

Focused run aggregate: **3 passed in 35.4 seconds**. Earlier interrupted run: 1 passed, 1 failed, 6 skipped. An initial outdated English sign-in locator had failed before localized selectors were corrected; initial native point attempt reached a real persisted creation before a stale combobox locator timed out, subsequently corrected and re-run successfully.

## Automated checks

- Initial complete `pnpm validate:ts` with graphical editor and first query rewrite: SDK **62/62**, web **51/51** unit tests, lint/typecheck and Vite production build passed. Subsequent final query UI typecheck passed and dedicated `query-filters.test.ts`: **14/14** passed. Build warning: large Vite chunk; not a build failure.
- Graphical geometry unit tests: **7/7**, including segment snap in CSS pixel tolerance, precise native-coordinate transform, polygon ring closure, rejection of unsupported dimensions and hole modification, and offscreen snap exclusion.
- R006 backend unit tests: **14/14**, exact canonical typed attributes and validation (including decimal/timestamp/invalid values); targeted Ruff passed.
- Browser tests: `tests/e2e/native-editing.spec.ts`, `tests/e2e/platform-m2-m3.spec.ts`, and earlier `tests/e2e/import-export-m1.spec.ts`.

## Honest limits and integration

R006 is an actual native-CRS SVG drawing workbench, not full GIS basemap editing: graphical Point, LineString and simple single-ring Polygon only, initial pinned 50 feature page/20,000 position graphical bound, no invisible reprojection, no modification that silently drops holes. Larger/unsupported shapes require manual GeoJSON or future graphical support. Draft is in-memory, not a durable offline queue. Server-side validation and revision conflict remain authoritative. The larger R004 renderer failure is open.

R007 saved-query payload no longer includes forbidden limit/offset or pins. The builder composes up to eight schema-aware typed conditions using AND/OR/NOT and reference-layer predicates; unsupported operators/values rejected, exact decimal conversion avoids binary floating point. Durable saved definition replay and first-page pin verified. Paging requires a server-issued fingerprint; SDK fields are optional for compatibility with the older baseline, so baseline paging fails closed until the processing agent's tightened R007 backend is integrated. No claim here of finished drawn AOI, map selection/highlight integration, arbitrary nesting UI or integrated fingerprint browser proof.

The separately developed R016/R017 UX line predates this baseline fork and overlaps page wrappers, labels, SDK/config and E2E selectors. Preserve canonical UX with the graphical workbench and query logic; reconcile exact paths and run real browser tests on the combined candidate. R013 offline shell generator must run after Vite build when combined. This evidence neither certifies all R001–R017 nor changes any release-matrix acceptance status. No deployment was attempted.
