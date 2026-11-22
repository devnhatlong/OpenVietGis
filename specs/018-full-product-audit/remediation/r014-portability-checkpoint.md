# R014 scoped extension data lifecycle and portable copies — 2026-11-22

## Candidate and scope

Code checkpoint `303b46ef22772955713f3a4176a955879bdc05d9` on isolated
`fix/018-next-r014` from `cb839d3`. Source requirements remain the original
scope-approved draft, not an accepted installation/SDK plan:
`git show 7bb9879:specs/014-module-framework/spec.md`.

- Migration `0019_extension_history` extends the existing tenant/project-scoped
  extension records, adds immutable record snapshots, activation events and
  portable-copy receipts, with forced RLS and append-only application grants.
  Existing rows get one explicit legacy baseline snapshot; previous unrecorded
  revisions and unpinned source revisions cannot be reconstructed. Downgrade
  refuses to silently discard histories after new events/records.
- Module registry is tenant metadata, not installation-level code approval.
  The internal declared-schema path validates bounded objects, typed attributes,
  semantic versions, permissions, capabilities and commands. No arbitrary code
  loading or permission grant by a module. A separately authorized project
  manager can transition to a registered newer compatible same-major manifest
  with the identical entity/permission/capability/command contract and a current
  manifest CAS. Changes to schema/permission contracts, downgrades, stale and
  conflicting transitions reject before mutation. Existing records retain their
  original historical manifest references.
- Record updates require current project edit authority and active compatible
  manifest, compare both record revision and manifest ID, retain typed/null
  semantics, current actor, timestamp, prior/current revisions and linkage.
  Links require explicit accepted Core layer/feature/source-content/schema/CRS
  pins. Changed pins cause conflict. Extension workflows never mutate Core
  spatial data implicitly.
- Disabled modules expose authorized retained data/history and portable export
  without executing module code. Export contains the manifest schemas, record
  IDs, current values, snapshots, ownership, activation history and Core link
  pins plus canonical payload SHA-256. Complete-or-reject bounds: 2 MiB bundle,
  200 records, 1,000 revisions, per-record and schema caps. SHA-256 detects
  content changes; it proves neither sender identity nor custody.
- Import is an atomic authorized *copy*, not restoration of trusted origin
  audit events. Active target manifest and matching version/contract are
  required. Same-scope Core link pins must still match current Core; linked
  cross-scope remapping is refused. New destination IDs, attribution and
  revision 1 use the current actor. Origin metadata is explicitly unverified.
  Exact digest retry returns the scoped existing receipt under current access
  and active version, without duplicating data. Incompatible/malformed or
  over-limit imports reject as a whole.
- SDK and `ExtensionWorkbenchPanel` expose typed schema forms, Core link
  confirmation, CAS editing/history, activation/version history, labeled
  deactivation and download/import with an explicit copy receipt. This is
  API-backed UI; browser acceptance was not performed in this branch.

## Verification

Actual isolated synthetic Postgres/PostGIS `ovg-next018-postgres` 54334.
No production, audit database or house-numbering package changed.

```sh
# OPENVIETGIS_TEST_DATABASE_URL set to guarded dedicated synthetic 54334
# OPENVIETGIS_ARTIFACT_STORE_DIR set to branch-private artifact directory
# OPENVIETGIS_LIVE_OIDC=0
uv run --locked --offline --project apps/api python -m tools.run_with_test_database pytest \
 tests/modules/test_extension_portability.py \
 apps/api/tests/integration/m3/test_independent_lifecycle.py \
 tests/modules/test_reference_modules.py --junitxml=dist/remediation-r014/real.xml -x -q
```

The recorded run used the pre-relocation path
`apps/api/tests/integration/m3/test_extension_portability.py`; the same tests
now live under `tests/modules` to respect the Core runtime scope guard.

Actual result: 0018_production_ops → 0019_extension_history succeeded;
**5 tests passed**, no skipped/failing cases. JUnit:
`/opt/openvietgis-next-r014/dist/remediation-r014/real.xml`.

- House-numbering reference: actual Core point import, typed address record,
  explicit feature revision/CRS pin, two authenticated actors with grant,
  history actor/values/pin, stale record CAS and changed Core revision rejection,
  disable blocks edits while read/export retained, cross-tenant read denial,
  revoke closes prior access, linked cross-tenant copy rejected.
- Independently registered land/asset reference: typed attributes and retained
  export, unauthorized copy failure, malformed bundle atomic failure, separate
  tenant authorized copy and exact retry receipt, copied origin marked
  unverified, explicit forward-compatible transition, stale and incompatible
  changes rejected; no house module required.
- Legacy independent reviewer/module lifecycle and separate reference module
  tests pass on the migrated guarded database.
- Domain tests `apps/api/tests/unit/test_extension_history_domain.py`: **12
  passed**; Ruff and targeted mypy (4 source files) clean. SDK platform contract
  tests **2 passed**; SDK/web typecheck and lint pass using pinned offline Node
  deps. Patch whitespace check clean.

## Requirement boundaries (not approvals)

Partial evidence for FR-001/003/004/007/010/011/012/013/014/015/016/018/019,
SC-001/003/004/006/007. FR-002/005/006/008/009/017/020/021 and SC-002/005/008
remain incompletely verified or unverified by this slice; see each source
requirement's full wording before any acceptance decision. Remaining:

- Actual installation operator approval and permission registration/policy,
  independent per-permission and deferred execution gates; no user-provided
  executable module path or public runtime compatibility claim.
- Arbitrary schema/data migrations, dependency graph semantics, interruption
  and verified recovery of module schema versions, lifecycle concurrency and
  full negative compatibility matrix. Tested metadata-only transition is not
  schema migration acceptance.
- Complete independently approved reference spatial workflows including
  locate/query/select through Core, clean Core-only install/dependency/runtime
  matrix, full browser and scope/authorization matrix.
- Unbounded portable data transfer or pagination, trusted signed origin,
  cross-project linked mapping, complete legacy historical pin reconstruction.
  Import is copy, not exact-ID restore; audit history is exportable but not
  forged into the destination's authoritative history.
- Public SDK stabilization remains blocked, separate proposal/review required.
  No production deployment or release certification.
