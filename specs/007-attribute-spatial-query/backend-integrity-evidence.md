# R007 query backend integrity checkpoint

Branch fix/018-r007-query-integrity based on caccfb3. No production or frozen
audit mutation, no source schema migration. This checkpoint hardens the
existing first implementation and does not itself accept the original full
R007 research profile or saved-query expansion.

## Actual defects corrected

1. Integer coercion previously truncated fractional input or raised HTTP 500;
   decimal comparison/sort used double precision, collapsing distinct 18-digit
   values; timestamps sorted as raw strings; contains used unescaped wildcard
   ILIKE. Query values now use the exact Core typed contract and parameter
   binding. Decimal binds Python Decimal to PostgreSQL numeric, dates bind an
   offset-aware datetime to timestamptz, text is literal case-sensitive C
   collation (no Unicode normalization, accent folding or wildcard/escape
   interpretation). Null comparison remains SQL three-valued logic, only TRUE
   matches. Integer, text, timestamp and decimal support equality, ordered
   comparisons, inclusive between, in and null predicates. Boolean supports
   equality, inequality, in and null tests. Literal contains/prefix are text
   only. Reject unknown/malformed AST fields/keys/operators, wrong types and
   oversized complexity; no arbitrary SQL.
2. Query pagination formerly checked optional target content only, not schema,
   reference revision or sort. Source/Layer locks and current project.read
   authority are required for both inputs. Responses contain target pins
   (content and schema), optional reference pin, and a query fingerprint bound
   to current scope, actor/credential, both pinned inputs, query/filter/order
   and explicit transformation. Offset>0 requires expected_query_fingerprint
   from the previous page. A changed input, predicate or order fails stale.
   Optional expected_content_revision and expected_schema_revision can pin
   the first page too. Stable feature-ID tie break, nulls last and exact
   typed sorting. Fingerprint is a consistency assertion, not a credential.
3. Reference sets formerly applied an unordered LIMIT 500, returning a false
   exact total. Oversize whole reference sets are rejected; explicitly requested
   missing reference feature fails not-found. Cross-project references always
   resolve within the same authorized scope, even when IDs are substituted.
   Input and result snapshots are checked for row-count/pin/geometry/type
   integrity. Return actual native WKB-decoded coordinates without GeoJSON
   precision rounding or implicit CRS.
4. Drawn geometry formerly assigned guessed CRS and arbitrary PostGIS
   ST_Transform. Require bounded explicit-CRS native XY Polygon, ring shape,
   domain and valid topology; reference geometries also receive Core shape
   validation. Spatial predicate direction is target versus each reference;
   intersects/within/contains use actual PostGIS relationships, duplicate
   reference matches aggregate only through EXISTS. Same-native-CRS planar
   relationships in supported vector families and fixed non-fixture-dependent
   R003 4326↔3857 single-step pipeline supported. No guessed operation or
   fixture-dependent 4756/5899 cross-CRS conversion; those reject explicitly.
   Geographic wrapping unsupported. Drawn geometry topology checked before
   transformation (final small safety tightening; included in combined gate).
5. Saved definitions now validate complete typed filter, sort, and authorized
   spatial reference/drawn shape before persistence; reopening and replay
   uses exact same query endpoint and current checks. Existing saved definition
   storage is a live definition, not historical materialized/pinned result.
   Old invalid/coercive saved definitions fail on replay; no legacy data
   rewriting, saved-query history, durable schema pin or sharing expansion.
6. Explicit limits: depth 6, 100 nodes, 1,000 bound values, membership list
   1..100, drawn positions 2,048, 25,000 target features, 1,000,000 target
   positions, 500 reference features/100,000 reference positions, page 500
   features/20,000 positions, offset max 25,000, 5s local per-statement timeout.
   Fail closed when limits exceeded; no successful empty result for SQL error,
   timeout, invalid source or inaccessible reference. Saved listing over 500
   explicitly rejects rather than truncates. Selection_feature_ids identifies
   only the current returned page, not query-wide selection; whole-source
   export remains independent and no subset-export API introduced.

## Test evidence

Dedicated test runtime ovg-remediation018-postgres (127.0.0.1:54332 only),
separate artifact directory /opt/openvietgis-agent-r007/dist/r007-integrity/artifacts.
Coordinated exclusive DB slot; released after tests. No production, original
audit DB or house-numbering branch mutation.

```sh
uv sync --locked --offline --project apps/api
uv run --locked --offline --project apps/api python -m pytest apps/api/tests/unit/test_query_domain.py
# With OPENVIETGIS_TEST_DATABASE_URL set to synthetic 54332,
# OPENVIETGIS_ARTIFACT_STORE_DIR as above and OPENVIETGIS_LIVE_OIDC=0:
nice -n 10 uv run --locked --offline --project apps/api python -m tools.run_with_test_database pytest \
 apps/api/tests/integration/m2/test_query_integrity.py \
 apps/api/tests/integration/m2/test_r006_r009_real.py \
 apps/api/tests/unit/test_query_domain.py --junitxml=dist/r007-integrity/m2-unit.xml
nice -n 10 uv run --locked --offline --project apps/api python -m tools.run_with_test_database pytest \
 apps/api/tests/integration/m2/test_query_integrity.py::test_typed_decimal_literal_and_revision_paging \
 --junitxml=dist/r007-integrity/typed.xml
```

- Unit domain 26 passed. Focused combined run 30 passed, 1 fixture setup failed
  because R006 requires complete nonnullable properties on update. Corrected
  fixture payload, reran one test: passed. Thus 31/31 collectively before the
  final drawn topology safety tightening, not a single all-pass report.
- Real DB oracle checks distinct 1.000000000000000001/1.000000000000000002,
  numeric comparison, literal "%_" and Vietnamese case behavior, NOT/NULL
  semantics, empty text, Boolean false, between, equivalent timezone offsets.
- Traversal of four features through four one-row pages with duplicate sort
  rank returns exactly a,b,c,d. Missing query pin, changed sort/schema,
  actual target edit, actual reference edit all invalidate continuation.
- Boundary-only point contact intersects but not within; contains direction
  verified; drawn valid polygon and malformed bowtie, explicit CRS requirement,
  authorized same-Project reference and unauthorized substituted ID, missing
  reference feature and 4,000-feature oversize reference set verified.
- Saved definition reopens/replays expected feature; invalid reference/sort
  saves reject. Wrong actor denied query and saved-list access.
- Analytic equatorial projected rectangle (0..200m) transformed to 4326
  contains 0.001° point but not 1° point; reports epsg-1024-inverse. Unsupported
  CRS rejected. Additional nonzero-signed-area projected self-intersection
  regression included for the final combined-candidate gate.
- Original M2 query/processing/cartography regression passes; exact current
  full candidate regression and browser UI acceptance remain assigned to root.

## Residual boundaries

No historical snapshot retention, query-wide selection algebra/consumer
manifest, total request wall-clock/p95/concurrency benchmark, trusted
fixture-dependent datum transformations, full multipart oracle or browser
state/cancellation claim. The per-statement timeout is not a total request
wall-clock guarantee (cross-CRS reference transformation currently verifies
each geometry separately). Original specification requires independent
approval of workload, precision and numeric budgets before release acceptance.
No production deployment.
