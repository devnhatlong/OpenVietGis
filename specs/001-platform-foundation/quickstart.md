# Quickstart Validation: Platform Foundation

**Feature**: 001-platform-foundation

This guide is the target validation experience for the implementation phase. Commands may be
implemented by tasks generated from this plan, but the final workflow MUST preserve the behavior
described here.

## Supported development baseline

- Git
- Docker with Compose support
- Node.js 26 LTS
- pnpm via Corepack
- Python 3.13
- uv

No production credential, production database, or production data is required.

## 1. Bootstrap dependencies

From the repository root:

```powershell
corepack enable
pnpm install
uv sync --project apps/api
docker compose -f infra/dev/compose.yaml up -d postgres
```

Expected result:
- dependency installation completes without manual source edits;
- the PostGIS development service becomes healthy.

## 2. Apply development migrations

```powershell
uv run --project apps/api alembic upgrade head
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

## Troubleshooting expectations

The implementation documentation MUST provide clear guidance for:
- port already in use;
- Docker/PostGIS unavailable;
- missing environment configuration;
- schema not migrated;
- unsupported runtime version.
