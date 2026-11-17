# ADR-010: S3-Compatible Object Storage

**Status**: Accepted  
**Date**: 2026-11-17

## Context

The platform will handle source files, rasters, CAD files, attachments, processing outputs, and
export packages that do not belong in relational storage.

## Decision

Use an S3-compatible object-store contract. Distinguish at least SourceAsset, DerivedArtifact, and
Attachment semantics instead of treating every file as an anonymous blob.

Self-hosted deployments may use an S3-compatible local service; Cloud deployments may use any
compatible managed provider.

## Consequences

- Storage provider selection remains a deployment concern.
- Checksums, provenance, retention, and immutable result artifacts can be modeled consistently.
- Database records retain metadata and ownership rather than large file payloads.
