# ADR-011: Job-Based Spatial Processing

**Status**: Accepted  
**Date**: 2026-11-17

## Context

Spatial workloads range from instant local operations to multi-minute or large-data processing.
The product must support UI tools, API calls, automation, and future model-builder workflows
without duplicating algorithms.

## Decision

Use a processing algorithm registry with three execution classes: local/browser, short synchronous
server work, and asynchronous jobs. PostgreSQL stores durable job state and result references.
Queue transport and worker implementation remain replaceable infrastructure adapters.

Domain events plus a transactional outbox are used when reliable asynchronous side effects are
required; a distributed event platform is not required initially.

## Consequences

- Long-running requests do not block interactive API flows.
- One algorithm contract can serve UI, API, automation, and future workflows.
- Job retry, cancellation, progress, idempotency, and artifact cleanup need explicit behavior.
