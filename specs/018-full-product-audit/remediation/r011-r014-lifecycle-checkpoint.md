# R011 / R014 independent lifecycle remediation checkpoint

Base: fix/018-confirmed-blockers at 596fb13. Synthetic dedicated VPS DB
ovg-remediation018-postgres, port 54332. No production or frozen-audit changes.

## R011 collaboration
- Assignment requires active human membership and current project edit permission
  consistent with the existing R002 role rules; assignment cannot grant access.
- Only the assigned current human reviewer may decide. A completed decision
  cannot be overwritten; recorded activities preserve the decision. Post-commit
  review remains distinct from changing spatial data.
- Independent test uses two separate authenticated actors: assignment denied
  before grant, then owner assigns editor, owner cannot decide in their place;
  reviewer comment and decision preserve actor, second decision denied, revocation
  denies reading/commenting/deciding despite historical assignment.
- Original draft R011 FR-024/026/027/029 partial; reassign/unassigned review,
  dedicated review permission model and broader activity privacy still require
  approved scope and evidence.

## R014 module lifecycle
- Tenant manifest metadata registration requires a current human organization
  settings administrator (not installation-level approval). Project activation
  and deactivation require project.manage; both emit attributable audit events.
- Active version is pinned. An implicit migration or downgrade is refused;
  reactivation of the same version retains data and activation identity.
- Creation checks active/enabled compatible manifest and scoped existing active
  layer/feature links. Authorized existing records remain readable when disabled,
  without running the module. Cross-tenant reads and editor lifecycle changes fail.
- Original draft R014 FR-003/007/011/012/019 partial; installation-level approval,
  explicit module permission grants, verified migration/recovery, full portable
  schema/history and standalone reference workflows remain unfinished.

## Verification
`apps/api/tests/integration/m3/test_independent_lifecycle.py` (2 tests) plus
`apps/api/tests/integration/m3/test_r015_ops_real.py` (2 existing tests):
4 passed on isolated PostgreSQL/PostGIS; JUnit
`dist/remediation018/r011-r014.xml`. Ruff and git diff --check passed.
Not external release acceptance.
