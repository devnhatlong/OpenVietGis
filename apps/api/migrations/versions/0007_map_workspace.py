"""Add atomic project map configuration, receipts and immutable revisions."""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_map_workspace"
down_revision: str | Sequence[str] | None = "0006_spatial_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPE = (
    "organization_id = NULLIF(current_setting('openvietgis.organization_id', true), '')::uuid "
    "AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid"
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA maps")
    op.execute("REVOKE ALL ON SCHEMA maps FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA maps TO openvietgis_runtime")
    op.execute("""
        CREATE FUNCTION maps.valid_number(v jsonb, lo numeric, hi numeric)
        RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
            SELECT COALESCE(CASE WHEN jsonb_typeof(v)='number'
                THEN (v#>>'{}')::numeric BETWEEN lo AND hi ELSE false END,false)
        $$
    """)
    op.execute("""
        CREATE FUNCTION maps.valid_configuration(v jsonb) RETURNS boolean
        LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
        DECLARE item jsonb; s jsonb; p jsonb; ids uuid[] := ARRAY[]::uuid[]; ident uuid;
        BEGIN
            IF v IS NULL OR jsonb_typeof(v)<>'object'
                OR NOT v ?& ARRAY['layers','basemap','default_viewpoint']
                OR v-ARRAY['layers','basemap','default_viewpoint']<>'{}'::jsonb
                OR v->'basemap' IS DISTINCT FROM '\"grid\"'::jsonb
                OR jsonb_typeof(v->'layers')<>'array'
            THEN RETURN false; END IF;
            IF jsonb_array_length(v->'layers')>32 THEN RETURN false; END IF;
            FOR item IN SELECT value FROM jsonb_array_elements(v->'layers') LOOP
                IF jsonb_typeof(item)<>'object'
                    OR NOT item ?& ARRAY['layer_id','visible','style']
                    OR item-ARRAY['layer_id','visible','style']<>'{}'::jsonb
                    OR jsonb_typeof(item->'layer_id')<>'string'
                    OR jsonb_typeof(item->'visible')<>'boolean'
                THEN RETURN false; END IF;
                ident := (item->>'layer_id')::uuid;
                IF ident=ANY(ids) THEN RETURN false; END IF;
                ids := array_append(ids,ident);
                s:=item->'style';
                IF jsonb_typeof(s)<>'object'
                    OR NOT s ?& ARRAY['color','opacity','width','radius']
                    OR s-ARRAY['color','opacity','width','radius']<>'{}'::jsonb
                    OR jsonb_typeof(s->'color')<>'string'
                    OR (s->>'color') !~ '^#[0-9A-F]{6}$'
                    OR NOT maps.valid_number(s->'opacity',0,1)
                    OR NOT maps.valid_number(s->'width',1,12)
                    OR NOT maps.valid_number(s->'radius',2,20)
                THEN RETURN false; END IF;
            END LOOP;
            p:=v->'default_viewpoint';
            IF p='null'::jsonb THEN RETURN true; END IF;
            RETURN COALESCE(
                jsonb_typeof(p)='object'
                AND p ?& ARRAY['longitude','latitude','zoom','bearing','pitch','crs']
                AND p-ARRAY['longitude','latitude','zoom','bearing','pitch','crs']='{}'::jsonb
                AND maps.valid_number(p->'longitude',-180,180)
                AND maps.valid_number(p->'latitude',-85.05112878,85.05112878)
                AND maps.valid_number(p->'zoom',0,22)
                AND maps.valid_number(p->'bearing',-180,180)
                AND maps.valid_number(p->'pitch',0,60)
                AND p->'crs'='4326'::jsonb,false);
        EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range
            THEN RETURN false;
        END $$
    """)
    for signature in ("valid_number(jsonb,numeric,numeric)", "valid_configuration(jsonb)"):
        op.execute(f"REVOKE ALL ON FUNCTION maps.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION maps.{signature} TO openvietgis_runtime")
    op.execute("""
        CREATE TABLE maps.project_maps (
            id uuid NOT NULL PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            configuration_revision bigint NOT NULL,
            configuration jsonb NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT fk_map_project FOREIGN KEY(organization_id,project_id)
                REFERENCES workspace.projects(organization_id,id) ON DELETE RESTRICT,
            CONSTRAINT uq_map_project UNIQUE(organization_id,project_id),
            CONSTRAINT uq_map_scope UNIQUE(organization_id,project_id,id),
            CONSTRAINT ck_map_revision CHECK(configuration_revision BETWEEN 1 AND 9007199254740991),
            CONSTRAINT ck_map_configuration CHECK(maps.valid_configuration(configuration))
        )
    """)
    op.execute("""
        CREATE TABLE maps.map_operations (
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            operation_id uuid NOT NULL,
            map_id uuid NOT NULL,
            actor_type varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            request_hash varchar(64) NOT NULL,
            committed_revision bigint NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT pk_map_operation PRIMARY KEY(organization_id,project_id,operation_id),
            CONSTRAINT uq_map_operation_evidence UNIQUE(
                organization_id,project_id,operation_id,map_id,committed_revision,actor_type,actor_id),
            CONSTRAINT uq_map_operation_revision
                UNIQUE(organization_id,project_id,map_id,committed_revision),
            CONSTRAINT fk_map_operation_map FOREIGN KEY(organization_id,project_id,map_id)
                REFERENCES maps.project_maps(organization_id,project_id,id) ON DELETE RESTRICT,
            CONSTRAINT ck_map_operation_actor CHECK(actor_type IN('human','service_principal')),
            CONSTRAINT ck_map_operation_hash CHECK(request_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_map_operation_revision
                CHECK(committed_revision BETWEEN 1 AND 9007199254740991)
        )
    """)
    op.execute("""
        CREATE TABLE maps.map_revisions (
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            map_id uuid NOT NULL,
            configuration_revision bigint NOT NULL,
            prior_revision bigint NOT NULL,
            operation_id uuid NOT NULL,
            actor_type varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            actor_display_snapshot varchar(200) NOT NULL,
            created_at timestamptz NOT NULL,
            before_configuration jsonb,
            after_configuration jsonb NOT NULL,
            audit_event_id uuid NOT NULL,
            CONSTRAINT pk_map_revision
                PRIMARY KEY(organization_id,project_id,map_id,configuration_revision),
            CONSTRAINT uq_map_revision_operation UNIQUE(organization_id,project_id,operation_id),
            CONSTRAINT fk_map_revision_map FOREIGN KEY(organization_id,project_id,map_id)
                REFERENCES maps.project_maps(organization_id,project_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_map_revision_operation FOREIGN KEY(
                organization_id,project_id,operation_id,map_id,configuration_revision,actor_type,actor_id)
                REFERENCES maps.map_operations(
                    organization_id,project_id,operation_id,map_id,
                    committed_revision,actor_type,actor_id)
                DEFERRABLE INITIALLY DEFERRED,
            CONSTRAINT fk_map_revision_audit FOREIGN KEY(organization_id,audit_event_id)
                REFERENCES audit.audit_events(organization_id,id) ON DELETE RESTRICT,
            CONSTRAINT ck_map_revision_sequence CHECK(
                configuration_revision BETWEEN 1 AND 9007199254740991
                AND prior_revision=configuration_revision-1
                AND (before_configuration IS NULL)=(prior_revision=0)),
            CONSTRAINT ck_map_revision_configurations CHECK(
                maps.valid_configuration(after_configuration)
                AND (before_configuration IS NULL OR
                    maps.valid_configuration(before_configuration))
                AND (before_configuration IS NULL OR
                    before_configuration<>after_configuration)),
            CONSTRAINT ck_map_revision_actor CHECK(
                actor_type IN('human','service_principal')
                AND length(actor_display_snapshot) BETWEEN 1 AND 200
                AND actor_display_snapshot=btrim(actor_display_snapshot))
        )
    """)
    op.execute("""
        ALTER TABLE maps.map_operations ADD CONSTRAINT fk_operation_revision
            FOREIGN KEY(organization_id,project_id,map_id,committed_revision)
            REFERENCES maps.map_revisions(organization_id,project_id,map_id,configuration_revision)
            DEFERRABLE INITIALLY DEFERRED
    """)
    op.execute("""
        ALTER TABLE maps.project_maps ADD CONSTRAINT fk_map_current_revision
            FOREIGN KEY(organization_id,project_id,id,configuration_revision)
            REFERENCES maps.map_revisions(organization_id,project_id,map_id,configuration_revision)
            DEFERRABLE INITIALLY DEFERRED
    """)
    op.execute("""
        CREATE FUNCTION maps.check_current_revision() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        DECLARE actual jsonb;
        BEGIN
            IF TG_OP='UPDATE' AND (
                NEW.id<>OLD.id OR NEW.organization_id<>OLD.organization_id
                OR NEW.project_id<>OLD.project_id
                OR NEW.configuration_revision<>OLD.configuration_revision+1
            ) THEN RAISE EXCEPTION 'invalid map transition' USING ERRCODE='23514'; END IF;
            SELECT after_configuration INTO actual FROM maps.map_revisions
                WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
                    AND map_id=NEW.id AND configuration_revision=NEW.configuration_revision;
            IF NOT FOUND OR actual IS DISTINCT FROM NEW.configuration
            THEN RAISE EXCEPTION 'map state and evidence disagree' USING ERRCODE='23514'; END IF;
            RETURN NULL;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION maps.check_revision_evidence() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog AS $$
        DECLARE actual jsonb; valid_audit boolean;
        BEGIN
            IF NEW.prior_revision>0 THEN
                SELECT after_configuration INTO actual FROM maps.map_revisions
                    WHERE organization_id=NEW.organization_id AND project_id=NEW.project_id
                        AND map_id=NEW.map_id AND configuration_revision=NEW.prior_revision;
                IF NOT FOUND OR actual IS DISTINCT FROM NEW.before_configuration
                THEN RAISE EXCEPTION 'map prior evidence disagrees' USING ERRCODE='23514'; END IF;
            END IF;
            SELECT actor_type=NEW.actor_type AND actor_id=NEW.actor_id
                AND actor_display_snapshot=NEW.actor_display_snapshot
                AND resource_type='project_map' AND resource_id=NEW.map_id
                AND action='map.configuration.saved' AND outcome='success'
                AND created_at=NEW.created_at
                AND metadata=jsonb_build_object(
                    'project_id',NEW.project_id::text,
                    'operation_id',NEW.operation_id::text,
                    'configuration_revision',NEW.configuration_revision)
            INTO valid_audit FROM audit.audit_events
                WHERE organization_id=NEW.organization_id AND id=NEW.audit_event_id;
            IF NOT FOUND OR valid_audit IS DISTINCT FROM true
            THEN RAISE EXCEPTION 'map audit evidence disagrees' USING ERRCODE='23514'; END IF;
            RETURN NULL;
        END $$
    """)
    for name in ("check_current_revision()", "check_revision_evidence()"):
        op.execute(f"REVOKE ALL ON FUNCTION maps.{name} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION maps.{name} TO openvietgis_runtime")
    op.execute("""
        CREATE CONSTRAINT TRIGGER project_map_evidence
        AFTER INSERT OR UPDATE ON maps.project_maps DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION maps.check_current_revision()
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER map_revision_evidence
        AFTER INSERT ON maps.map_revisions DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION maps.check_revision_evidence()
    """)
    for table in ("project_maps", "map_operations", "map_revisions"):
        op.execute(f"GRANT SELECT,INSERT ON maps.{table} TO openvietgis_runtime")
        op.execute(f"ALTER TABLE maps.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE maps.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_project_scope ON maps.{table}
            FOR ALL TO openvietgis_runtime USING ({_SCOPE}) WITH CHECK ({_SCOPE})""")
    op.execute("""
        GRANT UPDATE(configuration_revision,configuration,updated_at)
        ON maps.project_maps TO openvietgis_runtime
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE maps.project_maps DROP CONSTRAINT fk_map_current_revision")
    op.execute("ALTER TABLE maps.map_operations DROP CONSTRAINT fk_operation_revision")
    for table in ("map_revisions", "map_operations", "project_maps"):
        op.drop_table(table, schema="maps")
    op.execute("DROP FUNCTION maps.check_revision_evidence()")
    op.execute("DROP FUNCTION maps.check_current_revision()")
    op.execute("DROP FUNCTION maps.valid_configuration(jsonb)")
    op.execute("DROP FUNCTION maps.valid_number(jsonb,numeric,numeric)")
    op.execute("DROP SCHEMA maps")
