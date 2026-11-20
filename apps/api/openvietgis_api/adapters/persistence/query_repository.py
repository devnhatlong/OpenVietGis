"""R007 RLS-enforced PostGIS repository for typed attribute & bounded spatial queries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.adapters.persistence.spatial_repository import (
    SqlSpatialRepository,
    _source_from_row,
)
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.domains.queries.domain import (
    MAX_QUERY_LIMIT,
    SavedQueryRecord,
    SpatialPredicate,
    compile_attribute_filter,
)
from openvietgis_api.domains.spatial.domain import (
    FieldType,
    Lifecycle,
    SourceField,
    ValidationState,
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
        self._spatial = SqlSpatialRepository(session)

    def _prepare(self, context: AuthorizationContext, *, permission: Permission) -> None:
        prepare_project_scope(self._session, context, permission=permission)

    def _resolve_layer_source(
        self, org_id: UUID, project_id: UUID, layer_id: UUID
    ) -> tuple[Any, list[SourceField]]:
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
        return source, fields

    def execute_query(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        attribute_filter: dict[str, Any] | None = None,
        spatial_filter: dict[str, Any] | None = None,
        expected_content_revision: str | None = None,
        sort_field: str | None = None,
        sort_direction: str = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        self._prepare(context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        org_id, project_id = context.organization_id, context.project_id
        source, fields = self._resolve_layer_source(org_id, project_id, layer_id)

        if expected_content_revision and source.content_revision != expected_content_revision:
            raise PlatformConflictError(
                "layer content_revision changed during pagination",
                code="STALE_CONTENT_REVISION",
                details={"current_content_revision": source.content_revision},
            )

        if limit < 1 or limit > MAX_QUERY_LIMIT:
            raise PlatformValidationError(
                f"limit must be between 1 and {MAX_QUERY_LIMIT}", code="INVALID_LIMIT"
            )
        if offset < 0:
            raise PlatformValidationError("offset must be >= 0", code="INVALID_OFFSET")

        compiled = compile_attribute_filter(attribute_filter, fields)
        params: dict[str, Any] = {
            "org": org_id,
            "proj": project_id,
            "src": source.id,
            "lim": limit,
            "off": offset,
            **compiled.params,
        }

        where_clauses = [
            "rf.organization_id = :org",
            "rf.project_id = :proj",
            "rf.source_id = :src",
            compiled.sql,
        ]

        if spatial_filter:
            pred_raw = str(spatial_filter.get("predicate") or "").lower()
            try:
                pred = SpatialPredicate(pred_raw)
            except ValueError as exc:
                raise PlatformValidationError(
                    f"unsupported spatial predicate {pred_raw!r}", code="INVALID_SPATIAL_FILTER"
                ) from exc
            fn = {
                SpatialPredicate.INTERSECTS: "ST_Intersects",
                SpatialPredicate.WITHIN: "ST_Within",
                SpatialPredicate.CONTAINS: "ST_Contains",
            }[pred]

            if "geometry" in spatial_filter and spatial_filter["geometry"] is not None:
                geom_srid = int(spatial_filter.get("crs_code") or source.stored_crs or 4326)
                if geom_srid not in (4326, 3857, 4756, 5899):
                    raise PlatformValidationError(
                        f"unsupported filter CRS {geom_srid}", code="UNSUPPORTED_CRS"
                    )
                params["sp_geojson"] = json.dumps(spatial_filter["geometry"])
                params["sp_srid"] = geom_srid
                params["src_srid"] = source.stored_crs
                if geom_srid == source.stored_crs:
                    geom_expr = "ST_SetSRID(ST_GeomFromGeoJSON(:sp_geojson), :sp_srid)"
                else:
                    geom_expr = (
                        "ST_Transform("
                        "ST_SetSRID(ST_GeomFromGeoJSON(:sp_geojson), :sp_srid), :src_srid)"
                    )
                where_clauses.append(f"{fn}(rf.geometry, {geom_expr})")
            elif "reference_layer_id" in spatial_filter:
                ref_layer_id = UUID(str(spatial_filter["reference_layer_id"]))
                ref_source, _ = self._resolve_layer_source(org_id, project_id, ref_layer_id)
                params["ref_src"] = ref_source.id
                ref_fid = spatial_filter.get("reference_feature_id")
                if ref_fid:
                    params["ref_fid"] = str(ref_fid)
                    ref_sub = (
                        "SELECT geometry FROM spatial.reference_features "
                        "WHERE organization_id = :org AND project_id = :proj "
                        "AND source_id = :ref_src AND feature_id = :ref_fid"
                    )
                else:
                    ref_sub = (
                        "SELECT geometry FROM spatial.reference_features "
                        "WHERE organization_id = :org AND project_id = :proj "
                        "AND source_id = :ref_src LIMIT 500"
                    )
                where_clauses.append(
                    f"EXISTS (SELECT 1 FROM ({ref_sub}) AS ref_g "
                    f"WHERE {fn}(rf.geometry, ref_g.geometry))"
                )
            else:
                raise PlatformValidationError(
                    "spatial_filter requires 'geometry' or 'reference_layer_id'",
                    code="INVALID_SPATIAL_FILTER",
                )

        # Deterministic sort
        field_map = {f.field_id: f for f in fields}
        direction = "DESC" if str(sort_direction).lower() == "desc" else "ASC"
        if sort_field:
            if sort_field not in field_map:
                raise PlatformValidationError(
                    f"unknown sort field {sort_field!r}", code="UNKNOWN_SORT_FIELD"
                )
            fobj = field_map[sort_field]
            if fobj.type == FieldType.INTEGER:
                cast_col = f"(rf.attributes ->> '{fobj.field_id}')::bigint"
            elif fobj.type == FieldType.DECIMAL:
                cast_col = f"(rf.attributes ->> '{fobj.field_id}')::double precision"
            else:
                cast_col = f"(rf.attributes ->> '{fobj.field_id}')"
            order_expr = f"{cast_col} {direction} NULLS LAST, rf.feature_id ASC"
        else:
            order_expr = f"rf.feature_id {direction}"

        where_sql = " AND ".join(where_clauses)
        total = int(
            self._session.execute(
                text(f"SELECT COUNT(*)::int FROM spatial.reference_features rf WHERE {where_sql}"),
                params,
            ).scalar_one()
        )
        rows = (
            self._session.execute(
                text(f"""
                SELECT rf.feature_id, rf.attributes,
                       ST_AsGeoJSON(rf.geometry)::jsonb AS geometry
                FROM spatial.reference_features rf
                WHERE {where_sql}
                ORDER BY {order_expr}
                LIMIT :lim OFFSET :off
            """),
                params,
            )
            .mappings()
            .all()
        )

        items = [
            {
                "feature_id": str(r["feature_id"]),
                "attributes": dict(r["attributes"]),
                "geometry": dict(r["geometry"]) if r["geometry"] is not None else None,
            }
            for r in rows
        ]
        return {
            "layer_id": str(layer_id),
            "source_id": str(source.id),
            "content_revision": source.content_revision,
            "stored_crs": source.stored_crs,
            "total_count": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
            "selection_feature_ids": [i["feature_id"] for i in items],
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
        _, fields = self._resolve_layer_source(
            context.organization_id, context.project_id, layer_id
        )
        compile_attribute_filter(attribute_filter, fields)
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
                    "sdir": "desc" if str(sort_direction).lower() == "desc" else "asc",
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
        sql += " ORDER BY created_at DESC"
        rows = self._session.execute(text(sql), params).mappings().all()
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
