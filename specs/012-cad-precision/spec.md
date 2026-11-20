# R012 — CAD Interoperability & Precision

**Parent roadmap**: [ROADMAP.md — R012](../../ROADMAP.md#r012)

## Scope & First-Slice Verification

- Database migration (RLS-enforced): `apps/api/migrations/versions/0015_cad_precision.py`
- Automated verification suite: `apps/api/tests/integration/m3/test_r010_r013_real.py`
- Browser E2E verification: `tests/e2e/platform-m2-m3.spec.ts`
- Status: automated verification passing on VPS `integration/r006-r015-complete`.
