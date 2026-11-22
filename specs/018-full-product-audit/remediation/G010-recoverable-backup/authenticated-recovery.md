# R015 authenticated recovery — proposed recovery profile

## Snapshot format and trust

New snapshots use **manifest v4**. The atomic completion marker contains the
entire previous manifest (database, timestamp, dump SHA256 and byte count,
artifact keys/sizes/checksums, required references, revision/fingerprints and
authority fingerprint) plus a provenance identifier, key identifier and
HMAC-SHA256. The MAC covers canonical UTF-8/ASCII JSON of every field except
the MAC itself, using a format-specific domain string. A key identifier is
derived with separate HMAC context; it is not the secret key. Duplicate JSON
keys, unsigned/old versions, invalid or oversized manifests (64 MiB maximum),
wrong provenance, missing or wrong keys and failed MAC comparisons are refused.

The operator must provision an independent, cryptographically random 32-byte
key file with mode 0600 (or stricter), owned by the invoking operator, not a
symlink/hardlink, not inside the backup, original artifacts or restore roots.
Use the same protected key for creating and verifying a given snapshot.
Keep the key outside backup storage, outside application database/containers
and outside source control. Obtain the expected provenance and key through an
independent trusted configuration/secret delivery channel; **never** select
either from an untrusted backup. Use distinct keys per trust domain; the
provenance name is explicitly supplied by the operator, not inferred from a
claimed manifest. Key rotation requires versioned external key retention and
revocation policy; no automatic trust in a historical or unknown key.

The HMAC provides authenticity against a writer who can replace the backup
but has no signing key. It does not provide encryption, non-repudiation,
freshness beyond the included timestamp, or protection from a compromised
signer or operator. Key custody, encrypted/off-site storage, retention,
rollback/age policy and a trusted signing host remain external approval gates.
If trust in a signing key is lost, abort restore until independent authority
chooses a trustworthy snapshot; do not sign an old untrusted dump to bypass
the check. v1/v2/v3 backups cannot enter the production restore function.

## Restore contract

- The caller must explicitly attest quiescence when creating a backup and a
  truly isolated PostgreSQL instance when restoring. The operator supplies
  `manifest_key_file` and `provenance` to
  `backup_docker_postgres_and_artifacts`, and the independently selected
  `manifest_key_file` and `expected_provenance` to
  `verify_isolated_restore_docker`.
- Authenticate the complete manifest first, then check required artifact
  references, tree and root constraints. Stage SQL into a private anonymous
  temporary file while verifying its length and digest. Privileged psql reads
  the exact verified file descriptor, not a mutable backup path reopened after
  validation. No DB creation or SQL execution occurs before these checks pass.
  The temporary directory must be trusted, private and have adequate capacity.
- Create a new database initially closed to connections; deny PUBLIC/runtime
  CONNECT before enabling the restore owner's connection. Never overwrite a
  database. Verify restored inventory and quarantine old authority/jobs as in
  the earlier G010 implementation. Copy required artifacts to a new target and
  independently verify destination bytes. Failed restore targets stay closed;
  do not automatically delete them or certify partial data.
- The report includes manifest authentication, key identifier and backup
  provenance, elapsed time/age and reconciliation results. No runtime
  activation, RPO/RTO claim, release certification or production authorization.
  A signature authenticates provenance and contents, **not** safety of arbitrary
  SQL from a compromised/trusted signer. Use a genuinely isolated disposable
  instance never sharing a production cluster, privileged process/container,
  mounts or secrets.

The opt-in `tools/r015_synthetic_drill.py` is a narrowly scoped test runner,
not a general unsigned restore path. Its legacy v2 seed is an exact pinned
synthetic fixture from earlier remediation, not customer or production data.
It creates a new random test key, signs the new v4 snapshot and verifies
tamper rejection before database creation. It restores only to named fresh
`openvietgis_r015_*` targets on the currently coordinated dedicated synthetic
test container. Do not point this drill at any other database.

## Verification evidence and remaining gates

Static/unit verification: 48 targeted backup, authority and Settings tests
passed on the remediation candidate. The authenticated recovery tests cover
combined dump+manifest substitution, dump-only mutation, provenance tampering,
wrong key, missing MAC, legacy unsigned format, wrong trusted provenance,
duplicate keys, unsafe/private key paths, missing/corrupt files and unchanged
exact staged bytes after original file replacement. The negative restore
preflight tests prohibit any call to Docker/database creation.

### Real signed v4 synthetic drill (2026-11-22)

Executed commit `ff41b1b` with explicit isolated test attestation,
using the pinned synthetic v2 fixture only as seed for creating its own v4
snapshot and a fresh independently generated demo-only signing key. Dedicated
container `ovg-next018-postgres` (loopback 54334); four new databases:
`openvietgis_r015_src_e3467649`, `openvietgis_r015_current_e3467649`,
`openvietgis_r015_quarantine_e3467649`, and
`openvietgis_r015_reconciled_e3467649`. Private test files were in
`dist/r015/e3467649`; no key or backup payload is committed. The original
artifact root was moved aside in the drill before either restore.

- The deliberately modified SQL and matching changed manifest digest/size
  fields were refused by HMAC validation. The prospective
  `openvietgis_r015_tampered_e3467649` database and output artifact directory
  did not exist afterward.
- Both v4 restores verified manifest authentication, provenance and exact SQL
  and artifact bytes: 12/12 artifacts and references, same Alembic revision
  `0018_production_ops`, 38 features, 16 sources and 15 layers; zero
  inconsistent publications; exact equality of feature, source and layer
  fingerprints with the snapshot.
- Default closed recovery retained zero active users, memberships and grants.
  Reconciled recovery kept 33 unchanged users and 21 memberships, zero active
  grants. Both had zero unrevoked sessions, service credentials, active
  service identities, pending invitations or unrevoked offline packages.
  One processing job, one transfer job and seven transfer attempts quarantined.
- Application HTTP adapters executed in-process with a test-only restricted
  role connection: two old sessions and the old service key denied, revoked
  grant denied with a fresh test session, unchanged owner downloaded the real
  restored print artifact and its exact digest matched. Interrupted processing
  and transfer retries each returned conflict, with spatial fingerprints
  unchanged. Both recovered databases denied runtime CONNECT, and no runtime
  activation was performed.
- Measured isolated synthetic restores only: closed 4.88 s elapsed, 9.91 s
  snapshot age; reconciled 5.69 s elapsed, 15.60 s snapshot age. Whole runner
  completed in 26.9 s and exited successfully. These are measurements on a
  small synthetic fixture, not approved RPO/RTO limits or capacity evidence.

See [earlier recovery evidence](implementation-evidence.md) for the original
G010 data/authority verification. The proposed container configuration is in
[infra/prod/README.md](../../../../infra/prod/README.md). No production secrets,
databases, deployment or approved RPO/RTO have been used. Full profile
build/migration/TLS/OIDC workflow acceptance, independently approved recovery
objectives, encrypted backups and key custody remain separate gates.
G010 is not certified for release.
