# R015/G010 recovery reconciliation checkpoint

Branch: `fix/018-r015-reconciliation` (base `596fb13`). This is an offline
remediation, not production activation or release acceptance. Original audit
snapshot and previous R015 recovery database were unchanged.

## Implemented

- Backup format v3 extends the v2 SQL+artifact snapshot with ordered SHA-256
  fingerprints over native EWKB geometry, attributes, source revision metadata,
  layers, and active human authority envelopes. It verifies those values on both
  sides of restore and refuses inconsistent partially published unsuccessful jobs.
  All required database artifact references and copied bytes are checked. Recovery
  input paths are restricted to the actual local immutable-object key syntax,
  reject symlinks, and cannot overwrite existing destination databases/directories.
  A private staged manifest is fsync'd and linked atomically as the completion
  marker; dump and copied file content are fsync'd. Old format v2 lacks these
  reconciliation fingerprints and is rejected by the new restore function:
  create a current v3 backup or explicitly use the historical v2 verification
  tool only as an isolated, non-certified drill.
- Restore always revokes CONNECT from PUBLIC and the runtime role on its fresh
  database, checks that the runtime role cannot CONNECT, and never starts an app.
  On post-creation failure it disables new connections to that database; it
  never drops or overwrites a database. Isolated operator access remains an
  explicit prerequisite. Backup/source writers and expiry cleanup must be
  quiesced, rather than claiming live atomic snapshots.
- Default current authority is **none**. The recovery transaction disables
  historical human identities, revokes active memberships and grants, revokes
  all historical sessions, service principals/credentials, invitations and
  offline packages, and validates the deny-all invariants before commit.
- An independently reviewed and quiesced **current database authority source**
  can be explicitly attested via `current_authority=(container,user,database)`
  and `current_authority_confirmed=True`. The historical human envelope is
  preserved only if the user and entire issuer/subject-link fingerprint set,
  organization scope/workspace/project lifecycle and membership/grant envelope
  exactly match the fresh source. Missing, changed, downgraded, newly added or
  revoked authority is not copied. Service credentials and sessions are always
  revoked, including the unchanged ones. A changed current source during
  comparison aborts certification and leaves deny-all. No credential hash or
  token material is exported in the authority comparison or report.
- Processing jobs which did not succeed are cancelled and marked
  `RECOVERY_QUARANTINED`; execute/retry refuse that marker rather than reviving
  a cancelled historical operation. Nonterminal transfer jobs are denied and
  unfinished attempts closed, with their original IDs preserved. Published
  successes remain intact. A snapshot with a partially published unsuccessful
  job fails inventory verification rather than releasing uncertain output.
  An authorized user must submit a new operation, not retry the restored job.
- Recovery result reports snapshot age, measured elapsed time, database counts/
  fingerprints, verified artifact count/ref coverage and authority quarantine
  counts. `production_ready=false`, `runtime_activation_performed=false` always.

## Executed evidence (2026-11-21)

Opt-in `tools/r015_synthetic_drill.py` uses the immutable **synthetic** parent
v2 backup as seed and creates fresh test databases and directories, all in
`ovg-remediation018-postgres` (loopback 54332):
`openvietgis_r015_src_a340993f`,
`openvietgis_r015_current_a340993f`,
`openvietgis_r015_quarantine_a340993f`,
`openvietgis_r015_reconciled_a340993f`.
The original artifact root was moved away from the recovery inputs, and the
new backup's own files were used for both drills. No original DB was modified.
The synthetic current database revoked a previously valid editor grant,
credential and session after the new backup had been taken.

| Check | Result |
|---|---|
| Restore with no current authority | PASS, 4.92 s, snapshot age 8.98 s |
| Restore with current authority attested | PASS, 3.65 s, snapshot age 12.64 s |
| Geometry/attributes | 38 features; identical SHA-256 `e4fbb58f7a487d66ac0cd0ad4b74a1449b89b119878fb36e8a4fd239f0d386da` |
| Source/layer metadata | 16 sources and 15 layers, identical SHA-256 fingerprints |
| Artifact references/bytes | 12/12 required objects, read by actual LocalObjectStore and verified |
| Default authority | 0 active users, memberships, grants, sessions, credentials, service principals, pending invites, unrevoked offline packages |
| Reconciled authority | 33 unchanged identities, 21 exact-match memberships, 0 grants; no old session/credential/service principal/invite/offline package preserved |
| Interrupted jobs | 1 processing job, 1 transfer job, 7 unfinished transfer attempts quarantined |
| Real HTTP auth, restored historical sessions | 2 old valid synthetic session cookies rejected with 401 |
| Real HTTP auth, restored historical bearer | Old service credential rejected with 401 |
| Real HTTP authority | Revoked editor grant denied even with fresh authenticated session; unchanged owner permitted a real print download, SHA/size/file signature checked |
| Real HTTP replay | Historical processing and transfer retry rejected with 409; spatial fingerprints unchanged afterwards |
| Runtime DB CONNECT | Denied on both restored databases |

The application tests use in-process FastAPI TestClient with its actual auth,
authorization and download/processing/transfer adapters. The database
session dependency connects through an isolated synthetic operator account
and immediately SET ROLE to the actual restricted runtime role; this does
not grant runtime CONNECT or activate a real application. No OIDC provider
network or production endpoint contact.

After adding the explicit partial-publication count, independently querying
all three source/quarantine/reconciled databases read-only found
`inconsistent_publications=0` and identical source/layer/feature fingerprints.
23 targeted unit tests pass (snapshot integrity, atomic completion marker,
missing/tampered data, traversal/symlink, preflight same authority/future
snapshot, authority intersection, missing/reassigned links, revoked/changed
grants/scopes). Ruff and diff check pass. The full live drill preceded the
final small manifest-fsync/path/preflight hardening; that hardening is covered
by unit and read-only fixture checks. Re-run the opt-in drill on the final
integrated commit as part of convergence.

## Remaining acceptance gates

- No approved production recovery profile or RPO/RTO targets, key handling/
  encrypted off-site backup storage, operational retention or trust chain.
  Filesystem protections/checksums detect corruption, not adversarial
  replacement of both dump and manifest by an already privileged writer.
  Storage encryption and independently authenticated manifest policy remain
  operator/profile gates.
- Current authority is deliberately conservative; no current source means
  deny-all, and operator attestation is a required external trust input.
  It is not proof of a separate provider's live account state or post-drill
  changes. Repeat current reconciliation/authority review before any release,
  rotate external application/provider credentials and DB credentials,
  verify fresh identity provider claims, and independently approve any
  re-provisioned service authority. No automatic production activation.
- Authenticated real print artifact was downloaded (and all required bytes
  read). This synthetic fixture had no derived transfer export artifact and
  therefore does not prove all format-specific restore/download workflows.
- Release requires independent full regression, isolated target/operator
  review, explicit approved self-host profile, protected backups, authorized
  representative workflows and measured approved-profile recovery acceptance.
  G010 remains open for release acceptance; this is actual recovery and
  conservative authorization reconciliation evidence, not a production promise.
