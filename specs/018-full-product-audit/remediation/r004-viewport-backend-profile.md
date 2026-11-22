# R004 viewport backend targeted performance remediation

Source pin baseline: `22a4ed17b7c6d7f1992e94b2c842f86d998cb9dd`. Runtime/test commit: `692d1e065948baf75b158c537659d1d9dcce1244`.

## Bottleneck and fix

The earlier SC007 browser probe failed the open p95 budget (3352.17ms > 3000ms) while selection passed. Its phase logs showed late viewport responses as one contributor, not exclusive causality. A short, restricted-role repository profile of the actual 10,000-feature geographic reference grid found separate full-source validation and repeated viewport scans/validation in an inline display CTE and candidate-to-display join. The line/polygon queries hit an excessive number of warm shared buffers.

The new query materializes the bounded display within one statement, computes the full-source count and bool-and validity summary, gates candidate intersections on that summary, and carries geometry in the bounded candidate prefix instead of rejoining all display rows. A summary LEFT JOIN retains a validation marker even for zero viewport hits and true zero-feature sources. Extent computes count/validity and actual geometry extent in a single statement. For native EPSG:4326 only, redundant unchanged-geometry validity predicates are removed; transformed geometry retains the full original final-display validation. No cross-request cache, change to authorization, tenant-scope GUCs, existing project/source/layer and revision locks, transformation pipelines, source bounds, statement timeout, position limits, feature limits, byte limits, or per-item output geometry validation. Count disagreement becomes a safe generic 503 without features or bounds. A materialized CTE may use Postgres work_mem and spill for more complex geometries; no all-source WKB is serialized and the previous 10,001-row scan cap / 2s statement timeout remain in effect.

## Measured targeted A/B, not SC007 acceptance

Synthetic test database `ovg-next018-postgres` bound to loopback port 54334; the existing 10k fixture was read only by the verified restricted runtime role, with legitimate synthetic owner context and real repository scope checks; a separate admin SELECT only found the fixture's metadata. Native EPSG:4326 source cardinalities: points 4,000, lines 3,000, polygons 3,000. Same SC007 observed geographic viewport west 106.59902182006971, south 10.6995617213054, east 106.60897817993373, north 10.708438213711858, limit 500; each complete viewport returns 81 items. The profile performed one warmed and five measured sequential calls per family/mode, timed the repository including real transaction authorization and SQL execution, and canonicalized and hashed every returned wire. All six baseline and candidate result digests are identical. An independent workload was active on the host: these are diagnostic medians, not an unloaded browser acceptance benchmark.

| Source / mode | Baseline median ms | Candidate median ms | SHA equality |
|---|---:|---:|---|
| points viewport | 46.267 | 36.226 | yes |
| lines viewport | 154.642 | 57.603 | yes |
| polygons viewport | 170.207 | 68.733 | yes |
| points actual extent | 32.815 | 35.921 | yes |
| lines actual extent | 53.474 | 47.063 | yes |
| polygons actual extent | 59.058 | 61.244 | yes |

Every measured request went from 26 to 25 SQL calls. The SQL and successful response path above remain unchanged in the final runtime commit; the subsequent count-mismatch handler change is failure-only.

A separate actual `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` run on the same scoped read statements compared the exact original source function and final candidate. One explained execution per statement, warm data (0 physical reads and 0 temp read/writes for this fixture). Do not use the extra run's overall elapsed medians, which include EXPLAIN overhead.

| Source | Baseline validation + viewport exec ms | Candidate combined exec ms | Baseline validation + viewport shared hits | Candidate shared hits |
|---|---:|---:|---:|---:|
| points | 19.491 + 31.997 | 15.401 | 316 + 384 | 316 |
| lines | 37.381 + 205.849 | 28.880 | 247 + 20,254 | 247 |
| polygons | 37.897 + 184.106 | 35.625 | 275 + 22,550 | 275 |

This reproduces reduction in repeated table and function work, not a claim that SC007 browser p95 now meets its budget. Actual browser render/init/application state remains part of SC007 and must be remeasured on the merged candidate, with its original warmups/trials/budgets.

## Regression verification

- Ruff and mypy on changed repository/tests passed (mypy one source file).
- `pytest apps/api/tests/unit/maps/test_map_viewport.py apps/api/tests/contract/test_map_viewport_http.py -q`: 32 passed. Added missing/over-budget snapshot count rejection and all-source result validation unit cases.
- Dedicated DB guarded test `pytest apps/api/tests/integration/maps/test_map_viewport_real.py -q -k 'single_scan or empty_source or direct_5899 or display_domain or runtime_has_no'`: 5 passed, no failures/errors/skips in 10.895s. Real 5899→4326 independent control coordinates; stale/foreign/no-scope and out-of-area rejection; new test retains visible valid hits but mutates one *offscreen* source point to latitude 86 with original source pins, verifies both endpoints return 422 without artifacts, restores that fixture, verifies count drift returns safe 503 and exact recovery; true empty source yields complete empty viewport/extent without a phantom feature. Existing broader map viewport integration suite remains for root integrated validation.
- Only the authorized 54334 synthetic container was started for this short profile and focused tests, then stopped (database preserved).

## Retained evidence

All files under `/opt/openvietgis-next-r004-backend/dist/r004-backend`, no protected IDs, SQL parameter values, raw geometry payloads, or credentials printed by the profiling scripts:

| File | SHA256 |
|---|---|
| profile.py | 6c9a16b1bfbe3a488c418bb57f6560285ac9f6ec9948cfa2a5b9e05fcdbd3ba8 |
| explain.py | 79db5f0e9f324e09848b52a2bdea2faf2a1d88f6dd7c973c68b5bd24dc939dfc |
| baseline_map_viewport.py (exact 22a4ed1 source) | 66f68d20e6929287df9d02e0a99e697ebae7514f5e04f70fe13165025d213a76 |
| baseline-profile.jsonl | 5fdf8a04a5e175549913f8ecbd29642beb574329edd7f50038c3c71ddae67d22 |
| candidate-profile.jsonl | 740aeeede3fc989deda4f3ba899bfa2140787c973099c08f6ea05f688ed86fba |
| baseline-explain.jsonl | 2fd0c0a6afd08fbcca4b95c91e0a04751f1a6a6ddc3070ed71617bc9486a8673 |
| candidate-explain.jsonl | fba69c77639e049829e0aa0a5fbde07e7481ea938e0c7606296adc123b04e9e2 |
| focused.xml | b0d04174698ee24e70d3e659fc727a5b0e3c3d65127c3b13296235c523afc45f |
