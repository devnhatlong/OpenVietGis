# Baseline checkpoint — 2026-11-21
- Frozen audit runtime candidate: c6d449fc0ead93e259b79b87e63c1c894bd16c93 (integration/r006-r015-complete). Original branch retains 35 staged/unstaged/untracked paths observed in its worktree; no edits made to them.
- Verified main: c5cc5a9 (historical exact green CI), not the later candidate; candidate was 27 commits ahead at source inspection.
- Isolated docs audit branch: ed1b1d76de2d9c2dedc6f7e2fbdee3982fa85d7f, parent exactly candidate; worktree on VPS clean at transfer, active feature set to 018-full-product-audit. No public push, main promotion or deploy performed.
- Separate frontend implementation worktree observed at 6863d8c, with one modified E2E file, plus separate mobile focus fix at 8a3204c. Preserve current owners and retest only after isolated integration.
- Host tools observed: Python 3.13.5, Node v26.13.1 portable toolchain, Docker 26.1.5. These are not proof of an approved frozen test runtime. Dedicated fixture database, realm, artifact guard and dependency validation remain T007–T009.
- Spec Kit matching tracked tree 1fda0caa4ec96c2701ab6c2d54f1a04134e28e76; actual PowerShell resolver, plan/tasks setup and prerequisite checks completed on isolated Windows worktree, with process-only RemoteSigned. VPS Debian does not expose PowerShell. Bundle verified and exact commit transferred privately; documentation checks and diff whitespace passed.
- Original R006–R015 draft refs imported by verified incremental Git bundle, without overwriting code or publishing user data. Their precise source commits are in requirements.md.
