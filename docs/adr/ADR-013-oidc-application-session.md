# ADR-013: OIDC-Backed First-Party Application Session

**Status**: Accepted
**Date**: 2026-11-18

## Context

OpenVietGIS must support multiple external identity providers across Cloud, self-hosted, and
enterprise deployments while keeping membership and authorization inside OpenVietGIS. The browser
also needs a safe long-lived application session without making provider tokens the product's
authorization model.

## Decision

Authenticate humans through OIDC Authorization Code flow behind an IdentityProvider adapter.

After a successful OIDC callback:

1. resolve the stable external identity using issuer + subject;
2. map or create the internal OpenVietGIS User/IdentityLink;
3. create an opaque first-party OpenVietGIS application session;
4. store only a hash of the session secret server-side;
5. send the session secret only in an HttpOnly, SameSite cookie;
6. keep OIDC access/ID tokens out of browser storage.

The application session authenticates the User only. Organization membership, role, resource grants,
and authorization are resolved from current OpenVietGIS state on each protected request.

Cookie-authenticated unsafe requests require explicit CSRF protection.

Keycloak is the reference self-host/development OIDC provider, not a Core dependency.

## Consequences

- Membership/grant revocation can take effect on the next protected request without waiting for
  provider-token claims to expire.
- The browser does not need to persist provider bearer tokens.
- OpenVietGIS can switch identity providers without changing organization authorization semantics.
- Session storage, expiry, logout, CSRF, and OIDC state become application responsibilities.
- Provider availability is required for new login/link flows but not for every authorized request.
