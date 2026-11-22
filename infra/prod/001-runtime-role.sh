#!/bin/sh
# Only the proposed fixture's fresh PostgreSQL volume. Do not reuse this to
# rotate an existing database's credentials.
set -eu
: "${RUNTIME_DB_PASSWORD:?RUNTIME_DB_PASSWORD must be set}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -X -v ON_ERROR_STOP=1 <<'SQL'
\getenv runtime_password RUNTIME_DB_PASSWORD
CREATE ROLE openvietgis_runtime LOGIN PASSWORD :'runtime_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
SQL
