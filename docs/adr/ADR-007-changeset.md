# ADR-007: ChangeSet-Based Editing and History

**Status**: Accepted  
**Date**: 2026-11-17

## Context

Professional editing, undo/redo, offline synchronization, bulk operations, conflict detection, and
audit all need a common model of change.

## Decision

Use ChangeSet/revision semantics as the common primitive for material data changes. User edit
sessions may be long-lived in the UI, but database transactions must remain short-lived. Commits
use revisions and optimistic concurrency where conflicts are possible.

Imports, bulk edits, and offline synchronization should produce attributable change units rather
than invisible direct mutations.

## Consequences

- History, recovery, conflict detection, and audit share one conceptual model.
- Editing workflows do not hold database transactions open for the duration of user sessions.
- ChangeSet schema and retention policy require careful performance design.
