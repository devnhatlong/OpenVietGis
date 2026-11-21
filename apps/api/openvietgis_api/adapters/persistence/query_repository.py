"""R007 RLS-enforced PostGIS repository for typed attribute & bounded spatial queries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.adapters.persistence.spatial_repository import (
    _read_native_wkb,
    _source_from_row,
)
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformDomainError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.domains.queries.domain import (
    MAX_PAGE_POSITIONS,
    MAX_QUERY_FEATURES,
    MAX_QUERY_LIMIT,
    MAX_QUERY_OFFSET,
    MAX_QUERY_POSITIONS,
    MAX_REFERENCE_FEATURES,
    MAX_REFERENCE_POSITIONS,
    QUERY_STATEMENT_TIMEOUT,
    SavedQueryRecord,
    SpatialPredicate,
    compile_attribute_filter,
    compile_sort,
    parse_drawn_area,
)
from openvietgis_api.domains.spatial.crs import get_transformation_profile
from openvietgis_api.domains.spatial.domain import (
    WEB_MERCATOR_MAX,
    DataSource,
    FieldType,
    GeometryFamily,
    Lifecycle,
    NativeGeometry,
    SourceField,
    SpatialValidationError,
    ValidationState,
    canonical_attribute_value,
    canonical_manifest_digest,
    validate_ready_geometry,
    validate_revision_token,
)


def _saved_query_from_row(row: RowMapping) -> SavedQueryRecord:
    return SavedQueryRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        layer_id=row["layer_id"],
        name=str(row["name"]),
        description=str(row["description"]),
        attribute_filter=dict(row["attribute_filter"])
        if row["attribute_filter"] is not None
        else None,
        spatial_filter=dict(row["spatial_filter"]) if row["spatial_filter"] is not None else None,
        sort_field=str(row["sort_field"]) if row["sort_field"] is not None else None,
        sort_direction=str(row["sort_direction"]),
        created_by_actor_id=row["created_by_actor_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlQueryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _prepare(self, context: AuthorizationContext, *, permission: Permission) -> None:
        prepare_project_scope(self._session, context, permission=permission)

    def _resolve_layer_source(
        self, org_id: UUID, project_id: UUID, layer_id: UUID
    ) -> tuple[DataSource, list[SourceField]]:
        row = (
            self._session.execute(
                text("""
                SELECT s.*
                FROM spatial.layers l
                JOIN spatial.data_sources s
                  ON s.organization_id = l.organization_id
                 AND s.project_id = l.project_id
                 AND s.id = l.source_id
                WHERE l.organization_id = :org AND l.project_id = :proj AND l.id = :lid
                  AND l.lifecycle = 'active'
                FOR SHARE OF s, l
            """),
                {"org": org_id, "proj": project_id, "lid": layer_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("layer not found")
        source = _source_from_row(row)
        if source.lifecycle != Lifecycle.ACTIVE or source.validation_state != ValidationState.READY:
            raise PlatformValidationError("layer source is not ready", code="SOURCE_NOT_READY")
        frows = (
            self._session.execute(
                text("""
                SELECT field_id, name, ordinal, type, nullable, schema_revision
                FROM spatial.source_fields
                WHERE organization_id = :org AND project_id = :proj AND source_id = :src
                ORDER BY ordinal ASC
            """),
                {"org": org_id, "proj": project_id, "src": source.id},
            )
            .mappings()
            .all()
        )
        fields = [
            SourceField(
                organization_id=org_id,
                project_id=project_id,
                source_id=source.id,
                field_id=str(r["field_id"]),
                name=str(r["name"]),
                ordinal=int(r["ordinal"]),
                type=FieldType(str(r["type"])),
                nullable=bool(r["nullable"]),
                schema_revision=str(r["schema_revision"]),
            )
            for r in frows
        ]
        if any(field.schema_revision != source.schema_revision for field in fields):
            raise PlatformConflictError("source schema pins disagree", code="STALE_SCHEMA_REVISION")
        return source, fields

    @staticmethod
    def _pin(source: DataSource, layer_id: UUID) -> dict[str, Any]:
        return {
            "layer_id": str(layer_id),
            "source_id": str(source.id),
            "content_revision": source.content_revision,
            "schema_revision": source.schema_revision,
            "stored_crs": source.stored_crs,
        }

    @staticmethod
    def _source_params(source: DataSource) -> dict[str, Any]:
        return {
            "org": source.organization_id,
            "proj": source.project_id,
            "src": source.id,
            "crev": source.content_revision,
            "srev": source.schema_revision,
            "srid": source.stored_crs,
            "gtype": f"ST_{source.geometry_family.value}",
        }

    def _validate_snapshot(self, source: DataSource, fields: list[SourceField]) -> None:
        # All ready rows must agree with the pinned source before any exact count
        # is exposed. Never turn malformed/unsupported input into a zero match.
        if source.feature_count is None or source.feature_count > MAX_QUERY_FEATURES:
            raise PlatformValidationError(
                "target exceeds query feature limit", code="QUERY_TOO_COMPLEX"
            )
        domain = (
            " AND ST_CoveredBy(geometry, ST_MakeEnvelope(-180,-90,180,90,:srid))"
            " AND ST_XMax(geometry)-ST_XMin(geometry)<=180"
            if source.stored_crs in (4326, 4756)
            else " AND ST_CoveredBy(geometry, ST_MakeEnvelope(-:merc,-:merc,:merc,:merc,:srid))"
            if source.stored_crs == 3857
            else ""
        )
        params = self._source_params(source) | {"merc": WEB_MERCATOR_MAX}
        # Validate storage logical shape. Numeric casts must not silently accept
        # noncanonical or wrong-type attributes, including off-page records.
        checks = ["jsonb_typeof(attributes)='object'"]
        fields_keys = [field.field_id for field in fields]
        if fields_keys:
            params["expected_keys"] = fields_keys
            checks.append("attributes ?& CAST(:expected_keys AS text[])")
        params["expected_count"] = len(fields)
        checks.append("(SELECT count(*) FROM jsonb_object_keys(attributes))=:expected_count")
        for field in fields:
            key = field.field_id
            value = f"(attributes -> '{key}')"
            scalar = f"(attributes ->> '{key}')"
            type_check = {
                FieldType.TEXT: f"jsonb_typeof({value})='string' AND char_length({scalar})<=4096",
                FieldType.INTEGER: (
                    f"jsonb_typeof({value})='number' AND CASE WHEN {scalar} ~ '^-?[0-9]{{1,10}}$'"
                    f" THEN CAST({scalar} AS numeric) "
                    "BETWEEN -2147483648 AND 2147483647 ELSE false END"
                ),
                FieldType.DECIMAL: (
                    f"jsonb_typeof({value})='string' AND {scalar} "
                    "~ '^-?(0|[1-9][0-9]*)([.][0-9]*[1-9])?$'"
                    f" AND {scalar}<>'-0' "
                    f"AND char_length(replace(replace({scalar},'-',''),'.',''))<=38"
                    f" AND char_length(split_part({scalar},'.',2))<=18"
                ),
                FieldType.BOOLEAN: f"jsonb_typeof({value})='boolean'",
                FieldType.TIMESTAMP: (
                    f"jsonb_typeof({value})='string' AND {scalar} ~ '^[0-9]{{4}}-.*Z$'"
                ),
            }[field.type]
            if field.nullable:
                type_check = f"jsonb_typeof({value})='null' OR ({type_check})"
            checks.append(f"({type_check})")
        attributes_valid = " AND ".join(checks)
        row = (
            self._session.execute(
                text(f"""
            SELECT COUNT(*) AS cnt, COALESCE(SUM(ST_NPoints(geometry)),0) AS positions,
                COALESCE(bool_and((
                    content_revision=:crev AND schema_revision=:srev
                    AND geometry_state='present' AND ST_SRID(geometry)=:srid
                    AND ST_GeometryType(geometry)=:gtype AND ST_Zmflag(geometry)=0
                    AND ST_NPoints(geometry) BETWEEN 1 AND 4096
                    AND NOT ST_IsEmpty(geometry) AND ST_IsValid(geometry)
                    {domain} AND ({attributes_valid})
                ) IS TRUE), true) AS valid
            FROM spatial.reference_features
            WHERE organization_id=:org AND project_id=:proj AND source_id=:src
        """),
                params,
            )
            .mappings()
            .one()
        )
        if row["cnt"] != source.feature_count or not row["valid"]:
            raise PlatformValidationError(
                "source does not match ready snapshot", code="INVALID_QUERY_SOURCE"
            )
        if row["positions"] > MAX_QUERY_POSITIONS:
            raise PlatformValidationError("target exceeds position limit", code="QUERY_TOO_COMPLEX")

    def _checked_geometry(
        self, geometry: NativeGeometry, target_srid: int
    ) -> tuple[NativeGeometry, str | None]:
        # Only explicit, non-fixture-dependent, single-step R003 verified edges
        # are available here. Never implicit ST_Transform or guessed CRS.
        assert geometry.srid is not None
        profile = None
        if geometry.srid != target_srid:
            profile = get_transformation_profile(geometry.srid, target_srid)
            if profile is None or profile.requires_trusted_fixture or len(profile.steps) != 1:
                raise PlatformValidationError(
                    "no accepted query CRS transformation", code="UNSUPPORTED_CRS"
                )
            if geometry.srid in (4326, 4756) and any(
                not profile.geographic_bounds.contains(x, y)
                for x, y in validate_ready_geometry(geometry)
            ):
                raise PlatformValidationError(
                    "geometry outside transformation area", code="UNSUPPORTED_CRS"
                )
        expr = "native.geom"
        params: dict[str, Any] = {"wkt": geometry.to_wkt(), "source_srid": geometry.srid}
        if profile:
            step = profile.steps[0]
            fn = "ST_InverseTransformPipeline" if step.inverse else "ST_TransformPipeline"
            expr = f"{fn}({expr},:pipeline,:target_srid)"
            params.update(pipeline=step.pipeline, target_srid=target_srid)
        row = (
            self._session.execute(
                text(f"""
            WITH native AS MATERIALIZED (
                SELECT ST_GeomFromText(:wkt,:source_srid) AS geom
            ), result AS MATERIALIZED (
                SELECT CASE WHEN ST_IsValid(native.geom) THEN {expr} END AS geom FROM native
            )
            SELECT ST_IsValid(geom) AS valid, ST_SRID(geom) AS srid,
                CASE WHEN ST_NPoints(geom) BETWEEN 1 AND 4096 AND ST_Zmflag(geom)=0
                    AND NOT ST_IsEmpty(geom) THEN ST_AsBinary(geom,'NDR') ELSE NULL END AS wkb
            FROM result
        """),
                params,
            )
            .mappings()
            .one()
        )
        if not row["valid"] or row["wkb"] is None or row["srid"] != target_srid:
            raise PlatformValidationError("invalid query geometry", code="INVALID_SPATIAL_FILTER")
        try:
            checked = _read_native_wkb(bytes(row["wkb"]), target_srid)
            positions = validate_ready_geometry(
                checked,
                GeometryFamily(geometry.type),
                target_srid,
                output_roundoff=bool(profile),
            )
        except SpatialValidationError as exc:
            raise PlatformValidationError(
                "invalid query geometry", code="INVALID_SPATIAL_FILTER"
            ) from exc
        if (
            profile
            and target_srid in (4326, 4756)
            and any(not profile.geographic_bounds.contains(x, y) for x, y in positions)
        ):
            raise PlatformValidationError(
                "geometry outside transformation area", code="UNSUPPORTED_CRS"
            )
        return checked, profile.operation_id if profile else None

    def _spatial_clause(
        self,
        source: DataSource,
        spatial_filter: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any], str, dict[str, Any] | None, str | None]:
        if spatial_filter is None:
            return "TRUE", {}, "", None, None
        if not isinstance(spatial_filter.get("predicate"), str):
            raise PlatformValidationError(
                "invalid spatial predicate", code="INVALID_SPATIAL_FILTER"
            )
        try:
            pred = SpatialPredicate(spatial_filter["predicate"])
        except ValueError as exc:
            raise PlatformValidationError(
                "unsupported spatial predicate", code="INVALID_SPATIAL_FILTER"
            ) from exc
        fn = {
            SpatialPredicate.INTERSECTS: "ST_Intersects",
            SpatialPredicate.WITHIN: "ST_Within",
            SpatialPredicate.CONTAINS: "ST_Contains",
        }[pred]
        assert source.stored_crs is not None
        reference_pin = None
        operation = None
        geometries: list[NativeGeometry] = []
        if set(spatial_filter) == {"predicate", "geometry", "crs_code"}:
            area = parse_drawn_area(spatial_filter["geometry"], spatial_filter["crs_code"])
            checked, operation = self._checked_geometry(area, source.stored_crs)
            geometries.append(checked)
        elif {"predicate", "reference_layer_id"} <= set(spatial_filter) and set(spatial_filter) <= {
            "predicate",
            "reference_layer_id",
            "reference_feature_id",
        }:
            try:
                ref_layer = UUID(spatial_filter["reference_layer_id"])
            except (TypeError, ValueError, AttributeError) as exc:
                raise PlatformValidationError(
                    "invalid reference layer identifier", code="INVALID_SPATIAL_FILTER"
                ) from exc
            ref_source, ref_fields = self._resolve_layer_source(
                source.organization_id, source.project_id, ref_layer
            )
            reference_pin = self._pin(ref_source, ref_layer)
            ref_fid = spatial_filter.get("reference_feature_id")
            if ref_fid is not None and (
                not isinstance(ref_fid, str) or not 1 <= len(ref_fid) <= 128
            ):
                raise PlatformValidationError(
                    "invalid reference feature identifier", code="INVALID_SPATIAL_FILTER"
                )
            self._validate_snapshot(ref_source, ref_fields)
            if ref_fid is None and (
                ref_source.feature_count is None
                or ref_source.feature_count > MAX_REFERENCE_FEATURES
            ):
                raise PlatformValidationError(
                    "reference set exceeds feature limit", code="QUERY_TOO_COMPLEX"
                )
            params = self._source_params(ref_source) | {"fid": ref_fid}
            rows = (
                self._session.execute(
                    text("""
                WITH refs AS MATERIALIZED (
                    SELECT geometry, feature_id FROM spatial.reference_features
                    WHERE organization_id=:org AND project_id=:proj AND source_id=:src
                      AND content_revision=:crev AND schema_revision=:srev
                      AND (CAST(:fid AS text) IS NULL OR feature_id=:fid)
                    ORDER BY feature_id LIMIT 501
                )
                SELECT SUM(ST_NPoints(geometry)) OVER () AS positions,
                    COUNT(*) OVER () AS cnt,
                    CASE WHEN SUM(ST_NPoints(geometry)) OVER ()<=100000
                      AND COUNT(*) OVER ()<=500
                      THEN ST_AsBinary(geometry,'NDR') ELSE NULL END AS wkb
                FROM refs
            """),
                    params,
                )
                .mappings()
                .all()
            )
            if ref_fid is not None and not rows:
                raise PlatformNotFoundError("reference feature not found")
            assert ref_source.stored_crs is not None
            for row in rows:
                if (
                    row["cnt"] > MAX_REFERENCE_FEATURES
                    or row["positions"] > MAX_REFERENCE_POSITIONS
                ):
                    raise PlatformValidationError(
                        "reference set exceeds position limit", code="QUERY_TOO_COMPLEX"
                    )
                try:
                    native = _read_native_wkb(bytes(row["wkb"]), ref_source.stored_crs)
                    validate_ready_geometry(
                        native, ref_source.geometry_family, ref_source.stored_crs
                    )
                except SpatialValidationError as exc:
                    raise PlatformValidationError(
                        "invalid reference geometry", code="INVALID_SPATIAL_FILTER"
                    ) from exc
                if ref_source.stored_crs == source.stored_crs:
                    geometries.append(native)
                else:
                    checked, operation = self._checked_geometry(native, source.stored_crs)
                    geometries.append(checked)
        else:
            raise PlatformValidationError(
                "provide exactly one spatial input with explicit CRS if drawn",
                code="INVALID_SPATIAL_FILTER",
            )
        cte = """
            WITH ref_geometries AS MATERIALIZED (
                SELECT ST_GeomFromText(wkt,:ref_srid) AS geometry
                FROM jsonb_array_elements_text(CAST(:ref_wkts AS jsonb)) AS r(wkt)
            )
        """
        clause = f"EXISTS (SELECT 1 FROM ref_geometries rg WHERE {fn}(rf.geometry,rg.geometry))"
        return (
            clause,
            {
                "ref_srid": source.stored_crs,
                "ref_wkts": json.dumps([g.to_wkt() for g in geometries]),
            },
            cte,
            reference_pin,
            operation,
        )

    def execute_query(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        attribute_filter: dict[str, Any] | None = None,
        spatial_filter: dict[str, Any] | None = None,
        expected_content_revision: str | None = None,
        expected_schema_revision: str | None = None,
        expected_query_fingerprint: str | None = None,
        sort_field: str | None = None,
        sort_direction: str = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        self._prepare(context, permission=Permission.PROJECT_READ)
        try:
            return self._execute_query(
                context=context,
                layer_id=layer_id,
                attribute_filter=attribute_filter,
                spatial_filter=spatial_filter,
                expected_content_revision=expected_content_revision,
                expected_schema_revision=expected_schema_revision,
                expected_query_fingerprint=expected_query_fingerprint,
                sort_field=sort_field,
                sort_direction=sort_direction,
                limit=limit,
                offset=offset,
            )
        except SpatialValidationError as exc:
            raise PlatformValidationError(
                "invalid query snapshot or revision", code="INVALID_QUERY_SOURCE"
            ) from exc
        except SQLAlchemyError as exc:
            code = (
                "QUERY_TIMEOUT"
                if getattr(getattr(exc, "orig", None), "sqlstate", None) == "57014"
                else "QUERY_UNAVAILABLE"
            )
            raise PlatformDomainError(
                "query could not be completed safely; narrow or retry", code=code, status_code=503
            ) from exc

    def _set_timeout(self) -> None:
        self._session.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": QUERY_STATEMENT_TIMEOUT},
        )

    def _execute_query(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        attribute_filter: dict[str, Any] | None,
        spatial_filter: dict[str, Any] | None,
        expected_content_revision: str | None,
        expected_schema_revision: str | None,
        expected_query_fingerprint: str | None,
        sort_field: str | None,
        sort_direction: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        assert context.organization_id is not None and context.project_id is not None
        if type(limit) is not int or not 1 <= limit <= MAX_QUERY_LIMIT:
            raise PlatformValidationError("invalid query page size", code="INVALID_LIMIT")
        if type(offset) is not int or not 0 <= offset <= MAX_QUERY_OFFSET:
            raise PlatformValidationError("invalid query offset", code="INVALID_OFFSET")
        if offset and expected_query_fingerprint is None:
            raise PlatformConflictError(
                "page requires previous query fingerprint; restart at offset 0",
                code="MISSING_QUERY_PIN",
            )
        for value in (
            expected_content_revision,
            expected_schema_revision,
            expected_query_fingerprint,
        ):
            if value is not None:
                try:
                    validate_revision_token(value)
                except SpatialValidationError as exc:
                    raise PlatformValidationError(
                        "invalid query revision token", code="INVALID_QUERY_PIN"
                    ) from exc
        self._set_timeout()
        source, fields = self._resolve_layer_source(
            context.organization_id, context.project_id, layer_id
        )
        if (
            expected_content_revision is not None
            and source.content_revision != expected_content_revision
        ):
            raise PlatformConflictError(
                "layer content changed; rerun query", code="STALE_CONTENT_REVISION"
            )
        if (
            expected_schema_revision is not None
            and source.schema_revision != expected_schema_revision
        ):
            raise PlatformConflictError(
                "layer schema changed; rerun query", code="STALE_SCHEMA_REVISION"
            )
        compiled = compile_attribute_filter(attribute_filter, fields)
        order = compile_sort(fields, sort_field, sort_direction)
        self._validate_snapshot(source, fields)
        spatial, spat_params, cte, reference_pin, operation = self._spatial_clause(
            source, spatial_filter
        )
        fingerprint = canonical_manifest_digest(
            {
                "version": "r007-query-v1",
                "scope": [
                    str(context.organization_id),
                    str(context.project_id),
                    str(context.actor.actor_id),
                    str(context.credential_id),
                ],
                "target": self._pin(source, layer_id),
                "reference": reference_pin,
                "attribute_filter": attribute_filter,
                "spatial_filter": spatial_filter,
                "sort_field": sort_field,
                "sort_direction": sort_direction,
                "transformation": operation,
            }
        )
        if expected_query_fingerprint is not None and expected_query_fingerprint != fingerprint:
            raise PlatformConflictError(
                "query or input revision changed; rerun from offset 0", code="STALE_QUERY_PIN"
            )
        params = (
            self._source_params(source)
            | compiled.params
            | spat_params
            | {
                "lim": limit,
                "off": offset,
                "max_page_positions": MAX_PAGE_POSITIONS,
            }
        )
        where = (
            "rf.organization_id=:org AND rf.project_id=:proj AND rf.source_id=:src "
            "AND rf.content_revision=:crev AND rf.schema_revision=:srev "
            f"AND ({compiled.sql}) AND ({spatial})"
        )
        total = int(
            self._session.execute(
                text(f"{cte} SELECT COUNT(*) FROM spatial.reference_features rf WHERE {where}"),
                params,
            ).scalar_one()
        )
        if total > MAX_QUERY_FEATURES:
            raise PlatformValidationError(
                "query result exceeds feature limit", code="QUERY_TOO_COMPLEX"
            )
        prefix = f"{cte}, " if cte else "WITH "
        rows = (
            self._session.execute(
                text(f"""
            {prefix} page AS MATERIALIZED (
                SELECT rf.feature_id, rf.attributes, rf.geometry,
                    ROW_NUMBER() OVER (ORDER BY {order}) AS ordinal
                FROM spatial.reference_features rf
                WHERE {where}
                ORDER BY {order} LIMIT :lim OFFSET :off
            )
            SELECT feature_id, attributes, SUM(ST_NPoints(geometry)) OVER () AS page_positions,
                CASE WHEN SUM(ST_NPoints(geometry)) OVER ()<=:max_page_positions
                    THEN ST_AsBinary(geometry,'NDR') ELSE NULL END AS wkb
            FROM page ORDER BY ordinal
        """),
                params,
            )
            .mappings()
            .all()
        )
        items = []
        assert source.stored_crs is not None
        for row in rows:
            if row["page_positions"] > MAX_PAGE_POSITIONS:
                raise PlatformValidationError(
                    "page geometry exceeds position limit; reduce page size",
                    code="QUERY_TOO_COMPLEX",
                )
            geometry = _read_native_wkb(bytes(row["wkb"]), source.stored_crs)
            validate_ready_geometry(geometry, source.geometry_family, source.stored_crs)
            attributes = dict(row["attributes"])
            if set(attributes) != {field.field_id for field in fields}:
                raise SpatialValidationError("query row schema mismatch")
            for field in fields:
                value = attributes[field.field_id]
                canonical = canonical_attribute_value(field, value)
                if type(value) is not type(canonical) or value != canonical:
                    raise SpatialValidationError("noncanonical query row value")
            items.append(
                {
                    "feature_id": str(row["feature_id"]),
                    "attributes": attributes,
                    "geometry": {"type": geometry.type, "coordinates": geometry.coordinates},
                }
            )
        return {
            **self._pin(source, layer_id),
            "reference_pin": reference_pin,
            "query_fingerprint": fingerprint,
            "geometry_transformation": operation,
            "total_count": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
            "selection_feature_ids": [item["feature_id"] for item in items],
            "items": items,
        }

    def create_saved_query(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        name: str,
        description: str = "",
        attribute_filter: dict[str, Any] | None = None,
        spatial_filter: dict[str, Any] | None = None,
        sort_field: str | None = None,
        sort_direction: str = "asc",
    ) -> SavedQueryRecord:
        self._prepare(context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 200:
            raise PlatformValidationError("name must be 1..200 characters", code="INVALID_NAME")
        self._set_timeout()
        try:
            source, fields = self._resolve_layer_source(
                context.organization_id, context.project_id, layer_id
            )
            compile_attribute_filter(attribute_filter, fields)
            compile_sort(fields, sort_field, sort_direction)
            self._spatial_clause(source, spatial_filter)
        except SQLAlchemyError as exc:
            raise PlatformDomainError(
                "saved definition could not be validated", code="QUERY_UNAVAILABLE", status_code=503
            ) from exc
        except SpatialValidationError as exc:
            raise PlatformValidationError(
                "invalid saved definition", code="INVALID_QUERY_SOURCE"
            ) from exc
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO queries.saved_queries (
                    id, organization_id, project_id, layer_id, name, description,
                    attribute_filter, spatial_filter, sort_field, sort_direction,
                    created_by_actor_id, created_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :lid, :name, :desc,
                    CAST(:af AS jsonb), CAST(:sf AS jsonb), :sfield, :sdir,
                    :actor, :now, :now
                )
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "lid": layer_id,
                    "name": clean_name,
                    "desc": description.strip()[:500],
                    "af": json.dumps(attribute_filter) if attribute_filter is not None else None,
                    "sf": json.dumps(spatial_filter) if spatial_filter is not None else None,
                    "sfield": sort_field,
                    "sdir": sort_direction,
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._session.commit()
        return _saved_query_from_row(row)

    def list_saved_queries(
        self, *, context: AuthorizationContext, layer_id: UUID | None = None
    ) -> list[SavedQueryRecord]:
        self._prepare(context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        sql = """
            SELECT * FROM queries.saved_queries
            WHERE organization_id = :org AND project_id = :proj
        """
        params: dict[str, Any] = {"org": context.organization_id, "proj": context.project_id}
        if layer_id is not None:
            sql += " AND layer_id = :lid"
            params["lid"] = layer_id
        sql += " ORDER BY created_at DESC, id ASC LIMIT 501"
        rows = self._session.execute(text(sql), params).mappings().all()
        if len(rows) > 500:
            raise PlatformValidationError(
                "saved definition list exceeds limit", code="QUERY_TOO_COMPLEX"
            )
        return [_saved_query_from_row(r) for r in rows]

    def delete_saved_query(self, *, context: AuthorizationContext, query_id: UUID) -> None:
        self._prepare(context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        deleted = self._session.execute(
            text("""
                DELETE FROM queries.saved_queries
                WHERE organization_id = :org AND project_id = :proj AND id = :qid
                RETURNING id
            """),
            {"org": context.organization_id, "proj": context.project_id, "qid": query_id},
        ).first()
        if deleted is None:
            raise PlatformNotFoundError("saved query not found")
        self._session.commit()
