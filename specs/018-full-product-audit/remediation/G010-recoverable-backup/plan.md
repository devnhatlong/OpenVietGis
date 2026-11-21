# Implementation plan: R015 full recovery

Preserve audit baseline and G010 evidence. Start implementation in a separately coordinated branch. Review artifact-store lifecycle and database reference catalog, existing backup_restore.py and original R015 authorization/recovery contract before choosing snapshot mechanism.

1. Design consistency point for one approved small-team self-host profile (documented write quiesce or validated immutable snapshot/cutoff). Inventory required source and derived asset references, expected retired/expired states, job/authority state. A file listing alone is not a backup.
2. Create staged protected recovery set with verified DB dump and complete artifact bytes, manifest, checksums and scope. Use atomic completion marker; reject inconsistent/missing/unsafe paths, protect backup access and document encryption requirements.
3. Validate fresh restore target names/paths, explicit no overwrite by default, restore SQL and bytes into isolated environment, check DB integrity, real SHA/reference coverage, representative download/open workflows and current authority reconciliation.
4. Test missing/corrupted artifacts, partial snapshot, path traversal/symlink, invalid scope and pre-revocation/interrupted job recovery. Block readiness and publication until reconciliation. Preserve failures.
5. Measure recovery age/duration, compare to approved profile targets only; publish redacted evidence and run full candidate regression/security review. No deployment under audit.

Reference implementation: tools/backup_restore.py (currently SQL + manifest only); storage and reference catalogs, identity/runtime authorization, job publication. New configuration/format must be explicitly scoped and versioned. Do not expose actual backup payloads in audit documentation.
