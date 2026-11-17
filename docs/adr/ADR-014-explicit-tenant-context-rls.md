# ADR-014: Explicit Tenant Context with RLS Defense-in-Depth

**Status**: Accepted
**Date**: 2026-11-18

## Context

OpenVietGIS is multi-tenant. A user may belong to multiple Organizations, so implicit or sticky
tenant context creates a high-risk cross-tenant failure mode. Application authorization is required,
but the database should also defend tenant-sensitive rows from accidental unscoped access.

## Decision

Organization is the explicit tenant boundary.

For protected tenant requests:

1. derive actor identity first;
2. receive the target Organization explicitly from the resource/API context;
3. validate the actor's membership or Service Principal relationship;
4. create a short-lived AuthorizationContext;
5. set transaction-local database tenant/actor context;
6. execute authorized repository work inside that transaction.

Use PostgreSQL RLS selectively on tenant-sensitive tables. API traffic uses a dedicated runtime
database role that is not superuser and does not have BYPASSRLS. Migration/ownership work uses a
separate role. Protected tables use FORCE ROW LEVEL SECURITY where appropriate.

Tenant settings are transaction-local, never persistent session settings on pooled connections.

RLS is defense-in-depth and does not replace application AuthorizationService permission checks.

## Consequences

- Cross-tenant repository mistakes are more likely to fail closed.
- Pool reuse cannot retain tenant context after transaction completion.
- Tests must exercise the actual non-BYPASSRLS runtime role; testing as table owner/superuser is not
  sufficient evidence.
- A small number of pre-tenant/global paths (identity resolution, self-membership discovery,
  bootstrap) require explicit narrowly-scoped handling.
- Background jobs introduced later must carry the same Organization and actor context explicitly.
