# OpenVietGIS

OpenVietGIS is a platform-first spatial workspace for the web. Spec 001 intentionally builds only
the architecture runway and a disposable non-GIS vertical slice.

## Governance and architecture

- Constitution: `.specify/memory/constitution.md`
- ADR index: `docs/adr/README.md`
- Architecture boundaries: `docs/architecture.md`
- Active foundation specification: `specs/001-platform-foundation/`

Core/platform code must never depend on a vertical domain module. The foundation must build and run
when `modules/` is empty or absent.

## Supported development baseline

- Node.js 26 LTS
- pnpm 12.21 (installed explicitly; Node 26 no longer bundles Corepack)
- Python 3.13 managed by `uv`
- Docker with Compose
- PostgreSQL 18 + PostGIS 3.7 through the development compose profile

The current local machine may use another Node version for exploratory work, but accepted CI uses
Node 26 and is the authoritative runtime gate.

## Bootstrap

From the repository root:

```powershell
Copy-Item .env.example .env
npm install --global pnpm@12.21.0
pnpm install
uv python install 3.13
uv sync --project apps/api
docker compose -f infra/dev/compose.yaml up -d postgres
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
pnpm exec playwright install chromium
```

No production credential or production data is required.

## Run locally

API:

```powershell
pnpm dev:api
```

Web shell in another terminal:

```powershell
pnpm dev:web
```

Open `http://127.0.0.1:5173`.

The shell exposes only:
- foundation readiness;
- one disposable `FoundationSampleRecord` create/read flow.

It does **not** contain map rendering, GIS editing, production authentication, tenancy, billing,
processing, field/offline workflows, or House Numbering.

## Baseline validation

With the development PostGIS service running:

```powershell
pnpm validate
```

The command covers:
1. TypeScript/JavaScript static quality and unit tests.
2. Python static quality, unit tests, and contract checks.
3. Architecture dependency rules.
4. Documentation navigation.
5. Real PostgreSQL/PostGIS migration and integration tests.
6. Browser E2E through the web/API/persistence path.

CI runs the same logical validation path on Node 26 with real PostGIS.

## Safe development reset

```powershell
pnpm dev:reset
```

The reset command refuses:
- environments other than `development` or `test`;
- non-local database hosts;
- database names outside the OpenVietGIS development/test namespace.

It downgrades and reapplies migrations. Never point development configuration at a production
database.

## Acceptance measurements

Run the scenarios in `specs/001-platform-foundation/quickstart.md`.

Two measurements require explicit evidence:
- clean supported-environment bootstrap: at most 20 minutes excluding separately recorded download time;
- repository navigation: an unfamiliar reviewer must locate governance/architecture/spec artifacts
  in under 10 minutes without assistance.

## Troubleshooting

### Node engine warning

If pnpm reports an unsupported engine, install Node.js 26 LTS. CI does not accept older Node
versions even if local exploratory commands happen to work.

### Port already in use

Development defaults:
- web: `5173`
- API: `8000`
- PostGIS host port: `54329`

Stop the conflicting local process or intentionally change the development-only configuration.

### PostGIS unavailable

Check:

```powershell
docker compose -f infra/dev/compose.yaml ps
```

Start it with:

```powershell
docker compose -f infra/dev/compose.yaml up -d postgres
```

### Schema not migrated

Run:

```powershell
pnpm db:migrate
```

### Missing configuration

Copy `.env.example` to the ignored local `.env`. The API intentionally fails fast when required
configuration is absent.