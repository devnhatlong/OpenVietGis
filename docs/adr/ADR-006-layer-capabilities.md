# ADR-006: Map, Layer, and Capability Abstractions

**Status**: Accepted  
**Date**: 2026-11-17

## Context

OpenVietGIS must work with heterogeneous sources: editable PostGIS data, read-only OGC services,
rasters, tiles, files, derived layers, and future engines. These sources do not share identical
behavior.

## Decision

A Layer is a platform abstraction, not a synonym for a database table. Layers expose explicit
capabilities such as render, query, edit, style, export, analysis, and offline use.

Map rendering is accessed through a MapEngine contract. MapLibre is the first renderer and deck.gl
may augment it for appropriate workloads, but business UI must not depend directly on renderer
internals.

Commands are registered independently of UI location and are enabled based on active capabilities.

## Consequences

- Unsupported actions can be disabled predictably rather than failing through source-specific
  conditionals.
- Future sources and renderers can be added through adapters.
- Capability contracts become a central part of UI, module, and processing design.
