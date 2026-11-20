# R015 — Production & Commercial Readiness

**Parent roadmap**: [ROADMAP.md — R015](../../ROADMAP.md#r015)

## Scope & First-Slice Verification

- Database migration (RLS-enforced): `apps/api/migrations/versions/0018_production_ops.py`
- Automated verification suite: `apps/api/tests/integration/m3/test_r015_ops_real.py`
- Browser E2E verification: `tests/e2e/platform-m2-m3.spec.ts`
- Status: automated verification passing on VPS `integration/r006-r015-complete`.
