# R013 — Real offline workflow and durable-revocation evidence

Verification date: 2026-11-22. Runtime candidate **b97eaa9e37a44b65a1b1965bfaaef9f792194a3c**
(detached worktree `/opt/openvietgis-verify-r013`), including R013 implementation
commits `c3def6e`, `1a03e87` and integrated R006 exact replay digest.

## Product fixes

- Writable offline package list, download and browser snapshot require current
  project edit permission, not merely ordinary read access. This is the only
  supported package profile; a downgraded viewer cannot re-fetch writable data.
- Known online authorization denial durably locks that actor's local project
  records in a strict IndexedDB transaction and increments their revisions.
  The lock retains drafts, prevents stale-tab overwrite and survives later
  device unlock/regrant. Ordinary offline access is immediately locked on
  denial; window focus also triggers online revalidation.
- Public R006 edits and reverts reject the normalized reserved
  `field-sync-*` operation identity namespace. Internal R013 recovery can use
  it without a caller preempting the deterministic ID.

## Real execution (single browser worker)

Ran `tests/e2e/r013-offline-real.spec.ts` with production web build and generated
service worker, real synthetic Keycloak realm, actual HTTP API and guarded
PostgreSQL/PostGIS test database. All surfaces were loopback-only (DB 54334,
API 18085, web 5186, OIDC 18086). No production access. The real test DB was
selected through `tools.run_with_test_database` with the dedicated
`OPENVIETGIS_TEST_DATABASE_URL` and a disposable artifact-store directory.

**PASS: 1/1** (30.542s test; 43.086s overall). No unexpected, flaky or skipped tests.
Report: `/opt/openvietgis-verify-r013/dist/security-evidence/playwright-p1.json`,
SHA-256 `7b694aa9c5d04942f1930adc4d02026dbd8832a0d481acdbcd5d8ed501b5b67f`.
The API and web preview stopped after the suite, the dedicated synthetic realm
was stopped, and the ephemeral Chromium profile was removed. No traces,
screenshots or copied credentials retained.

Executed scenario:

1. Real OIDC owner creates project and imports a Point layer via the transfer
   UI. Issues and downloads a real authorized GeoPackage and typed projection
   from the running API; checksum-verification and local map readiness succeed.
2. Chromium offline networking enabled. User reads package, edits feature
   attributes, captures a new native-CRS point, and queues both changes.
   Sync disabled while disconnected. **Entire Chromium process closes and
   relaunches with the same temporary persistent browser profile, still offline.**
   Service-worker route loads, installed pack reopens, typed attribute draft and
   two queued changes survive.
3. Reconnect. Independent read proves live source still contains only original
   feature. Browser sync request is forwarded unchanged to the real API;
   server responds 201/applied, and only then a test interceptor deliberately
   substitutes a 503 response to simulate a lost acknowledgement.
   PostGIS-backed read confirms original attribute update and new point geometry.
   Online reload and UI retry submit JSON-equivalent intent and identical
   group ID; received receipt ID and Core changeset ID equal the first actual
   server receipt. Independent read confirms two features and unchanged source
   revision after retry (no duplicate mutation).
4. A second package is drafted offline. Independent R006 edit advances the
   source; stale sync yields a real conflict receipt. User retains original
   draft and compares current authorized feature data; no blind merge or
   overwrite of current source.
5. Revoked package is rejected by actual snapshot endpoint (403), marked
   locked by online revalidation and remains non-openable in disconnected
   reload. Explicit device lock hides all packages.
6. Distinct real OIDC member with project editor grant issues and drafts own
   package. While disconnected, owner revokes editor permission and grants
   viewer access. On reconnect, map/ordinary layer read remains allowed
   (200), while writable package list, download, snapshot and sync all deny
   (403). Local package inaccessible. Even subsequent valid editor regrant
   and explicit offline-device unlock do not reopen that known-denied
   locally retained pack. Final independent source revision is unchanged.

No mocked backend or fixtures replaced actual HTTP/PostGIS in this test.
Only the client-facing lost acknowledgement was intentionally replaced,
after the real server commit was independently observed.

Earlier isolated checks: offline snapshot/namespace Python 7 tests pass (3
snapshot, 4 namespace); Vitest offline-store 4 pass; Ruff, ESLint, TypeScript,
diff check pass. The prior narrower synthetic browser and separate real API
checkpoint remain documented in `r013-offline-client-checkpoint.md`.

## Remaining scope / limitations

This is real end-to-end acceptance evidence for the implemented **single-source,
non-sensitive writable browser profile**, not a claim of unrestricted/full
offline platform support or production release certification. The ordinary
browser IndexedDB actor/access lock is **not encryption**, not OS credential
isolation and not remote wipe. Server authorization and revocation are
rechecked on reconnection; an already disconnected client cannot know new
server decisions. Device clock manipulation, eviction, physical access and
developer-tools inspection remain limitations; no sensitive data profile.
Explicit editor consent is not a substitute for organization-wide data
classification policy. Locked/expired draft recovery is not yet designed.
No automatic merge, multi-source independent group sync, continuous GPS,
external basemap/raster cache or dedicated mobile app acceptance was proved.
The test capture used explicit native coordinates, not physical GPS.
The report intentionally makes no production deployment, release, or audit
closure claim beyond the verified journey.
