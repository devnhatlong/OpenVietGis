# Feature Specification: R008 readable and canonical derived processing output

**Status**: Draft child remediation; branch/feature number to be assigned after coordination.

**Parent**: 018 audit G009; original R008 FR-027, FR-034, SC-001.

**Baseline**: c6d449fc0ead93e259b79b87e63c1c894bd16c93; [reproduction](../../evidence/r008.md).

## User scenarios and acceptance

### US1 — Consume a derived layer (P1)
As a GIS analyst, after Buffer, Clip or Dissolve succeeds I can open, inspect, render, query and export the result under its current pins. The input remains unchanged.

Independent test: run the frozen independent geometry oracle on synthetic point and mask fixtures, then read each published feature through Core, compare count, geometry and attributes to the expected result.

1. Given a 1000 m Buffer request and valid fixture, when the job succeeds, then pinned feature list/detail return canonical typed attributes (e.g. "1000", not "1000.0"), correct CRS, valid polygons and expected geometry.
2. Given valid Clip/Dissolve inputs, when each job succeeds, then its output is consumable and correct independently, including disjoint/overlapping geometries, empty results and source attribution.
3. Given malformed or noncanonical output or denied scope, when publication is attempted, then no ready layer or successful job is exposed and failure is actionable; no partial publication.

### US2 — Safely recover affected existing outputs (P1)
An operator can identify affected derived results and obtain a corrected result without silently changing immutable read pins or input revisions. Repair/backfill policy requires explicit owner decision if historically published content must be replaced; no global rewrite of production rows authorized by this child draft.

## Functional requirements
- FR-001 Canonicalize and validate all derived attributes against declared logical field schema before publication using Core's existing contract; do not weaken read validation.
- FR-002 Ensure published geometry, CRS, dimensions, count, metadata and revision pins agree with the stored content and immutable job input/provenance.
- FR-003 Job success requires consumable output and valid atomic publication; failures leave no partially ready output.
- FR-004 Support regression cases for integer and fractional positive Buffer distances (including 1000, 250, 12.5), approved range limits and invalid parameters; preserve exact accepted numeric semantics.
- FR-005 Verify output read, map viewport/selection, query and supported export under authorization, stale pins and third-party project denial.
- FR-006 Detect existing affected results and report a versioned correction/recompute policy; no silent in-place modification, cross-tenant repair or unsupported CRS expansion.

## Success criteria
- SC-001 Reproduced G009 fails on baseline and passes on new candidate; 100% of supported test cases have canonical attribute/schema match.
- SC-002 Independent geometry oracle passes Buffer/Clip/Dissolve with agreed fixture tolerances; original input pins/values unchanged.
- SC-003 Zero ready partial layers and zero unauthorized/stale reads across explicit negatives.
- SC-004 Existing M2 suite, focused regression, browser render/selection and transfer consumer checks pass on the same new candidate; audit G009 closed only after review.

## Non-goals
No new algorithms, survey-grade accuracy assertion, blanket CRS approval, production repair/deploy, R016/R017 UX redesign or general processing framework rewrite.
