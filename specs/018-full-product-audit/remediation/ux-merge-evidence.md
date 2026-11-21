# 016/017 UX convergence — integrated source and static validation

**Date**: 2026-11-21. **Exact tested candidate**: `54dfd953492127d9e3712a160a8b678769837a6e`, dedicated branch `fix/018-ux-convergence`.

The merge commit has two exact parents: root remediation checkpoint `1ba643db60a8f52a4cd9f08c4bdcc351482e3802` and the current UX candidate `4b82daba45262c1893b24eab11b928fa09903d4a`. Merged in isolated worktree only; the active UX worktree, root candidate and production were untouched.

## Integration resolution

- Only merge conflict: `apps/web/src/features/platform/PlatformHubPage.tsx`. Keep UX localization/shell layout and R010 truthful availability (unverified unless separate provider operation evidence; revoked explicit). Registration notice describes configuration, not a successful retrieval.
- Preserve R015 release inventory distinction in the localized UI: healthy dependencies are not product acceptance; all current inventory capability records explicitly show **Chưa nghiệm thu**, not runtime on/off. Configured entitlement is metadata only, not quota enforcement or access authority. The SDK represents the actual report contract, including nullable verification evidence and explicit dependency scope. Added pure FE regression tests rejecting optimistic legacy flags and unverified profile/connection statuses.
- Updated localized broad M2/M3 browser scenario assertions to distinguish dependency health from release certification and require all fifteen inventory rows explicitly unverified. Browser execution remains pending on the final integration candidate.
- Removed four inherited trailing whitespace lines from the 016/017 requirement checklists to satisfy diff hygiene; no change to requirements.
- Future integration overlap: provider preview branch adds `ExternalSourcePreview.tsx` and overlaps Hub/SDK; retain both. Graphical editor/offline branches overlap parts of UX UI/routes/E2E; preserve canonical shell and labels when integrating their implementation.

## Observed validation

Pinned Node **26.13.1**, pnpm **12.21.0**. Frozen offline dependency install passed: 195 cached packages, zero downloaded, lockfile and supply-chain policy intact. No tracked dependency changes.

| Check | Observed |
| --- | --- |
| Node runtime gate | PASS |
| Client SDK lint / typecheck | PASS |
| Client SDK Vitest | **62/62 PASS**, 15 files |
| Web lint / typecheck | PASS |
| Web Vitest | **93/93 PASS**, 21 files; includes 5 new status safety regressions |
| Vite production build | PASS; JS 1,641.00 kB raw / 454.98 kB gzip, CSS 141.05 / 25.11 kB, worker 519.54 kB; known large-chunk warning |
| Source scope / architecture / docs checkers | PASS |
| Diff hygiene | PASS |

All FE checks executed sequentially at nice 15 with single Vitest worker concurrency to avoid disruption to other isolated agents. No DB, browser, CI, live OIDC or deployment ran in this worktree.

## Remaining convergence

This demonstrates merged source and static/frontend-unit compatibility on 54dfd95. It does not certify the later common candidate after merging other agent branches. The 017 quickstart/browser matrix/full repository/independent convergence gates T054/T056/T057 and mandatory human gates remain open. Rerun exact final integration candidate full CI, supported M1/M3, targeted advanced workflows and 016/017 browser/benchmark/security/acceptance; no automatic promotion.
