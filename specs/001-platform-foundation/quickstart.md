# Quickstart Validation: Platform Foundation

**Feature**: 001-platform-foundation

This guide is the target validation experience for the implementation phase. Commands may be
implemented by tasks generated from this plan, but the final workflow MUST preserve the behavior
described here.

## Supported development baseline

- Git
- Docker with Compose support
- Node.js 26 LTS
- pnpm 12.21 installed explicitly
- Python 3.13
- uv

No production credential, production database, or production data is required.

## 1. Bootstrap dependencies

From the repository root:

```powershell
npm install --global pnpm@12.21.0
pnpm install
uv sync --project apps/api
docker compose -f infra/dev/compose.yaml up -d postgres
```

Expected result:
- dependency installation completes without manual source edits;
- the PostGIS development service becomes healthy.

## 2. Apply development migrations

```powershell
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

Expected result:
- the foundation schema is created through migrations;
- no ORM auto-create shortcut is required.

## 3. Start the API

```powershell
uv run --project apps/api uvicorn openvietgis_api.main:app --reload
```

Verify readiness:

```text
GET /api/v1/health/ready
=> 200
=> {"status":"ready","database":"ready"}
```

If the database is unavailable, readiness returns a clear non-ready result instead of pretending the
application is healthy.

## 4. Start the web shell

In another terminal:

```powershell
pnpm --filter @openvietgis/web dev
```

Expected result:
- the OpenVietGIS foundation shell opens;
- it displays foundation readiness;
- it provides the temporary sample-record vertical slice only;
- no map, house-numbering, billing, production auth, or GIS tools appear.

## 5. Prove persistence

From the web shell:
1. Enter a short label such as `foundation-check`.
2. Create the record.
3. Copy the returned UUID.
4. Restart the API process.
5. Load the same record by UUID.

Expected result:
- the same label and stable UUID are returned after restart.

The HTTP behavior is defined in [contracts/foundation-api.yaml](contracts/foundation-api.yaml).

## 6. Run the baseline validation workflow

Target root command:

```powershell
pnpm validate
```

It MUST orchestrate:
- static/type/lint checks;
- web/package unit tests;
- Python unit tests;
- architecture boundary checks;
- migration + real PostGIS integration tests;
- the critical browser vertical-slice test.

Expected result on an unchanged accepted checkout: all mandatory categories pass.

## 7. Prove the architecture guard

The automated architecture test fixture MUST include a controlled forbidden example or an
equivalent test that proves:

```text
Core/platform -> vertical module   FAIL
vertical module -> public Core contract   PASS
```

The intentionally invalid fixture must not be imported into the shipping runtime.

## 8. Reset local development data

Target command:

```powershell
pnpm dev:reset
```

Expected behavior:
- refuses to run unless the configured database is explicitly marked as development/test;
- resets only the local foundation data;
- reapplies migrations;
- never accepts a production database target.

## 9. Acceptance repetition

The persistence integration scenario MUST pass ten consecutive automated runs to satisfy SC-003.

## 10. Measure clean bootstrap time

Use a clean supported development environment with no prior OpenVietGIS checkout or installed project
dependencies. Start timing immediately before following the documented bootstrap procedure and stop
when the foundation shell is running and readiness is healthy.

Dependency download time MAY be excluded only if it is recorded separately.

Expected result:
- bootstrap completion time, excluding recorded dependency download time, is at or below 20 minutes;
- any undocumented setup step is treated as a failure and must be added to the repository documentation.

## 11. Measure documentation discoverability

Ask a reviewer who has had no prior repository orientation to use repository documentation only.

Start timing before giving the reviewer these tasks:
1. Locate the Constitution and explain what kind of decision belongs there.
2. Locate the ADR index and identify how a technical decision is superseded.
3. Locate the architecture guide and explain why Core cannot depend on vertical modules.
4. Locate the active Spec 001 artifacts.

Expected result:
- all four tasks are completed in under 10 minutes;
- assistance from someone already familiar with the repository invalidates the measurement;
- record the reviewer role, elapsed time, and any navigation problem that required remediation.

## Troubleshooting expectations

The implementation documentation MUST provide clear guidance for:
- port already in use;
- Docker/PostGIS unavailable;
- missing environment configuration;
- schema not migrated;
- unsupported runtime version.

## Validation evidence

### 2026-11-17 — clean bootstrap measurement (SC-001)

A source-only checkout was copied to an isolated directory with no `node_modules`, Python virtual
environment, build output, test output, Git metadata, local `.env`, or existing development
database volume.

Measured environment:
- Node.js: 26.13.1
- pnpm: 12.21.0
- Python: 3.13.18 through uv
- PostgreSQL/PostGIS: fresh `postgis/postgis:18-3.7` development volume
- browser check: Chromium via Playwright

The package store and Python/download caches were warm; zero JavaScript packages were downloaded.
This is allowed by SC-001, which excludes dependency download time.

The measured path installed project dependencies, created a fresh Python environment, initialized a
fresh PostGIS database, applied migration `0001_foundation_sample`, started the API and web shell,
and used Chromium to observe:

```text
Foundation ready — database connected
```

**Measured elapsed time**: 31.5 seconds
**Limit**: 20 minutes excluding dependency download time
**Result**: PASS

The host already had another unrelated application on port 5173, so the acceptance shell used port
5188 as permitted by the documented port-conflict procedure. No OpenVietGIS source edit was required.

### 2026-11-17 — unfamiliar reviewer navigation measurement (SC-006)

A fresh ephemeral Codex CLI session, with no prior repository orientation and a read-only sandbox,
was asked to use repository documentation only. It correctly located and explained:

1. `.specify/memory/constitution.md`
2. `docs/adr/README.md`
3. `docs/architecture.md`
4. all active `specs/001-platform-foundation/` artifacts

**Measured elapsed time**: 33.96 seconds
**Limit**: 10 minutes
**Result**: PASS

Detailed evidence is recorded in
[checklists/reviewer-navigation.md](checklists/reviewer-navigation.md).