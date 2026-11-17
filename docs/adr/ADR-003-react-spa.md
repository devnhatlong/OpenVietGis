# ADR-003: React + TypeScript Desktop-Class Web SPA

**Status**: Accepted  
**Date**: 2026-11-17

## Context

The primary desktop experience is a long-lived professional workspace with maps, selection,
editing sessions, docked panels, attribute tables, command search, and keyboard-driven workflows.

## Decision

Use React + TypeScript with a client-side application architecture for the desktop workspace.
Vite and workspace-based package management are the initial toolchain. Server state and local
workspace state remain separate concerns.

The field/mobile experience is a separate shell optimized for field work and offline workflows,
while sharing contracts and services with the desktop application.

## Consequences

- Server-side rendering is not a core requirement for the professional workspace.
- UI code must not become the owner of map, editing, command, or business logic.
- Framework-specific implementation remains outside the Constitution and may be superseded by a
  later ADR.
