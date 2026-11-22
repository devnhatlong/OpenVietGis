# R004 renderer generation remediation

Date: 2026-11-22. Branch `fix/018-next-r004`, baseline `cb839d36bf1bdef4db03fb6ec355ad67e6e17085`. Isolated synthetic runtime only; API/web/OIDC on loopback 18085/5186/18086 and dedicated PostGIS test DB 54334. Existing house-numbering/test/prod services not changed. Browser Chromium, one worker, 1280×900, external HTTP blocked. No secret-bearing traces/screenshots or raw requests attached.

## What was actually wrong

The prior five-second large-reference readiness failure on an older UI line did not establish a renderer root cause. This common baseline already has a synchronous camera-fit viewport publication and awaits all three actual bounded partial responses before checking real renderer readiness. The baseline's unchanged product code passed the full existing large-reference browser flow in this session.

A separate reproducible implementation bottleneck nevertheless remained in the adapter: every identical React render frame, style/reorder operation and selected-feature change removed and rebuilt all native GeoJSON sources. A three-source test observed six source additions instead of three on duplicate frame or selection, and three removals rather than one when one source geometry changed. All four new adapter regression tests initially failed for these exact reasons.

MapLibre 6.18 package source also shows an asynchronous GeoJSON `onRemove()` worker message keyed by source ID and worker deletion keyed by that same ID. Immediately recycling `project-data-0..N` after removing them is an avoidable generation hazard; this is code-supported risk, not a claim it definitively caused the historic timeout.

## Implemented

- Reconcile frames using exact geometry and current scoped revision identity. Unchanged sources stay installed, including identical frame submissions.
- Apply selection through the existing actual paint expression, and style/order mutations through MapLibre paint/move APIs. Do not remove/reparse all geometry.
- Remove changed or absent layers and sources; changed source generations receive monotonically unique physical IDs within the renderer.
- Preserve previous scope/authorization safeguards: loading protected reads still explicitly submit an empty frame; denied/absent or changed geometry cannot retain an old source. Changed frames invalidate readiness and readiness still becomes true solely on actual MapLibre idle. No timeout or success-state relaxation.

Source implementation commit `6073aab11d47899a788947b887df7de0018d0f57`. Tests-only followups `a70a1d6` and `47b74be` synchronize selected camera network reads and canonical fixture color comparison.

## Unit and static verification

- Before change: four new adapter operation-count regressions failed (confirmed excessive additions/removals).
- After change: these four plus existing six workspace fail-closed invariant tests **10/10 pass**.
- Web typecheck and map-feature ESLint (zero warnings) passed. No build error; Vite bundle-size warning remains.

## Real Chromium

Baseline result: **1/1 full existing R004 test PASS**, 2.5-minute case (3.4-minute suite), largely source registration. Source catalog held 4,000 points, 3,000 lines, 3,000 polygons; on full extent it got 500 actual authorized features per layer with visibly partial status. Fit responses took 2,550 ms; actual readiness assertion took 17 ms, and the interval from all partial responses to verified ready was 702 ms. Full case also selected from table and canvas, changed arrangement, saved/reopened and checked immutable source metadata. No threshold was changed. The historic failure was not reproduced on this common baseline.

Corrected first focused attempt: reused the same explicitly identified synthetic fixture (read through ordinary authorized API, all three source pins verified). Got three real 500-feature partial responses in 1,192 ms, actual ready in 840 ms from all responses (26 ms readiness assertion); opening was 3,479 ms. This met the five-second readiness checkpoint. Subsequent canvas pick failed because the new regression had not awaited asynchronous fit-selection detail/viewport completion; added that actual network synchronization. Second attempt failed setup in 3.4 seconds because the fixture comparison did not normalize authoritative uppercase colors, giving the expected no-change 409; normalized colors before comparison. Both attempts retained separately, not suppressed.

Final corrected rerun at exact code+test commit `47b74be68bb3ccfc417ba436c0db4a83e5d2146c`: **1/1 PASS**, case 11.7 s, suite 20.513 s, no skipped/flaky/unexpected tests. Initial usable map open 2,844 ms; actual three bounded responses in 1,225 ms; actual renderer-ready check 11 ms, 865 ms from all responses. Visible status remained `partial` and 500 geometry records per layer. Real pinned detail and selected-viewport read succeeded, then Escape cleared selection and a real canvas click selected `point-000001` again. External request count zero. Own API/web/OIDC stopped; only shared test DB port left listening.

Exact verified source pins (synthetic fixture reused in both focused measurements):

| Family | Content revision | Schema revision | Manifest digest |
|---|---|---|---|
| Point | `8cc727a8541890a4d42c5aad802a166c23e5da7d0763c1da1d96e80fa3f17e11` | `e431628de1c897d4a8e8675c6cfc02bd541435fac44506ce79c02651db3ee106` | `c97ee6b2a350695aa0a8b7834eb854c0da45c42d16050bc886668644931d08e8` |
| LineString | `7ee21a43eab3f047b2b360ceaedf0a88080e3cc68a0394a4c5fd827cd1c14b7d` | `34bdc80d6b578817b9e042906735e6ac17c6d871081fc501d79b9907dff6f70c` | `15c390320ef9a24295cb0f0df8a356d75fe1249cd972663fde32965ffd374e43` |
| Polygon | `c94a8a652cc4d0739b08c9963396d48b39fee90906273145a0e0170cf78923a5` | `2d230da19ec8f536fe2ecb4114ee42f289ddfe5e161c0fe5c065f66027d26090` | `dbe99bc603c3572dfc34b62da0057217f59bfed7cef2da4e964bb1872f8d4a81` |

The fixture source pins and manifest digests are also emitted by the focused test and retained in local untracked JSON/log evidence. Baseline and corrected raw logs/reports stay under `dist/remediation-r004` (synthetic-only). Source counts and exact pins were tested via the real API, not mocked.

These are individual observed renderer workflows, not the R004 SC007 100-trial performance certification. The first corrected workspace open was 3,479 ms, above the 3,000 ms p95 budget if considered as an individual sample; no p95 or full release pass is claimed. Human observation gate remains open.
