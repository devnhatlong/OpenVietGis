# R009 and R012 independent remediation evidence

Root candidate caccfb3, isolated synthetic PostGIS container
ovg-remediation018-postgres at 54332; original audit/prod untouched.

## R009 — complete print output and actual scale

- A layout is rejected if it references absent, foreign, retired or unready
  layers, invalid extent, duplicate/excessive layer IDs. Export rechecks the
  same current scope and rejects over 2,500 features instead of silently
  truncating. Missing data extent no longer defaults to fabricated geography.
- Renderer preserves aspect, computes scale from the actual pixel transform,
  qualifies projected grid vs approximate local ground scale, labels grid
  north, handles multi-geometries and polygon holes, clips feature ink to map
  frame, rejects excessive/overflowing legend rather than silently clipping it.
- Independent unit controls: same vertical span gives the same scale for two
  different horizontally narrow extents; raster pixel oracle proves an
  unfilled polygon hole and both MultiPoint members; excess legend rejected.
  3 unit tests passed.
- Independent DB probe imports 2,501 synthetic points, verifies invalid/missing
  layout rejected and no partial print artifact created. Existing M2 outputs
  pass. Full pre-export preview, font/label profile and broader page fidelity,
  concurrent style/export jobs and approved scale tolerance remain pending.

## R012 — scoped COGO and fail-closed DXF interchange

- All four COGO preview routes require current project.read authorization.
  Raw caller coordinates are explicitly unreferenced planar input units,
  non-survey and not published; these previews do not confer edit permission.
  Finite bounded input/output, degenerate segment/tolerance limits, stable
  snapping priority and tie rule.
- DXF reads are size-bounded without silent truncation; import/export require
  supported projected metric CRS, export rejects feature-limit overflow,
  null/unsupported geometry, polygon holes instead of silently discarding
  topology, writes correct INSUNITS. Optional expected content revision
  rejects stale export requests. No DWG support asserted.
- 10 COGO unit cases + 6 DXF independent ezdxf unit oracles passed. Four
  integration cases show project owner success, ungranted member and
  cross-tenant denied. Existing real CAD import/export roundtrip passes.
- Full accepted geospatial precision/edit reference pinning, preview/explicit
  loss acknowledgement, linked per-entity provenance and profile-specific
  coordinate accuracy still need independent acceptance.

## Combined regression

M2/M3 integration on exact local root caccfb3:

`pytest apps/api/tests/integration/m2 apps/api/tests/integration/m3` through
the guarded test DB wrapper, 17 passed, no failures or skipped cases.
JUnit `dist/remediation018/combined-m2-m3.xml`. Earlier combined
63 unit tests at 1ba643d passed; later COGO/DXF 16 additional unit cases
passed. This is scoped regression evidence, not release acceptance.
