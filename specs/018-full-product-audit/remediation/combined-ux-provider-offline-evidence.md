# Combined UX, restricted provider, and field offline candidate

Candidate: `fix/018-ux-convergence`, isolated worktree only; no production mutation, push, deploy, or acceptance sign-off.

## Integrated source

- Existing canonical R016/R017 merge and release-truth checkpoint: `0a19e2619d97da2f3ce1c27501c7d277dea52a14`.
- Root remediation through COGO `caccfb3`, merge `f2a73d770b270653270e51426fcb7cbbba2739d5`.
- R010 restricted WMS/WFS provider sample behavior, cherry-pick `64e373a`. Kept existing localized status truth and added preview without calling provider data native storage.
- R013 scoped offline snapshot, local draft persistence and sync, cherry-pick `f6ffd57`. Conflict resolution keeps canonical protected routes and puts the dedicated offline workspace outside the online-only layout; confirmed account changes and authorization loss lock the offline marker in SessionBoundary. Both logout entry points lock it before network acknowledgement. The platform field tab routes to the actual workspace rather than creating a hard-coded package.
- R013 static-only offline browser fixture `243d8f8`; browser evidence/fixture follow-up from source agent `fe06f3e9bb971e4bdff7b44072fab549e4501b81`.

## Verification on integrated source

At runtime revision `243d8f8`, pinned Node/Pnpm, offline-installed lockfile dependencies, nice level 15, one test worker:

| Check | Result |
| --- | --- |
| SDK lint | PASS |
| SDK TypeScript | PASS |
| SDK Vitest | PASS, 62 tests / 15 files |
| Web lint | PASS |
| Web TypeScript | PASS |
| Web Vitest | PASS, 97 tests / 22 files |
| Web production build | PASS, generated offline static shell |
| Architecture, accepted scope, documentation, patch-whitespace checks at `fe06f3e9` | PASS |

The build has the existing chunk-size warning. This candidate's checks did not execute a browser or database, because those isolated slots were reserved for the respective implementation agents. The offline evidence follow-up changes fixture/docs/tests only; its independent browser and backend outcomes are documented in [R013 checkpoint](r013-offline-client-checkpoint.md). Neither those independent outcomes nor static verification constitute a full integrated release gate. Re-run representative integration and browser acceptance on the ultimate integrated candidate, review remaining R010, R012, R013 limitations, and leave restricted release status unchanged until all applicable gates and evidence pass.
