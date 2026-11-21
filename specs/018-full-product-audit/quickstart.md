# Audit quickstart
1. Verify isolated worktree and exact candidate SHA; verify other active worktree ownership; inspect ROADMAP, Constitution, ADRs, original approved specs and prior decision register. Keep the baseline immutable during audit.
2. Establish a disposable synthetic test DB/artifact store, unique service ports and test realm; verify test guard rejects production/default DB. Do not restart shared services or modify production configuration.
3. Run existing project validation via documented package scripts and frozen dependencies. Capture exact commands, versions, SHA, logs, failures and skipped cases; do not relax age/pin or security checks.
4. Use synthetic point/line/polygon and CRS/format fixtures for M1, M2. Compare results against independent control geometry/format tooling. Verify persisted values after reload, deny other tenant accesses.
5. Exercise M3 two-user, local OGC responses, DXF conversion/loss, disconnected/reconnected client, two-module workflows and isolated backup/restore. Confirm actual output; mark missing flows partial/blocked.
6. Populate status-matrix.md and gaps.md per evidence contract; classify each requirement. Scope any remediation as child Spec Kit work. Do not deploy or promote audit candidate.
7. Run independent review, convergence and exact-candidate full validation; manual observation and owner-approved release scope required before external release.
