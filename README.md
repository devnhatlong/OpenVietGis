# OpenVietGIS

OpenVietGIS is a platform-first spatial workspace for the web. Spec 001 intentionally builds only
the architecture runway and a disposable non-GIS vertical slice.

## Product direction and roadmap

- [Product direction and release outcomes](docs/product.md)
- [Product roadmap, dependencies, milestones, and feature status](ROADMAP.md)
- Foundation: [Spec 001](specs/001-platform-foundation/spec.md), roadmap entry [R001](ROADMAP.md#r001)
- Identity/organization/tenancy: [Spec 002](specs/002-identity-organization-tenancy/spec.md), roadmap entry [R002](ROADMAP.md#r002)

Only 001 and 002 have feature specifications at the roadmap baseline. Future numbered labels are
provisional capability slices, not implemented functionality. Before opening another feature, read
the product direction and its roadmap entry; update both directions of the roadmap/spec links.

## Governance and architecture

- Constitution: `.specify/memory/constitution.md`
- ADR index: `docs/adr/README.md`
- Architecture boundaries: `docs/architecture.md`
- Accepted foundation specification and evidence: `specs/001-platform-foundation/`

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
docker compose -f infra/dev/compose.yaml up -d postgres postgres-test
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

The shell exposes real identity, Organization, Workspace and Project flows, with scoped access,
invitation, service identity, and audit contracts. Foundation readiness remains at
`/api/v1/health/ready`. The disposable Spec 001 sample route, SDK, UI and table are retired by
migration `0005_retire_foundation_sample`; existing sample-only records are intentionally removed.
The historical Spec 001 evidence remains unchanged. Create/read/restart and browser persistence
regressions now exercise an authenticated tenant Project instead.

It does **not** contain map rendering, GIS editing, billing, processing, field/offline workflows,
or House Numbering.

## Identity and tenancy development profile

Spec 002 adds a real OIDC reference profile for development and E2E validation. Keycloak is a
reference provider only; OpenVietGIS product identity remains provider-neutral.

Start PostgreSQL plus the synthetic Keycloak realm:

```powershell
pnpm dev:identity
```

Reference endpoints and identities:

- Keycloak: `http://127.0.0.1:18080`
- Realm: `openvietgis`
- Synthetic users: `owner-a`, `member-a`, `member-b`
- All fixture credentials are development/test-only and live in
  `infra/dev/keycloak/realm-openvietgis.json`.
- Copy the current `.env.example` to ignored `.env` before running the API.

The application uses OIDC only for human authentication. Organization membership, scoped
authorization, tenant isolation, service principals, and audit semantics are owned by OpenVietGIS.
Provider tokens must not be stored in browser local/session storage.

The complete security/tenancy acceptance flow is maintained in
`specs/002-identity-organization-tenancy/quickstart.md`.

## Contract generation

Spec 002 OpenAPI contracts generate TypeScript types into the client SDK:

```powershell
pnpm contracts:generate
pnpm validate:contracts
```

Generated files are committed so contract drift is visible in code review.

## Baseline validation

With the development and dedicated test PostGIS services running:

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

Integration and browser tests use the dedicated local `openvietgis_test` database on port
`54330`. They ignore the application `OPENVIETGIS_DATABASE_URL`; an optional exported
`OPENVIETGIS_TEST_DATABASE_URL` must still name `openvietgis_test` on localhost/127.0.0.1.
URL query parameters and other drivers are rejected before migrations or child processes run.
Migration tests may downgrade/recreate the dedicated test schema; never store working data there.
Development application data remains on port `54329`.

## Safe development reset

```powershell
pnpm dev:reset
```

The reset command refuses:
- environments other than `development` or `test`;
- non-local database hosts;
- database names other than exactly `openvietgis`, `openvietgis_dev`, or `openvietgis_test`.

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
- PostGIS development host port: `54329`
- PostGIS dedicated test host port: `54330`

Stop the conflicting local process or intentionally change the development-only configuration.

### PostGIS unavailable

Check:

```powershell
docker compose -f infra/dev/compose.yaml ps
```

Start it with:

```powershell
docker compose -f infra/dev/compose.yaml up -d postgres postgres-test
```

### Schema not migrated

Run:

```powershell
pnpm db:migrate
```

### Missing configuration

Copy `.env.example` to the ignored local `.env`. The API intentionally fails fast when required
configuration is absent.