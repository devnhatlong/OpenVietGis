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

See [earlier recovery evidence](implementation-evidence.md) for real isolated
data/authorization verification before v4. The proposed container configuration
is in [infra/prod/README.md](../../../../infra/prod/README.md). No production
secrets, databases, deployment or approved RPO/RTO have been used. Complete
isolated signed-recovery evidence and full profile build/migration/TLS/OIDC
workflow acceptance remain separate gates; G010 is not certified for release.
