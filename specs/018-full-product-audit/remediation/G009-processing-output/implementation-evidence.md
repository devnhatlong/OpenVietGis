# G009 — R008 derived output integrity, second remediation

Branch: `fix/018-r008-integrity` based on `596fb13` (includes the prior
canonical-decimal correction). This is a synthetic-only implementation checkpoint;
not a release acceptance, production repair, or production deployment.

## Concrete implementation

- Persist both content and schema pins for every input/overlay. Re-resolve the
  authorized active layer and source under locks at execution/retry, verify source
  ID, CRS, both pins, row count, geometry family/dimensions/topology and actual
  row pins. Refuse queued legacy jobs without schema pins rather than repinning.
- Keep job scope and row lock in the outer transaction. Execute and publish in a
  savepoint, rebind current RLS proof inside it, validate deferred constraints, and
  roll back all source/layer/features/catalog changes upon any domain or database
  failure. Rebind after rollback and persist a durable failed job with no output
  IDs. No internal SQL errors exposed to a user.
- Derive content revision from actual canonical attributes, native geometry,
  field interpretations and CRS, not merely job ID/output count. Validate result
  topology in PostGIS, then decode the same native WKB and validate the exact Core
  shape/XY/domain/position contract before publication.
- Clip requires polygon overlay and preserves the input family. Boundary-only
  contacts of lower dimension are not clipping output. Empty layers retain the
  source family and readable empty extent; no arbitrary first-row family.
- Dissolve distinguishes null grouping keys from the literal "__null__";
  parameterized field lookup and proper NULL groups. Preserve input family.
- Validate numeric JSON Buffer parameters without lossy strings, bools, fractional
  integer coercion or nonfinite values. Reject unknown parameters. Same operation
  ID with different algorithm, layer, overlay, parameters or output name conflicts;
  same request yields the original pinned job.
- First synchronous slice limits: up to 25,000 features and 1,000,000 positions
  per input and output (matching the transfer feature cap; independent Core max
  4,096 positions per feature). All output rows/positions counted before limiting
  response materialization. A limit violation is a durable failure, never a
  successful truncated layer. Local per-statement timeout 30s; no claim of
  bounded total processing latency or capacity at these limits.

Geographic Buffer remains EPSG:3857 projected distance as in the frozen original
oracle, not a geodesic or survey-ground-distance promise. Other supported CRS
profiles are not expanded; operations requiring unavailable transformation
support fail closed.

## Test evidence

Dedicated synthetic DB only: `ovg-remediation018-postgres`,
`127.0.0.1:54332/openvietgis_test`. Separate artifact directory
`/opt/openvietgis-agent-r008/dist/r008-integrity/artifacts`. DB usage was
coordinated exclusively with the parent task; released after testing.

Commands (set `OPENVIETGIS_TEST_DATABASE_URL` to the synthetic URL above,
`OPENVIETGIS_ARTIFACT_STORE_DIR` to the isolated path above,
`OPENVIETGIS_LIVE_OIDC=0`):

```sh
uv sync --locked --offline --project apps/api
nice -n 10 uv run --locked --offline --project apps/api python -m tools.run_with_test_database pytest \
  apps/api/tests/integration/m2/test_processing_integrity.py \
  apps/api/tests/integration/m2/test_r006_r009_real.py \
  apps/api/tests/unit/test_processing_domain.py \
  --junitxml=dist/r008-integrity/m2-unit.xml
nice -n 10 uv run --locked --offline --project apps/api python -m tools.run_with_test_database pytest \
  apps/api/tests/integration/m2/test_processing_integrity.py::test_clip_retains_family_and_empty_output \
  --junitxml=dist/r008-integrity/clip.xml
```

- First implementation run detected a genuine savepoint-scoped authorization
  issue (audit repository cleared the previous savepoint's RLS claim); fixed by
  re-verifying project scope inside the savepoint and after any rollback.
- Subsequent combined run: 31 passed, 1 failed solely because the new test read
  the geometry family at the wrong response location. Corrected the test to read
  `source.schema.geometry_family`, reran that test: 1 passed. **32/32 cases passed
  collectively on unchanged runtime implementation**, not a single all-pass run.
- Original M2 suite passed (including Buffer 1000/250/12.5 m regression).
- Stale pin after actual changeset: repeated retries fail with STALE_INPUT_PIN,
  original pins retained, zero new derived objects, resubmit succeeds; another
  tenant user denied read/retry/output access.
- Polygon partially overlapped + edge-only contact: exactly the overlapping
  polygon returned and attributed; disjoint polygon/point results empty with
  correct family; nonpolygon overlay rejected.
- Inject a publication failure **after** source, feature, and layer insertions:
  persistent failure, zero new derived source/layer. Retry without fault:
  readable 12.5m Buffer result, stale feature read denied, viewport and query
  return expected feature, GeoPackage export succeeds and downloaded bytes
  have correct SQLite header and SHA-256.
- Dissolve null/literal "__null__" stays separate; differing intent on same
  operation ID conflicts; exact replay returns original job ID.
- 26 parameter unit cases (distance bounds, string/bool/oversize/nonfinite
  number, fractional quad count, unsupported parameter).
- Ruff lint/format and git diff --check pass. Prior independent geometry oracle
  result remains documented in the first remediation; rerun against the final
  combined candidate is required (do not write into frozen audit artifact paths).

## Affected historical outputs: read-only inventory / repair policy

The frozen audit already independently reproduced a historically published
Buffer attribute "1000.0" that fails the exact canonical decimal parser. No
production inventory or in-place repair has been run. For an authorized operator,
this scoped read-only inventory finds the specific known defect in succeeded
Buffer outputs (including missing/non-string values); it is **not** a full
content integrity scanner:

```sql
BEGIN READ ONLY;
SELECT j.id AS job_id, j.output_source_id, j.output_layer_id,
       j.output_content_revision, COUNT(*) AS affected_features
FROM processing.jobs AS j
JOIN spatial.reference_features AS f
  ON f.organization_id = j.organization_id AND f.project_id = j.project_id
  AND f.source_id = j.output_source_id
WHERE j.status = 'succeeded' AND j.algorithm_id = 'buffer'
  AND j.organization_id = :authorized_organization
  AND j.project_id = :authorized_project
  AND (
    jsonb_typeof(f.attributes -> 'buffer_meters') IS DISTINCT FROM 'string'
    OR (f.attributes ->> 'buffer_meters') !~ '^(0|[1-9][0-9]*)([.][0-9]*[1-9])?$'
  )
GROUP BY j.id, j.output_source_id, j.output_layer_id, j.output_content_revision;
ROLLBACK;
```

Use correct current operator authorization and RLS; never bypass tenant scope.
For a known invalid result, preserve historical job and read pins. If the
original input revision is still current and authorized, resubmit a new
operation ID to publish a new source/layer with truthful new pins. If the
original input revision is no longer accessible, report inability to reproduce
that historical result; an explicit new current-input recompute is a different
job, not repair of the old immutable result. Any retirement/replacement of old
layers requires separate approved policy and scope; never rewrite pins/rows in
place.

## Remaining acceptance work

One final combined-candidate run of original independent geometry oracle,
complete exact-candidate regression, independent browser render/selection and
final release review. Historical production inventory/repair authorization,
performance/large-output stress and all CRS/geometry boundary coverage remain
unapproved/unverified. No production, original audit, or house-numbering DB
mutated.
