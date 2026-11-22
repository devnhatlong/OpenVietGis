# R012 remediation — bounded 2D DXF interchange

**Status:** implemented and tested for the bounded profile below; not full CAD/survey acceptance.

## Source and tested candidate

- Feature commit: `877839417d36a2e5483d38444637daa25808eeee` (branch `fix/018-next-r012`).
- Integrated test candidate: `d32a37f93dab53ab4ace0af4631aeae70898e9d0` on the remediation worktree.
- Isolated synthetic database only; no audit or production database touched by this verification.

## Actual supported behavior

- UTF-8 text DXF R2010/R2013/R2018 modelspace. POINT, straight LINE, straight LWPOLYLINE (including declared valid closed polygon mapping). ARC, CIRCLE and signed curved LWPOLYLINE bulges are optional tessellations, not native curve preservation.
- The caller selects source length units (m/cm/mm) and an already georeferenced projected grid EPSG:3857 or EPSG:5899. `$INSUNITS` disagreement is rejected. No implicit origin, rotation, scale beyond unit conversion, geographic degree conversion, or control-point registration.
- Curve tolerance is explicitly supplied in *grid metres*, finite and in [1e-6, 1000]. The chord-deviation bound derives from `2*r*sin(step/4)^2` plus floating-point margin. Source bulge endpoints are preserved; infeasible precision/position budgets reject rather than flatten or silently relax tolerance.
- Bounds: 25 MiB upload, 10,000 entities, 4,096 positions per geometry, 200,000 positions per drawing. Nonstandard extrusion, nonzero elevation/thickness, polyline width, degenerate edges and unsupported geometry fail where necessary. Unsupported entities or secondary homogeneous geometry families are counted and disclosed.
- `POST /cad/inspect` requires project edit permission and validates output geometry with PostGIS without inserting source/layer/conversion or storing artifact bytes. It reports type/layer counts, entity handles and dispositions, chosen geometry family, exclusion/approximation counts, bounded chord deviation and drawing SHA-256. Drawing handles are scoped by original drawing checksum and resulting source. It does not claim lossless CAD fidelity or survey-grade precision.
- Loss-bearing publication requires explicit acknowledgement and a deterministic inspection fingerprint binding drawing bytes, selected units, CRS, curve tolerance and mapping profile. Changed fingerprint fails with 409; missing confirmation fails with 422. Successful publication emits a new project-owned source and layer. UI exposes meaningful file/units/CRS/tolerance selection, grid-coordinate confirmation, inspection report and explicit acceptance.
- DXF export requires a selected unit, exact source content revision and acknowledgement that attributes/original curve semantics are omitted. The source/layer rows are locked during extraction; non-XY, null/multipart/hole geometries unsupported by the simple writer are rejected. Output is an R2010 straight-segment DXF with declared length units.
- Existing COGO calculations remain clearly labeled unreferenced planar previews, not verified survey coordinates or committed edits.

## Executed verification

| Evidence | Result |
|---|---|
| `uv run --locked --offline --project apps/api python -m pytest apps/api/tests/unit/test_dxf_integrity.py -q` | 32 passed, including independent ezdxf bulge circle controls and measured chord deviation ≤ declared bound; six signed/major/minor bulges, closed final edge, ARC wrapping zero, mm conversion, CIRCLE tolerance/position limits, R2010/R2013/R2018 fixtures, unsupported/nonfinite cases, DXF reopen roundtrip, and no silent XYZ truncation. |
| Ruff and mypy on changed CAD backend files and fixtures | Pass (mypy 3 source files, no issues). |
| SDK/web `pnpm ... typecheck` and `pnpm ... lint` with cached locked dependencies | Pass. |
| Integrated root-run M3 suite on `d32a37f93dab53ab4ace0af4631aeae70898e9d0` | 9 passed, 0 failures/errors/skips, 19.425s. Includes authorized/denied inspection, no conversion after inspect/unacknowledged import, stale profile rejection, actual PostGIS import and independent ezdxf export reopen, stale export and loss-approval gates, COGO access/planar labels. Root-run JUnit: `dist/remediation-next018/initial-focused-m3.xml` within remediation worktree. |

## Residual acceptance gates

Do not mark original R012 fully accepted. Remaining gaps include verified survey/control-point transformation and tolerances in the relevant real-world CRS, exact per-entity roundtrip and preservation of native CAD semantics/layers/attributes beyond this simple geometry profile, separate verified DWG licensing/adapter, unsupported layouts/blocks/3D, R005 resilient job/cancel/retry workflow and failure-recovery evidence, pre-confirmation export UX/manifest and broader eligible revisions, and R006 revision-pinned precision reference snapping/edit acceptance. Browser end-to-end validation of the new CAD inspection UI is not claimed by the static check above. The deterministic tessellation tests measure grid-plane chord deviation, not earth-surface or field survey accuracy.
