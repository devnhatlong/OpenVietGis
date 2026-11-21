# 018 remediation checkpoint — confirmed runtime blockers

Branch: `fix/018-confirmed-blockers`, based on audit checkpoint `15f0c5e`.
Synthetic test container `ovg-remediation018-postgres`, loopback port 54332;
original audit container/worktree and production untouched. No merge/deploy.

## R008 / G009 — canonical derived attributes
- Canonicalize all output attributes against the derived schema before publication,
  rejecting a mismatched field set or invalid value rather than weakening the Core reader.
- Original independent audit oracle passed: 3 buffer features, 2 clipped features,
  dissolved area 6,242,890.3045124635 m²; expected per-buffer projected area
  3,121,445.152258052 m². Original pinned input unchanged. This is Web Mercator
  projected area, not a geodesic accuracy claim.
- Integration regression reads derived outputs at revision pins and asserts
  canonical values "1000", "250", and "12.5". M2/M3 existing suite: 6 passed.
- Broader processing readiness still subject to spec-defined validation and
  supported CRS/geometry coverage.

## R010 / G004 — truthful external availability
- All four unverified protocols expose only local registration metadata.
  Old stored optimistic flags are gated at read time. API availability and UI
  explicitly show unverified or revoked; no protocol falsely implies usability.
- Original negative audit probe: 4 passed. Existing M2/M3 integration suite:
  6 passed.
- Actual provider adapters, request-time DNS/IP/redirect safety, render/query
  proof, and positive provider tests are NOT completed. No R010 acceptance yet.
- Frontend browser/type-check proof pending; no dependencies installed in this
  isolated worktree.

## R015 / G010 — recovery of bytes
- Version 2 manifest; operator must attest quiescence and isolated restore.
  Backup includes actual bytes, validates database artifact references,
  rejects unsafe paths/symlinks and verifies the copied bytes. Missing
  required records fail closed; explicitly non-ready derived artifacts may
  be absent. Existing restore targets are never dropped/overwritten.
- Actual isolated recovery using `backup-v2-run1`, DB
  `openvietgis_rem018_restore1` and `restored-artifacts-v2-run1`:
  dump 355,862 bytes, SHA256
  `93f911c8827fbf2025c49b818c36aee1a90f7e730c525f3269c702d03ff66df7`;
  12/12 artifact files and 12/12 DB references verified; 38 features,
  16 sources, 15 layers, schema `0018_production_ops`; elapsed 2.60 s.
- Independent geometry/attribute fingerprint on source and isolated DB:
  `6a8cb7b65c14720f02e9b924b39b3c2d` (38 rows).
  Independent recursive artifact directory comparison: identical.
- Attempt to restore over existing verification DB rejected by createdb;
  retained original 38 features and no new artifact directory.
- Safety unit tests: 5 passed (tamper, missing files, symlink, traversal,
  missing DB reference, isolation/consistency attestation, obsolete manifest,
  existing destination). Ruff and git diff --check passed.
- Only an isolated file/DB recovery drill: authorization/job reconciliation,
  independent application artifact retrieval, protected/encrypted storage
  policy, approved RPO/RTO, and profile recovery acceptance remain open.
  Tool explicitly reports `authorization_reconciled=false`,
  `production_ready=false`. No production readiness claim.

Evidence outputs in ignored `dist/remediation018/` on the remediation VPS
worktree (JUnit XML plus restricted synthetic backup and restore directories).
Original baseline audit evidence remains unchanged.
