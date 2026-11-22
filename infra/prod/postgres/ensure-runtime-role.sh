#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${RUNTIME_DB_PASSWORD:?RUNTIME_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1   --host "$PGHOST"   --username "$PGUSER"   --dbname "$PGDATABASE"   --set=runtime_password="$RUNTIME_DB_PASSWORD" <<'SQL'
SELECT format(
  'CREATE ROLE openvietgis_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'runtime_password'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'openvietgis_runtime'
)
\gexec

SELECT format(
  'ALTER ROLE openvietgis_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'runtime_password'
)
WHERE EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'openvietgis_runtime'
)
\gexec
SQL
