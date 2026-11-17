# ADR-008: Controlled Module Architecture

**Status**: Accepted  
**Date**: 2026-11-17

## Context

Vertical products such as house numbering must extend the platform without becoming hidden Core
dependencies. A public SDK designed before real modules exist would likely freeze the wrong
extension points.

## Decision

Introduce an internal module framework first. Modules may register documented extension points such
as commands, UI contributions, permissions, forms, processing algorithms, reports, events, and
module-owned migrations.

Core must never import a vertical module. Modules cannot modify Core-owned database schema directly.
The public Module SDK is stabilized only after at least two materially different modules have
validated the extension model. Official and future third-party modules may use different trust
models.

## Consequences

- House Numbering becomes a reference/stress-test module rather than an architecture template.
- Extension points evolve before public compatibility is promised.
- Module lifecycle and compatibility are explicit instead of ad-hoc imports.
