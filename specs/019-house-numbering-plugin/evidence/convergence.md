# HN019 convergence evidence — 2026-11-22

Status: **technical candidate verified; external release gate T007 remains open.**

## Automated convergence

- Python/domain/module integration: **25 passed** in the combined HN + reference-module run.
- HN edge acceptance: **3/3 passed**.
- Batch document acceptance: **100 official plate PDFs generated**, first/last opened as PDF, **>=100** document-issue audit events.
- Architecture guard: **PASS**.
- Accepted runtime scope / MapEngine boundary: **PASS**.
- Architecture tests: **5 passed**.
- Client SDK: **62/62 passed**.
- Web unit tests: **44/44 passed**.
- Module frontend typecheck: **PASS**.
- Web typecheck/lint/production build: **PASS** (only the existing >500 kB Vite chunk warning).
- Browser E2E: **PASS**, including isolated Core + official-module migrations, module activate/disable, all seven UI journeys, and 390×844 mobile viewport.
- Public VPS HTTPS preview: **PASS** on https://vps1.gpcds.site:2087; root/health HTTP 200 and full public Keycloak + US1–US7 Playwright journey **1 passed in 40.0 s**.
- Performance: see [performance.md](performance.md).
- Recovery: see [recovery.md](recovery.md).

## Edge/security evidence

The candidate now exercises real HTTP/PostGIS guards for:

- editor cannot register/activate/disable modules requiring organization/project management authority;
- direct other-organization access denied; inactive sibling project cannot open HN runtime;
- House Numbering and Land Asset coexist in the same project;
- route-side ambiguity, bent-route nearest tie, missing/invalid CRS request and max-distance threshold;
- nested alley prefix;
- stale preview fails atomically and writes no number;
- preview replay is idempotent;
- draft/non-authoritative rule cannot approve;
- stale proposal revision fails;
- rejection requires a reason;
- approved/submitted number locks route direction;
- route deletion with dependencies returns 409;
- duplicate official number is rejected as `NUMBER_OCCUPIED` before the DB unique index;
- 50 offline survey operations apply, replay idempotently, and changed replay conflicts;
- viewer cannot read/export/download private household artifacts.

Three defects were found and fixed before convergence:
1. dependent route deletion used invalid PostgreSQL UNION/LIMIT SQL and returned 500; it now returns a domain 409;
2. duplicate proposed numbers could hit the partial unique index during submit and return 500; route-level serialization + preflight conflict detection now returns 409 `NUMBER_OCCUPIED`;
3. the generic isolated test runner migrated Core but not official modules, allowing the browser to activate House Numbering while its schema was absent; the runner now applies official-module migrations before launching tests, with a dedicated regression test.

## PII leak scan

A clean isolated artifact store ran the US6/US7 test with synthetic markers `demo_resident`, `demo_contact`, and `SYNTH-001`.

- Public namespace `house-numbering-exports`: **no marker found**.
- Private namespace `house-numbering-private-exports`: marker **present**, proving the scan had a positive control.
- Public export API also rejects private field requests and viewer private access/download is denied.

## Remaining release blockers

This branch is not promoted to production. Spec task T007 remains open because exact promoted Core evidence for audit-018 G001/G003/G004/G005 is not yet established. G009/G010 have remediation evidence, including artifact-byte restore, but that does not close the whole exact-Core promotion gate. Human/owner/legal/data-authority gates also remain external.
