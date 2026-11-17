# ADR-005: PostgreSQL/PostGIS Is the Spatial Source of Truth

**Status**: Accepted  
**Date**: 2026-11-17

## Context

The platform needs transactional spatial data, indexing, querying, tenant ownership, history
references, and compatibility with professional GIS tooling.

## Decision

Use PostgreSQL with PostGIS as the source of truth for structured spatial and business data.
Tenant-owned records carry explicit organization ownership. Server authorization is mandatory and
database-level isolation such as RLS is applied selectively to high-value tenant-sensitive paths
with integration tests.

Large binary/source artifacts are not stored in normal relational rows.

## Consequences

- Spatial correctness can be validated close to the data.
- SQL and spatial indexing remain available for analytical and operational workflows.
- RLS is a defense-in-depth mechanism, not a substitute for application authorization.
- Connection pooling, workers, migrations, and administrative operations must preserve tenant
  context correctly.
