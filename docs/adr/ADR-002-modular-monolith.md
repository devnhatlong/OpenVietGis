# ADR-002: Start with a Modular Monolith

**Status**: Accepted  
**Date**: 2026-11-17

## Context

The product needs clear domain boundaries but does not yet need the operational complexity of a
fully distributed microservice architecture.

## Decision

The primary application backend is a modular monolith. Domain boundaries own their application
logic and persistence contracts. Heavy or operationally distinct workloads may run separately,
including tile rendering, spatial processing workers, object storage, and optional OGC gateways.

## Consequences

- Business behavior remains easier to change and test in the early product phase.
- Domain boundaries must be enforced in code review and architecture tests.
- Services may be extracted later without redefining product concepts.
- Network boundaries are introduced only when there is a technical or organizational reason.
