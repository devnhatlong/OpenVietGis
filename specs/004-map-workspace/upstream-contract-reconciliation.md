# R004 upstream contract reconciliation — checkpoint 2026-11-19

Status: **read-only upstream reconciliation; not Plan/Tasks acceptance or runtime implementation**.

Verified baseline: local clean `integration/004-on-verified-main` at `42efe56`, parent verified `main` `c5cc5a9`. R003 exact-main CI #44341205122 passed. This note supersedes only the stale dependency-status descriptions in `research-preparation.md`; it does not amend the accepted product scope.

## Confirmed from committed upstream contracts

- R002 `specs/002-identity-organization-tenancy/contracts/permission-registry.md`: server-side authorization is expressed as stable permission codes, not UI role-name checks. `project.read`, `project.edit`, `project.manage` have distinct meanings; inherited grants and service-credential permission ceilings must be honored. Shared map configuration mutation needs an explicit reviewed mapping to these existing permissions, without inventing a role bundle.
- R003 `specs/003-spatial-catalog-crs/contracts/catalog-semantics.md` and `spatial-catalog-api.yaml`: source/layer operations use Project-scoped permissions and explicit catalog semantics. R004 must reuse accepted source/layer identities, revision pins and authorization rather than create parallel catalog semantics.
- R004 draft `spec.md` and `research-preparation.md`: one logical Project map; explicit Save; transient personal camera separate from saved startup viewpoint; local blank/grid basemap by default; bounded rendering, selection and inspection; no advanced query/editing/import in this slice.

## Remaining gates before Spec Kit Plan/Tasks

1. Read actual R002/R003 runtime route/service implementations and current OpenAPI to establish exact reusable Project authorization, Layer/Source/Feature detail, revision and stale-read behavior. Record file/route references, not speculative API names.
2. Decide and independently review the R004-only shared map configuration contract: expected revision, atomic commit, idempotent save intent, lost-ack reconciliation, safe change history and archived-Project behavior.
3. Define bounded viewport read and renderer-neutral MapEngine adapter semantics; reconcile CRS/profile and render eligibility against the accepted R003 fixture and capabilities.
4. Confirm review ownership and absence of a concurrent R004 worker before editing plan/contracts. Run Spec Kit Plan/Tasks only after these evidence gates, then isolated test-first implementation and exact-SHA CI.

No task completion, release, integration, CI dispatch or downstream R005 implementation is claimed by this note.
