# Implementation plan: R008 output integrity

Current audit worktree remains immutable evidence. Start a separately named implementation branch only after scope/owner/base coordination. Preserve source audit result and exact candidate references.

1. Add failing focused test for pinned feature read after success; replay the original oracle unchanged and capture result.
2. Inspect canonical logical attribute contract and all result publishers. Choose shared canonicalization before insert, validate schema and geometry with Core's existing model. Keep decimal precision exact and failure atomic; no relaxed serializer.
3. Validate actual output stored revision pins and publication transaction; regression cases for Buffer, Clip, Dissolve. Use the existing query/processing oracle plus independent geometric controls and test actual map/export consumers.
4. Inventory historical invalid rows read-only; propose separately approved versioned recompute/replacement policy. No direct production mutation.
5. Run local integration, focused browser and complete exact-candidate validation, and independently review authority, data integrity and original R008 scope.

Files to inspect: processing_repository.py, domains/spatial/domain.py, domains/spatial/service.py, processing domain, existing test_r006_r009_real.py, audit probe. Implementation details conditional on branch integration. No dependency changes or schema migration by default.
