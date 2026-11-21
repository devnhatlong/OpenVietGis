# 018 convergence comparison and release handoff — 2026-11-21

Read-only source/ancestry review from the isolated `fix/018-release-convergence` worktree. This is the T024 comparison, not a completed integration or user acceptance. The original frozen 018 evidence and active UX worktrees remain unchanged.

## Exact branch comparison

| Ref | Observed SHA | Implication |
| --- | --- | --- |
| main | c5cc5a9d47b611334327805cf5516782ecfb84cb | Earlier verified main, not the later product candidate |
| integration/r006-r015-complete | c6d449fc0ead93e259b79b87e63c1c894bd16c93 | Frozen audit candidate; 27 later commits than main |
| fix/018-confirmed-blockers (base used) | 596fb13 | Initial R008/R010/R015 repairs on audit branch lineage |
| impl/frontend-ux-current-dev | 4b82daba45262c1893b24eab11b928fa09903d4a | Separate R002/R004 UX child slices 016/017, not part of frozen candidate |
| fix/017-mobile-sheet-focus | cb26e7440a59393bb524e620e99b3710c6dbe568 | Parallel mobile fix branch; divergence at 8a3204c; current UX already contains mobile-exclusive fix 046640d |

`git merge-base 596fb13 4b82dab` returns exactly c6d449fc0ead93e259b79b87e63c1c894bd16c93. The UX diff relative to that ancestor touches 95 web paths, 30 E2E paths, 21 UX spec paths, Keycloak dev realm and Playwright config, **no API source paths**. Only shared changed path with the initial 596fb13 remediation is `apps/web/src/features/platform/PlatformHubPage.tsx`. Read-only `git merge-tree` with d8c6927 and 4b82dab identified one conflict in the external connection list: the remediation's lifecycle/unverified disclosure vs localized read-only text on UX. Preserve truthful provider state after integration. Also reconcile the R015 badge: certification is not a runtime switch. Keep 016/017 localized label changes and the parent R010/R015 truth semantics; replay current UX tests against the final common runtime candidate.

## 016/017 evidence status (not rerun here)

- **016 App Shell/Identity UX** on the UX branch has 48/48 task boxes checked, prior recorded automated convergence and a historical 31/31 non-bootstrap browser suite + 1/1 bootstrap, 60 web tests, 62 SDK tests, 538 Python checks and 273 pass/1 skip integration/performance. This evidence belongs to its earlier UX snapshot, not to the new remediation branches. R002 SC-013 human observation is not satisfied.
- **017 GIS Workspace UX** has 54/57 tasks checked. T053 recorded benchmark on exact SHA 8a3204c991cd04979af96d14d26ff062a844bf07 (10,000 features; p95 2,299.48 ms map-open, 306.60 ms select/inspect; budgets 3,000/1,000 ms). Later 34fa854, 046640d, 77c7054 fixed a fixture, responsive sheets and loading/command states; T055 parent regression checkpoint records 8/8 browser tests and 88 web/62 SDK tests, lint/typecheck/build. T054 (quickstart complete), T056 (all exact full validation), T057 (independent convergence) remain **open on 4b82dab**.
- Parent R004 SC-009 still requires human observation; neither UX child removes this. R005 SC-008 is also open.
- Do not cherry-pick stale mobile-only branch blindly; current UX incorporates the relevant fix by a different commit.

## Release gates after remediation

| Gate | Evidence at this checkpoint | Required before acceptance |
| --- | --- | --- |
| G006 static false-enabled claim | [G006 unit + real integration evidence](G006-release-certification/evidence.md) | Integrated FE/SDK labels, exact integrated retest; no positive release certification yet |
| G001 candidate ancestry | exact branch comparison above | coordinate common integration candidate, independent security/review, all CI checks on exact commit |
| G002 requirements restoration | 656 original requirement rows preserved under audit 018 | row-by-row reviewed accepted scope and exact evidence; no task count inference |
| G003/G005/G007 | known graphical editing, true disconnected client and advanced browser coverage limitations | demonstrate required workflows or explicitly approve a smaller release scope |
| G004/G009/G010 | separate agent remediation tracks | review and rerun on common candidate; do not extrapolate their branch tests |
| G008 human observation | R002 SC-013, R004 SC-009, R005 SC-008 not observed | real independent human evidence or release remains blocked |
| R015 profile | dependency readiness and synthetic recovery are not profile acceptance | approved install/upgrade/storage/limits/RPO/RTO and protected recovery/auth reconciliation; exact verification record |

Additional source evidence of profile incompatibility: `infra/prod/docker-compose.prod.yml` declares `OPENVIETGIS_ENVIRONMENT=production`, whereas Settings supports only development/test and `test_settings_reject_unknown_environment` deliberately asserts production rejection (the 4 config tests passed). Compose omits the required `OPENVIETGIS_DATABASE_URL`; the production web Dockerfile uses Node 22 whereas locked root engines and CI require Node 26. No profile deployment was attempted, and these are not silently bypassed. A proposed production container profile is not an accepted one.

## Required common-candidate acceptance sequence

1. Integrate reviewed scoped commits and current approved 016/017 branch in an isolated integration candidate; preserve the conflict resolution and verify no dependency or API/SDK contract downgrade. Do not alter active worktree ownership.
2. Run full mandatory test and quality gates, including exact frozen dependencies, migration/runtime role, contract generation, scope, architecture and redaction. Record exact candidate SHA, test environment/profile, tests and negatives.
3. Run real synthetic M1/M3 end-to-end scenarios, targeted advanced workflow tests and R016/R017 convergence on the same candidate, including live OIDC and stateful browser acceptance; repeat required benchmarks without introducing new approved scope.
4. Independently approve any remaining capability exclusions/required profile limits. Obtain manual gates and independent code/security/release review, including complete verified backup/recovery and authority reconciliation.
5. `uv run --project apps/api --locked --offline python tools/check_release_gate.py` currently declines release. It is an explicit fail-closed preflight, not authority to create a certification or promotion. Only an independently verified exact candidate/profile record can permit a later acceptance decision.

No M3 certification, main promotion, deployment or commercial approval is implied.
