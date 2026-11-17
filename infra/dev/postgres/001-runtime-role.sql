DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'openvietgis_runtime') THEN
        CREATE ROLE openvietgis_runtime LOGIN PASSWORD 'openvietgis-runtime-dev'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    ELSE
        ALTER ROLE openvietgis_runtime LOGIN PASSWORD 'openvietgis-runtime-dev'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END
$$;
