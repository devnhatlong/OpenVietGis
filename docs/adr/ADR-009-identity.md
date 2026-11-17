# ADR-009: OIDC-First Identity and Scoped Authorization

**Status**: Accepted  
**Date**: 2026-11-17

## Context

Cloud and enterprise deployments need different identity providers while sharing the same product
authorization model.

## Decision

Authentication uses OIDC/OAuth2-compatible identity providers behind an identity adapter. The
platform owns membership, role, resource scope, and authorization decisions.

Use RBAC plus resource scope initially. Add more general policy/attribute-based authorization only
when a concrete workflow requires it. Keycloak may serve as the reference self-host identity
provider, but Core does not depend on Keycloak-specific semantics.

## Consequences

- Enterprise SSO and managed Cloud identity can coexist.
- Hiding UI controls never counts as authorization.
- Token/claim mapping and tenant membership require explicit tests.
