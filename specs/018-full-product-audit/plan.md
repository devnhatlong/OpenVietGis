# Implementation Plan: Full Product Audit R001–R015
**Branch**: audit/018-full-product-audit | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

## Summary
Freeze the actual VPS candidate, reconstruct requirement traceability, execute independent M1/M2/M3 workflows, rank defects and open scoped remediation specs. This is a documentation/evidence audit of an unpromoted integration candidate, not a new product feature or a substitute for verified main.

## Technical Context
- Baseline: integration/r006-r015-complete at c6d449fc0ead93e259b79b87e63c1c894bd16c93; verified main c5cc5a9. R016/R017 frontend work remains separate.
- Stack: FastAPI/Python, SQLAlchemy/PostgreSQL/PostGIS, GDAL/OGR, MapLibre/React/TypeScript, ezdxf, Pillow, Keycloak; exact versions record in evidence at execution.
- Testing: existing pytest real database, SDK/web tests, Playwright, independent geometry/format oracle, security/permission and recovery checks. Never substitute a route, mock, or static readiness flag for the actual outcome.
- Target: isolated Linux test runtime, synthetic point/line/polygon and raster/OGC fixtures; separately validate supported release profile. No live operation against production tenant or shared writable database.
- Performance: reuse each approved spec budget and benchmark profile; where absent, record missing requirement and create scope decision before acceptance.
- Storage: audit reports only; no new product table/API. Retain redacted evidence files and checksums.

## Constitution Check
PASS design: module independence (R014), portability (R005/R012), tenant isolation (all), explicit CRS (R003/R005/R008/R012), revision/audit (R006/R011/R013), real capabilities (all; no static acceptance), web-native workflows (R004/R016/R017), workflow value (M1–M3). Rerun at convergence. No amendment. Production mutation, deployment, bypassing frozen dependency policy, overwriting other worktrees, or accepting unapproved scope are prohibited.
The audit branch is deliberately pinned to the candidate under review, not an implementation branch from main. Any product remediation integrates via approved feature/child branches and exact green validation.

## Project Structure
- specs/018-full-product-audit/{spec,plan,research,data-model,quickstart,tasks,status-matrix,gaps}.md
- specs/018-full-product-audit/contracts/evidence-contract.md
- specs/018-full-product-audit/checklists/requirements.md
- specs/018-full-product-audit/evidence/ (redacted manifests/reports, not sensitive fixtures)
- Existing product: apps/api/openvietgis_api, apps/web/src, packages/client-sdk, tests/e2e, tests/modules, apps/api/tests/integration, infra/prod, tools.
- Original requirement authority: ROADMAP, Constitution, ADRs, detailed upstream specs and approved draft/decision registers; draft != accepted scope. Do not erase or silently replace stubs with guessed scope.

## Execution phases
1. Baseline, ownership and requirements reconciliation (US1).
2. Isolated readiness and M1 (US2).
3. M2 and frontend integration (US3).
4. M3 and capability truth (US4).
5. Gap backlog, child spec dispatch, independent review, final exact-candidate evidence (US5).
Gate: no promotion until exact candidate full CI, independent review, convergence and required human gates. No deployment under audit-only authorization.

## Complexity Tracking
None. Auditing an integration candidate does not amend the verified-main implementation rule.
