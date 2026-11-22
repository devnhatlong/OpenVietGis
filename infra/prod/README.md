# Proposed small-team self-host container fixture

**Status: proposed configuration only. Not an approved production release.**
No images have been certified, no live installation has been migrated by this
remediation, and dependency readiness is not a release capability gate.

## Configuration contract

- Python 3.13, PostGIS 18 / 3.7, Node 26 and the locked pnpm version follow the
  product's declared development/validation baseline. Image digest selection,
  software supply-chain review and an isolated build/start drill are outstanding.
- Create a fresh dedicated Compose project/volumes for verification. PostgreSQL
  18's volume is mounted at `/var/lib/postgresql`. The initialization script
  provisions a restricted `openvietgis_runtime` role only on a fresh volume.
  Do not apply the fixture to an existing database or reset a volume.
- Set all secrets from an external protected secret store. The proposed
  fixture uses Compose interpolation; do not print rendered configuration with
  real secrets, commit secret environment files, or copy them into backups.
  Use distinct unpredictable session, CSRF, bootstrap and database credentials.
- Required variables: `POSTGRES_PASSWORD`, `RUNTIME_DB_PASSWORD`,
  `RUNTIME_DATABASE_URL`, `MIGRATION_DATABASE_URL`, `SESSION_SECRET`,
  `CSRF_SECRET`, `BOOTSTRAP_SECRET`, `PUBLIC_HTTPS_ORIGIN`,
  `OIDC_PROVIDERS_JSON`. Optional: `POSTGRES_USER`, `POSTGRES_DB`,
  `HTTP_PORT`. Database URLs are explicit SQLAlchemy
  `postgresql+psycopg` URIs to the same database at host `postgres`,
  with correctly URL-encoded passwords matching the corresponding role.
  Do not include query overrides. The API receives the restricted runtime URL
  only; the separate migration service receives the owner URL and must finish
  successfully before the API starts. Runtime role verification remains active.
- The frontend is bound only to loopback; a separately configured TLS reverse
  proxy must serve the public HTTPS origin and forward requests to that
  listener. Production Settings require HTTPS origins, secure cookies, and
  distinct application secrets of at least 32 characters. The production API
  CORS policy admits only the configured web origin. Production Settings also
  reject missing or non-HTTPS OIDC issuers.
- Configure an independent HTTPS OIDC provider and approved issuer/client
  settings, including the exact application redirect and trusted TLS chain.
  This fixture deliberately does not deploy or claim to configure Keycloak.
  Authentication, bootstrap and tenant workflows with the selected provider,
  TLS termination, network restrictions, monitoring, rotation, backup
  retention, and operator approval remain acceptance gates.

## Verification boundaries

Validate configuration with dummy inputs only, e.g. using
`docker compose --env-file /dev/null -f infra/prod/docker-compose.prod.yml config --quiet`
after supplying a complete **synthetic** environment. Do not run this against
production secrets or a deployed Compose project. Configuration parse and
Settings validation do not demonstrate that images build, services start,
migrations finish, external identity works, or a production RPO/RTO is met.

The recovery procedure uses signed v4 manifests with externally held keys; see
[recovery authentication](../../specs/018-full-product-audit/remediation/G010-recoverable-backup/authenticated-recovery.md).
No release certification is granted by this profile.
