"""House Numbering official module typed storage, isolated from Core tables."""

from __future__ import annotations

from alembic import op

revision = "hn_0001_house_numbering"
down_revision = None
branch_labels = None
depends_on = None

_TABLES = (
    "rules",
    "areas",
    "routes",
    "buildings",
    "evidence",
    "address_numbers",
    "previews",
    "proposals",
    "proposal_items",
    "import_batches",
    "reconcile_cases",
    "surveys",
    "assignments",
    "restricted_households",
    "documents",
    "access_log",
)


def _rls(
    table: str, *, update: bool = True, delete: bool = False, private: bool = False
) -> None:
    op.execute(f"ALTER TABLE house_numbering.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE house_numbering.{table} FORCE ROW LEVEL SECURITY")
    private_guard = (
        " AND current_setting('openvietgis.extension_private_access', true) = 'house_numbering'"
        if private
        else ""
    )
    op.execute(f"""
        CREATE POLICY hn_{table}_project_scope ON house_numbering.{table}
        FOR ALL TO openvietgis_runtime
        USING (
            organization_id = NULLIF(current_setting('openvietgis.organization_id', true), '')::uuid
            AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
            {private_guard}
        )
        WITH CHECK (
            organization_id = NULLIF(current_setting('openvietgis.organization_id', true), '')::uuid
            AND project_id = NULLIF(current_setting('openvietgis.project_id', true), '')::uuid
            {private_guard}
        )
    """)
    grants = ["SELECT", "INSERT"]
    if update:
        grants.append("UPDATE")
    if delete:
        grants.append("DELETE")
    op.execute(
        f"GRANT {', '.join(grants)} ON house_numbering.{table} TO openvietgis_runtime"
    )


def upgrade() -> None:
    op.execute("CREATE SCHEMA house_numbering")
    op.execute("GRANT USAGE ON SCHEMA house_numbering TO openvietgis_runtime")
    op.execute("""
        CREATE OR REPLACE FUNCTION house_numbering.reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'house_numbering audit rows are append-only';
        END;
        $$
    """)

    op.execute("""
        CREATE TABLE house_numbering.rules (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            version varchar(64) NOT NULL,
            status varchar(24) NOT NULL,
            authority_ref varchar(500) NULL,
            left_odd boolean NOT NULL DEFAULT true,
            suffix_style varchar(16) NOT NULL DEFAULT 'letters',
            max_distance_m numeric(10,2) NOT NULL DEFAULT 150,
            sealed boolean NOT NULL DEFAULT false,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_rules_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT uq_hn_rules_version UNIQUE (organization_id, project_id, version),
            CONSTRAINT fk_hn_rules_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_rules_status CHECK (status IN ('draft','authoritative')),
            CONSTRAINT ck_hn_rules_suffix CHECK (suffix_style IN ('letters','dash')),
            CONSTRAINT ck_hn_rules_authority CHECK (
                status <> 'authoritative' OR (authority_ref IS NOT NULL AND length(btrim(authority_ref)) > 0)
            ),
            CONSTRAINT ck_hn_rules_revision CHECK (revision > 0),
            CONSTRAINT ck_hn_rules_distance CHECK (max_distance_m > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.areas (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            name varchar(200) NOT NULL,
            kind varchar(24) NOT NULL,
            parent_id uuid NULL,
            linked_source_id uuid NULL,
            linked_feature_id varchar(128) NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_areas_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_areas_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_areas_parent FOREIGN KEY (organization_id, project_id, parent_id)
                REFERENCES house_numbering.areas(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_areas_kind CHECK (kind IN ('current','historic','custom')),
            CONSTRAINT ck_hn_areas_revision CHECK (revision > 0),
            CONSTRAINT ck_hn_areas_name CHECK (name=btrim(name) AND length(name)>0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.routes (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            name varchar(200) NOT NULL,
            route_type varchar(16) NOT NULL,
            parent_route_id uuid NULL,
            prefix varchar(100) NULL,
            linked_source_id uuid NULL,
            linked_feature_id varchar(128) NULL,
            direction_state varchar(16) NOT NULL DEFAULT 'forward',
            source_label varchar(200) NOT NULL DEFAULT 'manual',
            status varchar(16) NOT NULL DEFAULT 'draft',
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_routes_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_routes_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_routes_parent FOREIGN KEY (organization_id, project_id, parent_route_id)
                REFERENCES house_numbering.routes(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_route_type CHECK (route_type IN ('street','alley')),
            CONSTRAINT ck_hn_route_direction CHECK (direction_state IN ('forward','reverse')),
            CONSTRAINT ck_hn_route_status CHECK (status IN ('draft','confirmed')),
            CONSTRAINT ck_hn_route_revision CHECK (revision > 0),
            CONSTRAINT ck_hn_route_name CHECK (name=btrim(name) AND length(name)>0),
            CONSTRAINT ck_hn_route_parent CHECK (
                (route_type='street' AND parent_route_id IS NULL)
                OR route_type='alley'
            )
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.buildings (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            route_id uuid NULL,
            area_id uuid NULL,
            parcel_ref varchar(200) NULL,
            linked_source_id uuid NULL,
            linked_feature_id varchar(128) NULL,
            eligibility varchar(16) NOT NULL DEFAULT 'unknown',
            ineligibility_reason varchar(500) NULL,
            state varchar(16) NOT NULL DEFAULT 'active',
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_buildings_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_buildings_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_buildings_route FOREIGN KEY (organization_id, project_id, route_id)
                REFERENCES house_numbering.routes(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_buildings_area FOREIGN KEY (organization_id, project_id, area_id)
                REFERENCES house_numbering.areas(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_building_eligibility CHECK (eligibility IN ('unknown','eligible','ineligible')),
            CONSTRAINT ck_hn_building_reason CHECK (
                eligibility <> 'ineligible' OR (ineligibility_reason IS NOT NULL AND length(btrim(ineligibility_reason))>0)
            ),
            CONSTRAINT ck_hn_building_state CHECK (state IN ('active','removed')),
            CONSTRAINT ck_hn_building_revision CHECK (revision > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.evidence (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            building_id uuid NULL,
            route_id uuid NULL,
            origin varchar(24) NOT NULL,
            raw_number varchar(200) NULL,
            source_reference varchar(500) NOT NULL,
            evidence_date date NULL,
            confidence varchar(16) NOT NULL,
            private_ref uuid NULL,
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_evidence_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_evidence_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_evidence_building FOREIGN KEY (organization_id, project_id, building_id)
                REFERENCES house_numbering.buildings(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_evidence_route FOREIGN KEY (organization_id, project_id, route_id)
                REFERENCES house_numbering.routes(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_evidence_origin CHECK (origin IN ('certificate','cad','survey','legacy','manual')),
            CONSTRAINT ck_hn_evidence_confidence CHECK (confidence IN ('authoritative','observed','estimated')),
            CONSTRAINT ck_hn_evidence_source CHECK (length(btrim(source_reference))>0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.address_numbers (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            building_id uuid NULL,
            route_id uuid NOT NULL,
            number_text varchar(200) NOT NULL,
            kind varchar(24) NOT NULL,
            side varchar(8) NULL,
            measure_m numeric(14,3) NULL,
            rule_id uuid NULL,
            source_evidence_id uuid NULL,
            retired_at timestamptz NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_numbers_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_numbers_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_numbers_building FOREIGN KEY (organization_id, project_id, building_id)
                REFERENCES house_numbering.buildings(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_numbers_route FOREIGN KEY (organization_id, project_id, route_id)
                REFERENCES house_numbering.routes(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_numbers_rule FOREIGN KEY (organization_id, project_id, rule_id)
                REFERENCES house_numbering.rules(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_numbers_evidence FOREIGN KEY (organization_id, project_id, source_evidence_id)
                REFERENCES house_numbering.evidence(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_number_kind CHECK (kind IN (
                'old','certificate','cad','survey','proposed','submitted','approved','reserved'
            )),
            CONSTRAINT ck_hn_number_text CHECK (length(btrim(number_text))>0),
            CONSTRAINT ck_hn_number_location CHECK (
                (side IS NULL AND measure_m IS NULL)
                OR (side IN ('left','right') AND measure_m IS NOT NULL AND measure_m>=0)
            ),
            CONSTRAINT ck_hn_number_revision CHECK (revision > 0)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_hn_official_number
        ON house_numbering.address_numbers (organization_id, project_id, route_id, number_text)
        WHERE retired_at IS NULL AND kind IN ('submitted','approved','reserved')
    """)

    op.execute("""
        CREATE TABLE house_numbering.previews (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            operation_id uuid NOT NULL,
            rule_id uuid NOT NULL,
            base_revisions jsonb NOT NULL,
            candidate_changes jsonb NOT NULL,
            warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
            expires_at timestamptz NOT NULL,
            applied_at timestamptz NULL,
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_previews_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT uq_hn_preview_operation UNIQUE (organization_id, project_id, operation_id),
            CONSTRAINT fk_hn_preview_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_preview_rule FOREIGN KEY (organization_id, project_id, rule_id)
                REFERENCES house_numbering.rules(organization_id, project_id, id) ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.proposals (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            scope_kind varchar(16) NOT NULL,
            scope_id uuid NOT NULL,
            rule_id uuid NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'draft',
            decision_comment varchar(1000) NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            submitted_at timestamptz NULL,
            decided_at timestamptz NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_proposals_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_proposal_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_proposal_rule FOREIGN KEY (organization_id, project_id, rule_id)
                REFERENCES house_numbering.rules(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_proposal_scope CHECK (scope_kind IN ('route','area')),
            CONSTRAINT ck_hn_proposal_status CHECK (status IN ('draft','submitted','approved','rejected')),
            CONSTRAINT ck_hn_proposal_revision CHECK (revision > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.proposal_items (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            proposal_id uuid NOT NULL,
            building_id uuid NOT NULL,
            proposed_number varchar(200) NOT NULL,
            source_number_id uuid NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_proposal_items_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT uq_hn_proposal_building UNIQUE (proposal_id, building_id),
            CONSTRAINT fk_hn_item_proposal FOREIGN KEY (organization_id, project_id, proposal_id)
                REFERENCES house_numbering.proposals(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_item_building FOREIGN KEY (organization_id, project_id, building_id)
                REFERENCES house_numbering.buildings(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_item_number FOREIGN KEY (organization_id, project_id, source_number_id)
                REFERENCES house_numbering.address_numbers(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_item_number CHECK (length(btrim(proposed_number))>0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.import_batches (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            source_fingerprint varchar(64) NOT NULL,
            source_name varchar(500) NOT NULL,
            source_crs integer NULL,
            mapping jsonb NOT NULL,
            read_count integer NOT NULL DEFAULT 0,
            accepted_count integer NOT NULL DEFAULT 0,
            rejected_count integer NOT NULL DEFAULT 0,
            original_artifact_id uuid NULL,
            status varchar(16) NOT NULL DEFAULT 'staging',
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            committed_at timestamptz NULL,
            CONSTRAINT uq_hn_imports_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT uq_hn_import_fingerprint UNIQUE (organization_id, project_id, source_fingerprint),
            CONSTRAINT fk_hn_import_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_import_fingerprint CHECK (source_fingerprint ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_hn_import_counts CHECK (
                read_count>=0 AND accepted_count>=0 AND rejected_count>=0
                AND read_count=accepted_count+rejected_count
            ),
            CONSTRAINT ck_hn_import_status CHECK (status IN ('staging','committed','failed'))
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.reconcile_cases (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            building_id uuid NULL,
            evidence_ids jsonb NOT NULL,
            case_class varchar(40) NOT NULL,
            estimated boolean NOT NULL DEFAULT false,
            status varchar(16) NOT NULL DEFAULT 'open',
            resolution varchar(1000) NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_reconcile_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_reconcile_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_reconcile_building FOREIGN KEY (organization_id, project_id, building_id)
                REFERENCES house_numbering.buildings(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_reconcile_class CHECK (case_class IN (
                'matched','number_mismatch','cad_certificate_mismatch','new_building',
                'no_longer_exists','not_surveyed','certificate_unmatched'
            )),
            CONSTRAINT ck_hn_reconcile_status CHECK (status IN ('open','resolved','ignored')),
            CONSTRAINT ck_hn_reconcile_revision CHECK (revision > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.surveys (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            client_uuid uuid NOT NULL,
            building_id uuid NULL,
            point_x double precision NULL,
            point_y double precision NULL,
            crs_code integer NULL,
            photo_artifact_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
            condition varchar(24) NOT NULL,
            state varchar(16) NOT NULL DEFAULT 'draft',
            recorded_by_actor_id uuid NOT NULL,
            submitted_by_actor_id uuid NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_surveys_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT uq_hn_survey_client UNIQUE (organization_id, project_id, client_uuid),
            CONSTRAINT fk_hn_survey_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_survey_building FOREIGN KEY (organization_id, project_id, building_id)
                REFERENCES house_numbering.buildings(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_survey_condition CHECK (condition IN ('house','vacant','removed','other')),
            CONSTRAINT ck_hn_survey_state CHECK (state IN ('draft','submitted','accepted','rejected')),
            CONSTRAINT ck_hn_survey_point CHECK (
                (point_x IS NULL AND point_y IS NULL AND crs_code IS NULL)
                OR (point_x IS NOT NULL AND point_y IS NOT NULL AND crs_code IS NOT NULL)
            ),
            CONSTRAINT ck_hn_survey_revision CHECK (revision > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.assignments (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            scope_kind varchar(16) NOT NULL,
            scope_id uuid NOT NULL,
            assignee_actor_id uuid NOT NULL,
            target_count integer NULL,
            starts_on date NOT NULL,
            ends_on date NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_assignments_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_assignment_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_assignment_scope CHECK (scope_kind IN ('area','route')),
            CONSTRAINT ck_hn_assignment_target CHECK (target_count IS NULL OR target_count>=0),
            CONSTRAINT ck_hn_assignment_dates CHECK (ends_on IS NULL OR ends_on>=starts_on),
            CONSTRAINT ck_hn_assignment_revision CHECK (revision > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.restricted_households (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            building_id uuid NOT NULL,
            purpose varchar(500) NOT NULL,
            consent boolean NOT NULL DEFAULT false,
            lawful_basis_ref varchar(500) NULL,
            protected_data jsonb NOT NULL,
            expires_at timestamptz NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_households_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_household_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_household_building FOREIGN KEY (organization_id, project_id, building_id)
                REFERENCES house_numbering.buildings(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_household_purpose CHECK (length(btrim(purpose))>0),
            CONSTRAINT ck_hn_household_basis CHECK (
                NOT consent OR lawful_basis_ref IS NOT NULL OR length(btrim(purpose))>0
            ),
            CONSTRAINT ck_hn_household_revision CHECK (revision > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.documents (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            building_id uuid NOT NULL,
            number_id uuid NULL,
            doc_type varchar(24) NOT NULL,
            template_revision varchar(100) NOT NULL,
            status varchar(24) NOT NULL,
            artifact_id uuid NULL,
            issued_at timestamptz NULL,
            replaces_document_id uuid NULL,
            revision bigint NOT NULL DEFAULT 1,
            created_by_actor_id uuid NOT NULL,
            updated_by_actor_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_documents_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_doc_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_doc_building FOREIGN KEY (organization_id, project_id, building_id)
                REFERENCES house_numbering.buildings(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_doc_number FOREIGN KEY (organization_id, project_id, number_id)
                REFERENCES house_numbering.address_numbers(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_hn_doc_replaces FOREIGN KEY (organization_id, project_id, replaces_document_id)
                REFERENCES house_numbering.documents(organization_id, project_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_hn_doc_type CHECK (doc_type IN ('inspection','certificate','house_form','plate')),
            CONSTRAINT ck_hn_doc_status CHECK (status IN ('draft','official','void','reissue_required')),
            CONSTRAINT ck_hn_doc_issue CHECK (
                (status IN ('official','reissue_required'))=(issued_at IS NOT NULL)
            ),
            CONSTRAINT ck_hn_doc_revision CHECK (revision > 0)
        )
    """)

    op.execute("""
        CREATE TABLE house_numbering.access_log (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            actor_id uuid NOT NULL,
            action varchar(64) NOT NULL,
            resource_type varchar(64) NOT NULL,
            resource_id uuid NULL,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_hn_access_log_scope UNIQUE (organization_id, project_id, id),
            CONSTRAINT fk_hn_access_log_project FOREIGN KEY (organization_id, project_id)
                REFERENCES workspace.projects(organization_id, id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE TRIGGER trg_hn_access_log_immutable
        BEFORE UPDATE OR DELETE ON house_numbering.access_log
        FOR EACH ROW EXECUTE FUNCTION house_numbering.reject_mutation()
    """)

    immutable = {"evidence", "access_log"}
    private = {"restricted_households"}
    deletable = {"areas", "routes", "previews"}
    for table in _TABLES:
        _rls(
            table,
            update=table not in immutable,
            delete=table in deletable,
            private=table in private,
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE house_numbering.{table}")
    op.execute("DROP FUNCTION house_numbering.reject_mutation()")
    op.execute("DROP SCHEMA house_numbering")
