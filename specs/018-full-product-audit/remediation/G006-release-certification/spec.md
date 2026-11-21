# G006 — release certification and dependency truth

**Parent**: R015 / audit 018 G006. **Status**: scoped remediation of the existing source finding, not approval of a new release profile or commercial policy.

**Source requirements**: original immutable R015 draft `3831db0:specs/015-production-readiness/spec.md`, FR-014, FR-015, FR-017–018, FR-020–021, SC-008–009. Constitution III, V, VI; [audit source finding](../../evidence/source-gap-review.md).

The former API and Prometheus gauge asserted fifteen enabled release groups regardless of exact candidate, profile, scope or evidence. Healthy database/storage checks and configured entitlement fields are also not proof of production acceptance.

## User stories and acceptance

1. **Release operator**: see the complete stable R001–R015 inventory, distinguish each group's release certification from its implemented runtime operations, and see a blocked production profile when exact acceptance is missing. A count of inventory groups is not an accepted count.
2. **Operator diagnosing dependencies**: distinguish PostgreSQL, PostGIS and configured artifact storage availability with bounded, non-destructive, sanitized failure signals. Healthy dependencies never imply release readiness.
3. **Organization owner/admin**: configure optional commercial metadata without granting permissions or deleting project data. Ordinary members cannot modify organization configuration. Requested quotas/features MUST be identified as metadata only while the commercial enforcement policy remains unapproved.

## Functional requirements

- G006-FR1: Return the fifteen stable roadmap IDs exactly once with explicit certification state and reason for evidence absence. No positive certification from static flags, liveness or passing subsets of tests; no mutation of runtime operation authorization.
- G006-FR2: Expose the selected proposed profile as unverified until a separately reviewed acceptance record pins the exact candidate and profile. Report `production_ready=false` while mandatory gates remain open.
- G006-FR3: Metrics and API MUST agree on inventory vs certification count.
- G006-FR4: Missing or unavailable dependencies MUST return safe not-ready state; probe unique disposable files and do not create a replacement store or clobber existing files.
- G006-FR5: Entitlement reads/writes remain tenant scoped; mutation requires organization settings authority and attributable audit. Unknown/duplicate roadmap IDs and out-of-range integer fields are rejected. Entitlement metadata is not resource authorization, certified profile identity, quota enforcement or deletion policy.
- G006-FR6: Provide a read-only repeatable release preflight that fails closed when exact candidate acceptance is absent. It does not create a verification record, promote a branch or certify a deployment.

## Out of scope

- Implementing an approval authority or positive release certificate without approved profile criteria, full CI, reviewer/human evidence and an approved record format.
- Deploying or promoting any branch; changing the approved user workflow, commercial policy, quota/billing enforcement, R010 adapter scope, R015 backup policy, or 016/017 UI implementation.
- Treating release certification as a kill switch for otherwise authorized development/test operations.
