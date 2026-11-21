# R013 offline-client remediation checkpoint (G005)

Candidate baseline: `596fb13`. Implementation branch `fix/018-r013-offline-client`.
This checkpoint is a **narrow writable browser profile**, not full R013 release acceptance.

## Implemented behavior

- Dedicated mobile-oriented route `/offline-field/:organizationId/:projectId` linked from the field hub. Online layer choice, native CRS bounds, TTL and explicit non-sensitive local-storage confirmation; project-owned active editable sources only (read-only/reference fixtures excluded). Fully contained features only, with no silent truncation beyond 5000.
- Server emits a normal vector GeoPackage and embeds a deterministic typed JSON projection in its private SQLite table `ovg_offline_snapshot`. The issuance pin binds the projection's SHA-256 as well as the GeoPackage's authoritative SHA-256. Exact field IDs, values (including decimal strings), nullable schema, native CRS, feature IDs, actor, project, layer/source identity, revisions, area and lease are stored.
- Browser fetches authorized bytes for both artifact and projection, checks length, both checksums and scope/revision consistency, then commits the complete record to IndexedDB. Corrupt, unissued, legacy, expired and revoked package data cannot be opened by the new workflow. Server downloads are `no-store`.
- Static-only versioned service worker generated from the production build. It precaches only application shell/assets and provides offline navigation fallback only for the dedicated route. No API, auth response, external tile or protected data enters Cache Storage.
- Native-CRS local map (pan/zoom/reset, layer visibility, selection); selected feature attributes displayed separately from draft attributes. Point creation uses manually confirmed native X/Y or explicit device geolocation only for EPSG:4326 (display source/time/accuracy); no guessed transformations.
- Typed attribute form and point draft validation. Immutable package baseline, identifiable local point/feature draft, stable group ID, strict IDB commit and optimistic record revision check against multi-tab overwrites. Attempted groups cannot silently change payload; reconnect requires current authenticated account, server scope/pins and explicit sync. Accepted/rejected/conflicted receipts persist before display and drafts remain for review.
- Server rejects package actor substitution, just-in-project but unissued feature updates, deletion/geometry changes, point creation outside AOI or for non-point geometry, wrong/canonical typed attributes, missing lease and invalid packages. Replay identity is hashed over actor/org/project/package/client group and canonical payload; changed replay conflicts. No migration or production data mutation.
- Browser account-local ordinary access is opt-in and locked on explicit logout/account switch/denial; cross-tab lock and online revalidation. Expiry and device limitations shown. Package deletion warns about stale/unacknowledged drafts.

## Scope deliberately not claimed

This profile supports application shell reload in secure contexts on an installed production build (HTTPS or localhost). No background tracking, external basemap tiles, multi-layer independent groups, device-lost remote wipe, OS-level disk encryption, confidential-data profile, or automatic conflict merge. User confirmation of non-sensitive classification is necessary, not evidence of an organization classification framework. The local clock can be manipulated, browser storage can be evicted and ordinary-access locks are not cryptographic isolation. Offline drafts may be inaccessible after lease expiry/revocation; a separate approved recovery design is required. The server uses issued source-level revision conflict and all operations from one source in one atomic Core ChangeSet; operation-level durable IDs/group migration and automatic conflict reapplication provenance are not yet independent acceptance evidence. Conflict UI permits current-state comparison when authorized; revised operations must be explicitly staged on a freshly issued package, not an implicit rebase.

## Verification at implementation checkpoint

- Python unit test `apps/api/tests/unit/transfers/test_offline_snapshot.py`: 3 pass, exercising real GeoPackage writer, lossless typed projection and integrity, rejected stale scope and invalid types/bounds.
- Vitest `apps/web/src/features/offline/offline-store.test.ts`: 4 pass, verifies both hashes, expiry, actor scope, typed values, immutable attempt group and wire payload.
- Ruff, web ESLint, TypeScript production build: pass at preliminary implementation checkpoint.
- Integration test prepared in the existing R013 flow (real PostgreSQL / import / artifact / edits / conflict / replay), pending isolated shared DB slot.
- Dedicated Playwright test `playwright.offline-client.config.ts`, pending browser slot:
  `pnpm --filter @openvietgis/web build`, then `pnpm exec playwright test --config playwright.offline-client.config.ts`.
  It uses no live API/DB/identity provider: intercepted synthetic response URLs, real Chromium service worker and IndexedDB; disconnect, save draft, reload, reconnect, sync and reload receipt. This is distinct from real backend integration and does not constitute a complete live browser/API acceptance workflow.

No production deploy, push, release promotion or R013 acceptance claim.
