# G006 remediation plan

**Base**: remediation checkpoint 596fb13, isolated worktree fix/018-release-convergence.

## Design

- Immutable roadmap inventory in `domains/ops/domain.py`, fresh report generated per request. The compatibility field `enabled` denotes release certification, not runtime feature availability. Report explicit profile status, accepted count, verification-record and candidate absence. All groups remain unverified pending exact-candidate release acceptance.
- HTTP adapter and Prometheus derive consistent certification counts from a single report. `/ops/health/ready` remains a dependency-only health probe and returns 503 on controlled dependency failure.
- Artifact readiness probes exclusively created temporary file handles in the configured store; no local replacement when missing. Do not return exception text.
- Entitlement repository checks current effective `organization.manage_settings` permission at write boundary; read requires organization.read. Audit metadata records the configuration update in the same transaction. Requests remain metadata only.
- `tools/check_release_gate.py` checks exact source identity and mandatory evidence-bearing inventory consistency, returns nonzero when certification is absent. CI ordinary test collection exercises negative gate tests; this command is a separate release preflight, not routine development CI certification.

## Constitution check

Platform isolation preserved; no reverse domain-module dependencies. Tenant isolation uses existing authorization/RLS; no quota/entitlement privilege expansion. CRS/data/operation semantics unchanged. Attributable config mutation via existing audit contract. Capability certification explicit and distinct. No deployment. No new dependency.

## Verification

Focused unit tests for inventory immutability, readiness success/failure, safe probe, sanitization, Prometheus consistency, false all-true flags, missing/duplicate IDs, candidate/profile mismatches. Real restricted-runtime integration via dedicated synthetic 54332 fixture: owner requests, ordinary member denial and outsider isolation, invalid feature list rejection, non-destructive downgrade + audit; real HTTP 503 missing store. Run Ruff, targeted mypy and existing static contract/scope/architecture/docs checkers.

Full exact-candidate CI, independent reviewer and mandatory human acceptance remain separate pending gates; no production certification in this remediation.
