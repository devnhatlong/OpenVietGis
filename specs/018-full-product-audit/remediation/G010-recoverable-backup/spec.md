# Feature Specification: R015 recoverable database and artifact snapshot

**Status**: Draft child remediation; branch/feature number pending coordination.

**Parent**: 018 G010, original R015 FR-010–013, SC-004–005.

**Baseline**: c6d449fc0ead93e259b79b87e63c1c894bd16c93; [reproduction](../../evidence/r015.md).

## User scenarios and acceptance

### US1 — Restore a complete project snapshot (P1)
An authorized operator creates a recovery set representing one documented consistency point, including required immutable source and published artifact bytes, and restores it in isolation without requiring the original artifact store.

Independent test: seed synthetic GIS imports, outputs and packages; back up DB plus artifacts, restore into new DB and empty artifact root. Verify all required references/checksums and download/open representative artifacts, compare data/revisions/geometry and report access conditions.

1. Given an accepted snapshot, when the original artifact root is unavailable to the isolated restore, then every required artifact is restored from backup, checksum verified, references resolve and representative workflows work after reconciliation.
2. Given missing, corrupted, tampered, inconsistent, traversal or unauthorized content, when validation/restore runs, then recovery cannot be certified, readiness fails closed, and no existing data is overwritten.
3. Given snapshot predating credential/session/grant revocation or an interrupted publication, when restored, then prior authority is not usable until current reconciliation and jobs cannot publish unauthorized/duplicate results.

### US2 — Reproducible operator evidence (P1)
An operator receives a protected manifest and measurable recovery report including consistency point, version, scope, data age, duration, required/expected-expired assets, integrity and authorization checkpoints. No claim of production RPO/RTO before selected profile targets are approved.

## Functional requirements
- FR-001 Include structured tenant data, schema/version, revision/authorization state, job/publication state and all required immutable source/derived bytes at one consistent recovery point.
- FR-002 Produce versioned manifest of snapshot identity, scope, DB and asset path identifiers, byte size, checksum and lifecycle; expected unavailable/expired content explicit. Store with appropriate access protection and configured encryption requirements.
- FR-003 Validate manifest integrity and completeness before certification; bounded safe path handling, reject symlinks/traversal/tampering, never restore over a live DB or artifact root.
- FR-004 Restore to freshly isolated DB and artifact store with no original-store dependency; independently compare data/geometry/revisions and artifact references/bytes and execute representative authorized workflows.
- FR-005 Reconcile current authorities fail-closed; do not revive old grants, sessions, service identities or credentials; reconcile interrupted jobs before execution/publication.
- FR-006 Report missing/corrupt/partial backup, mismatched logical snapshot, failed reconciliation and recovery duration/data age; do not mark profile ready absent approved limits and passing gates.

## Success criteria
- SC-001 100% required source/derived artifacts present and byte-identical in fully independent restore; no dependence on original artifact root.
- SC-002 Database counts/digests, source/asset references, tenant boundaries and representative workflow outputs match agreed consistency point.
- SC-003 Every missing/corrupt/truncated/inconsistent/unsafe artifact negative fails certification, no production overwrite and no unauthorized access.
- SC-004 Pre-revocation and interrupted job recovery tests fail closed until reconciled; no revived authority/duplicate valid outputs.
- SC-005 Recovery report records elapsed duration and data age against approved profile values; no blanket readiness claim.

## Non-goals
No production backup now, no customer data/credential extraction, no recovery of unprovided historical assets, no commercial cloud design, no automatically approved RPO/RTO.
