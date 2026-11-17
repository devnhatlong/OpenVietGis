# ADR-001: Use a Monorepo

**Status**: Accepted  
**Date**: 2026-11-17

## Context

OpenVietGIS will contain web, field, API, workers, shared contracts, spatial packages, official
modules, services, infrastructure, and documentation. These parts will evolve together during the
early product phase.

## Decision

Use one Git repository with explicit top-level boundaries for applications, reusable packages,
official modules, specialized services, infrastructure, specifications, and documentation.

Do not split services into separate repositories until independent release cadence, ownership, or
operational scaling creates a demonstrated need.

## Consequences

- Cross-boundary refactors and contract changes remain atomic.
- CI can validate the whole product consistently.
- Repository ownership rules and dependency checks are required to prevent accidental coupling.
- A monorepo does not imply a single deployable process.
