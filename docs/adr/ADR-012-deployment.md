# ADR-012: One Logical Architecture for Cloud and Self-Host

**Status**: Accepted  
**Date**: 2026-11-17

## Context

OpenVietGIS targets both Team SaaS and organizations that require private or on-premise
deployments.

## Decision

Cloud, enterprise, and self-hosted editions share the same product architecture and application
code. Provider-specific identity, storage, queue, observability, and deployment systems remain
adapters.

Billing and commercial entitlements are not prerequisites for the GIS Core. Multi-tenancy,
organization ownership, and tenant isolation are designed from the beginning even before Cloud
billing is implemented.

## Consequences

- Self-hosting cannot become a separate legacy fork.
- SaaS isolation is validated early rather than retrofitted.
- Deployment profiles may differ in scale and optional services without changing domain semantics.
