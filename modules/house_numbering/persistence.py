"""Typed RLS persistence for the House Numbering official module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.module_sdk import (
    AuthorizationContext,
    append_project_audit,
    prepare_module_scope,
    set_extension_private_access,
)
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session


class HouseNumberingRepository:
    def __init__(self, session: Session, context: AuthorizationContext) -> None:
        self.session = session
        self.context = context

    @property
    def org_id(self) -> UUID:
        assert self.context.organization_id is not None
        return self.context.organization_id

    @property
    def project_id(self) -> UUID:
        assert self.context.project_id is not None
        return self.context.project_id

    @property
    def actor_id(self) -> UUID:
        assert self.context.actor.actor_id is not None
        return self.context.actor.actor_id

    def prepare(self, access: str = "read") -> None:
        if access not in {"read", "edit", "manage"}:
            raise ValueError("invalid module access level")
        prepare_module_scope(self.session, self.context, access=access)  # type: ignore[arg-type]
        active = self.session.execute(
            text("""
                SELECT 1 FROM extensions.project_activations
                WHERE organization_id=:org AND project_id=:project
                  AND extension_key='house_numbering' AND status='active'
            """),
            {"org": self.org_id, "project": self.project_id},
        ).first()
        if active is None:
            raise PlatformNotFoundError(
                "house_numbering module is not active in this project"
            )

    def audit(
        self,
        action: str,
        resource_type: str,
        resource_id: UUID,
        metadata: dict[str, Any],
    ) -> None:
        append_project_audit(
            self.session,
            self.context,
            audit_id=uuid4(),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            created_at=datetime.now(UTC),
        )

    def spatial_feature(
        self, source_id: UUID, feature_id: str, *, expected: set[str]
    ) -> dict[str, Any]:
        row = (
            self.session.execute(
                text("""
                SELECT ds.stored_crs, ds.lifecycle, ds.validation_state,
                       ST_SRID(rf.geometry) AS srid,
                       ST_GeometryType(rf.geometry) AS geometry_type,
                       ST_AsGeoJSON(rf.geometry)::jsonb AS geometry
                FROM spatial.data_sources ds
                JOIN spatial.reference_features rf
                  ON rf.organization_id=ds.organization_id
                 AND rf.project_id=ds.project_id
                 AND rf.source_id=ds.id
                WHERE ds.organization_id=:org AND ds.project_id=:project
                  AND ds.id=:source AND rf.feature_id=:feature
                  AND rf.geometry_state='present'
            """),
                {
                    "org": self.org_id,
                    "project": self.project_id,
                    "source": source_id,
                    "feature": feature_id,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError(
                "linked spatial feature not found or not usable"
            )
        if row["lifecycle"] != "active" or row["validation_state"] != "ready":
            raise PlatformValidationError(
                "linked spatial source is not ready", code="SOURCE_NOT_READY"
            )
        if str(row["geometry_type"]) not in expected:
            raise PlatformValidationError(
                f"linked feature geometry {row['geometry_type']!r} is not valid for this entity",
                code="GEOMETRY_TYPE_MISMATCH",
            )
        srid = int(row["srid"] or row["stored_crs"] or 0)
        if srid <= 0:
            raise PlatformValidationError(
                "linked geometry has no explicit CRS", code="MISSING_CRS"
            )
        return {
            "srid": srid,
            "geometry_type": str(row["geometry_type"]),
            "geometry": dict(row["geometry"]),
        }

    def create_rule(
        self,
        *,
        version: str,
        status: str,
        authority_ref: str | None,
        left_odd: bool,
        suffix_style: str,
        max_distance_m: float,
    ) -> RowMapping:
        self.prepare("manage")
        now = datetime.now(UTC)
        row = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.rules (
                    id, organization_id, project_id, version, status, authority_ref,
                    left_odd, suffix_style, max_distance_m, sealed, revision,
                    created_by_actor_id, updated_by_actor_id, created_at, updated_at
                ) VALUES (
                    :id,:org,:project,:version,:status,:authority,
                    :left_odd,:suffix,:distance,true,1,:actor,:actor,:now,:now
                ) RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": self.org_id,
                    "project": self.project_id,
                    "version": version,
                    "status": status,
                    "authority": authority_ref,
                    "left_odd": left_odd,
                    "suffix": suffix_style,
                    "distance": max_distance_m,
                    "actor": self.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self.audit(
            "house_numbering.rule.create",
            "house_numbering_rule",
            row["id"],
            {"version": version},
        )
        return row

    def list_rules(self) -> list[RowMapping]:
        self.prepare("read")
        return (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.rules
                WHERE organization_id=:org AND project_id=:project
                ORDER BY created_at DESC
            """),
                {"org": self.org_id, "project": self.project_id},
            )
            .mappings()
            .all()
        )

    def get_rule(self, rule_id: UUID) -> RowMapping:
        self.prepare("read")
        row = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.rules
                WHERE organization_id=:org AND project_id=:project AND id=:id
            """),
                {"org": self.org_id, "project": self.project_id, "id": rule_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("numbering rule not found")
        return row

    def create_area(
        self,
        *,
        name: str,
        kind: str,
        parent_id: UUID | None,
        source_id: UUID | None,
        feature_id: str | None,
    ) -> RowMapping:
        self.prepare("edit")
        if (source_id is None) != (feature_id is None):
            raise PlatformValidationError(
                "area spatial source and feature must be supplied together"
            )
        if source_id is not None and feature_id is not None:
            self.spatial_feature(source_id, feature_id, expected={"ST_Polygon"})
        now = datetime.now(UTC)
        row = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.areas (
                    id,organization_id,project_id,name,kind,parent_id,
                    linked_source_id,linked_feature_id,revision,
                    created_by_actor_id,updated_by_actor_id,created_at,updated_at
                ) VALUES (
                    :id,:org,:project,:name,:kind,:parent,:source,:feature,1,
                    :actor,:actor,:now,:now
                ) RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": self.org_id,
                    "project": self.project_id,
                    "name": name.strip(),
                    "kind": kind,
                    "parent": parent_id,
                    "source": source_id,
                    "feature": feature_id,
                    "actor": self.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self.audit(
            "house_numbering.area.create",
            "house_numbering_area",
            row["id"],
            {"name": row["name"]},
        )
        return row

    def list_areas(self) -> list[RowMapping]:
        self.prepare("read")
        return (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.areas
                WHERE organization_id=:org AND project_id=:project
                ORDER BY name,id
            """),
                {"org": self.org_id, "project": self.project_id},
            )
            .mappings()
            .all()
        )

    def create_route(
        self,
        *,
        name: str,
        route_type: str,
        parent_route_id: UUID | None,
        prefix: str | None,
        source_id: UUID,
        feature_id: str,
        direction_state: str,
        source_label: str,
        status: str,
    ) -> RowMapping:
        self.prepare("edit")
        self.spatial_feature(source_id, feature_id, expected={"ST_LineString"})
        now = datetime.now(UTC)
        row = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.routes (
                    id,organization_id,project_id,name,route_type,parent_route_id,prefix,
                    linked_source_id,linked_feature_id,direction_state,source_label,status,revision,
                    created_by_actor_id,updated_by_actor_id,created_at,updated_at
                ) VALUES (
                    :id,:org,:project,:name,:rtype,:parent,:prefix,:source,:feature,
                    :direction,:source_label,:status,1,:actor,:actor,:now,:now
                ) RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": self.org_id,
                    "project": self.project_id,
                    "name": name.strip(),
                    "rtype": route_type,
                    "parent": parent_route_id,
                    "prefix": prefix,
                    "source": source_id,
                    "feature": feature_id,
                    "direction": direction_state,
                    "source_label": source_label.strip(),
                    "status": status,
                    "actor": self.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self.audit(
            "house_numbering.route.create",
            "house_numbering_route",
            row["id"],
            {"name": row["name"]},
        )
        return row

    def list_routes(self) -> list[RowMapping]:
        self.prepare("read")
        return (
            self.session.execute(
                text("""
                SELECT r.*,
                       (SELECT count(*) FROM house_numbering.buildings b
                        WHERE b.organization_id=r.organization_id AND b.project_id=r.project_id
                          AND b.route_id=r.id AND b.state='active') AS building_count
                FROM house_numbering.routes r
                WHERE r.organization_id=:org AND r.project_id=:project
                ORDER BY r.route_type,r.name,r.id
            """),
                {"org": self.org_id, "project": self.project_id},
            )
            .mappings()
            .all()
        )

    def get_route(self, route_id: UUID, *, for_update: bool = False) -> RowMapping:
        self.prepare("edit" if for_update else "read")
        lock = " FOR UPDATE" if for_update else ""
        row = (
            self.session.execute(
                text(
                    """
                SELECT * FROM house_numbering.routes
                WHERE organization_id=:org AND project_id=:project AND id=:id
            """
                    + lock
                ),
                {"org": self.org_id, "project": self.project_id, "id": route_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("route not found")
        return row

    def update_route(
        self,
        route_id: UUID,
        *,
        expected_revision: int,
        name: str,
        direction_state: str,
        status: str,
    ) -> RowMapping:
        current = self.get_route(route_id, for_update=True)
        if int(current["revision"]) != expected_revision:
            raise PlatformConflictError("route revision is stale", code="STALE_ROUTE")
        if direction_state != current["direction_state"]:
            locked = self.session.execute(
                text("""
                    SELECT 1 FROM house_numbering.address_numbers
                    WHERE organization_id=:org AND project_id=:project AND route_id=:route
                      AND retired_at IS NULL AND kind IN ('submitted','approved') LIMIT 1
                """),
                {"org": self.org_id, "project": self.project_id, "route": route_id},
            ).first()
            if locked is not None:
                raise PlatformConflictError(
                    "route direction is locked by submitted or approved numbers",
                    code="ROUTE_DIRECTION_LOCKED",
                )
        row = (
            self.session.execute(
                text("""
                UPDATE house_numbering.routes
                SET name=:name,direction_state=:direction,status=:status,
                    revision=revision+1,updated_by_actor_id=:actor,updated_at=:now
                WHERE organization_id=:org AND project_id=:project AND id=:id
                RETURNING *
            """),
                {
                    "name": name.strip(),
                    "direction": direction_state,
                    "status": status,
                    "actor": self.actor_id,
                    "now": datetime.now(UTC),
                    "org": self.org_id,
                    "project": self.project_id,
                    "id": route_id,
                },
            )
            .mappings()
            .one()
        )
        self.audit(
            "house_numbering.route.update",
            "house_numbering_route",
            route_id,
            {"revision": row["revision"]},
        )
        return row

    def delete_route(self, route_id: UUID) -> None:
        self.prepare("edit")
        dependency = (
            self.session.execute(
                text("""
                SELECT 'child_route' AS kind FROM house_numbering.routes
                 WHERE organization_id=:org AND project_id=:project AND parent_route_id=:route LIMIT 1
                UNION ALL
                SELECT 'building' AS kind FROM house_numbering.buildings
                 WHERE organization_id=:org AND project_id=:project AND route_id=:route LIMIT 1
                UNION ALL
                SELECT 'number' AS kind FROM house_numbering.address_numbers
                 WHERE organization_id=:org AND project_id=:project AND route_id=:route LIMIT 1
                LIMIT 1
            """),
                {"org": self.org_id, "project": self.project_id, "route": route_id},
            )
            .mappings()
            .first()
        )
        if dependency is not None:
            raise PlatformConflictError(
                f"route has dependent {dependency['kind']}",
                code="ROUTE_HAS_DEPENDENCIES",
            )
        deleted = self.session.execute(
            text("""
                DELETE FROM house_numbering.routes
                WHERE organization_id=:org AND project_id=:project AND id=:id
                RETURNING id
            """),
            {"org": self.org_id, "project": self.project_id, "id": route_id},
        ).scalar_one_or_none()
        if deleted is None:
            raise PlatformNotFoundError("route not found")
        self.audit(
            "house_numbering.route.delete", "house_numbering_route", route_id, {}
        )

    def create_building(
        self,
        *,
        route_id: UUID | None,
        area_id: UUID | None,
        parcel_ref: str | None,
        source_id: UUID,
        feature_id: str,
        eligibility: str,
        ineligibility_reason: str | None,
    ) -> RowMapping:
        self.prepare("edit")
        self.spatial_feature(source_id, feature_id, expected={"ST_Point", "ST_Polygon"})
        now = datetime.now(UTC)
        row = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.buildings (
                    id,organization_id,project_id,route_id,area_id,parcel_ref,
                    linked_source_id,linked_feature_id,eligibility,ineligibility_reason,
                    state,revision,created_by_actor_id,updated_by_actor_id,created_at,updated_at
                ) VALUES (
                    :id,:org,:project,:route,:area,:parcel,:source,:feature,:eligibility,:reason,
                    'active',1,:actor,:actor,:now,:now
                ) RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": self.org_id,
                    "project": self.project_id,
                    "route": route_id,
                    "area": area_id,
                    "parcel": parcel_ref,
                    "source": source_id,
                    "feature": feature_id,
                    "eligibility": eligibility,
                    "reason": ineligibility_reason,
                    "actor": self.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self.audit(
            "house_numbering.building.create", "house_numbering_building", row["id"], {}
        )
        return row

    def list_buildings(self, *, route_id: UUID | None = None) -> list[RowMapping]:
        self.prepare("read")
        sql = """
            SELECT b.*,
                   n.number_text AS current_number,n.kind AS number_kind,n.id AS number_id
            FROM house_numbering.buildings b
            LEFT JOIN LATERAL (
                SELECT id,number_text,kind FROM house_numbering.address_numbers n
                WHERE n.organization_id=b.organization_id AND n.project_id=b.project_id
                  AND n.building_id=b.id AND n.retired_at IS NULL
                ORDER BY CASE n.kind
                    WHEN 'approved' THEN 1 WHEN 'submitted' THEN 2 WHEN 'proposed' THEN 3
                    WHEN 'certificate' THEN 4 WHEN 'survey' THEN 5 WHEN 'cad' THEN 6 ELSE 7 END,
                    n.created_at DESC LIMIT 1
            ) n ON true
            WHERE b.organization_id=:org AND b.project_id=:project AND b.state='active'
        """
        params: dict[str, Any] = {"org": self.org_id, "project": self.project_id}
        if route_id is not None:
            sql += " AND b.route_id=:route"
            params["route"] = route_id
        sql += " ORDER BY b.created_at,b.id"
        return self.session.execute(text(sql), params).mappings().all()

    def get_building(
        self, building_id: UUID, *, for_update: bool = False
    ) -> RowMapping:
        self.prepare("edit" if for_update else "read")
        lock = " FOR UPDATE" if for_update else ""
        row = (
            self.session.execute(
                text(
                    """
                SELECT * FROM house_numbering.buildings
                WHERE organization_id=:org AND project_id=:project AND id=:id
            """
                    + lock
                ),
                {"org": self.org_id, "project": self.project_id, "id": building_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("building not found")
        return row

    def set_building_eligibility(
        self,
        building_id: UUID,
        *,
        expected_revision: int,
        eligibility: str,
        reason: str | None,
    ) -> RowMapping:
        current = self.get_building(building_id, for_update=True)
        if int(current["revision"]) != expected_revision:
            raise PlatformConflictError(
                "building revision is stale", code="STALE_BUILDING"
            )
        row = (
            self.session.execute(
                text("""
                UPDATE house_numbering.buildings
                SET eligibility=:eligibility,ineligibility_reason=:reason,
                    revision=revision+1,updated_by_actor_id=:actor,updated_at=:now
                WHERE organization_id=:org AND project_id=:project AND id=:id
                RETURNING *
            """),
                {
                    "eligibility": eligibility,
                    "reason": reason,
                    "actor": self.actor_id,
                    "now": datetime.now(UTC),
                    "org": self.org_id,
                    "project": self.project_id,
                    "id": building_id,
                },
            )
            .mappings()
            .one()
        )
        self.audit(
            "house_numbering.building.eligibility",
            "house_numbering_building",
            building_id,
            {"eligibility": eligibility},
        )
        return row

    def route_geometry(self, route_id: UUID) -> dict[str, Any]:
        self.prepare("read")
        row = (
            self.session.execute(
                text("""
                SELECT r.id,r.prefix,r.direction_state,r.revision,
                       ST_SRID(f.geometry) AS srid,
                       ST_AsGeoJSON(
                           CASE WHEN r.direction_state='reverse' THEN ST_Reverse(f.geometry) ELSE f.geometry END
                       )::jsonb AS geometry
                FROM house_numbering.routes r
                JOIN spatial.reference_features f
                  ON f.organization_id=r.organization_id AND f.project_id=r.project_id
                 AND f.source_id=r.linked_source_id AND f.feature_id=r.linked_feature_id
                WHERE r.organization_id=:org AND r.project_id=:project AND r.id=:route
                  AND f.geometry_state='present' AND ST_GeometryType(f.geometry)='ST_LineString'
            """),
                {"org": self.org_id, "project": self.project_id, "route": route_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("route geometry not available")
        srid = int(row["srid"] or 0)
        projected = self.session.execute(
            text("""
                SELECT NOT (COALESCE(srtext,'') ILIKE 'GEOGCS%' OR COALESCE(proj4text,'') LIKE '%+proj=longlat%')
                FROM spatial_ref_sys WHERE srid=:srid
            """),
            {"srid": srid},
        ).scalar_one_or_none()
        if projected is not True:
            raise PlatformValidationError(
                "numbering requires a verified projected route CRS",
                code="PROJECTED_CRS_REQUIRED",
            )
        return dict(row)

    def transform_point(
        self, x: float, y: float, source_crs: int, target_crs: int
    ) -> tuple[float, float]:
        row = self.session.execute(
            text("""
                SELECT ST_X(g),ST_Y(g) FROM (
                    SELECT ST_Transform(ST_SetSRID(ST_MakePoint(:x,:y),:source_crs),:target_crs) g
                ) q
            """),
            {"x": x, "y": y, "source_crs": source_crs, "target_crs": target_crs},
        ).one()
        return float(row[0]), float(row[1])

    def building_points_for_route(
        self, route_id: UUID, target_crs: int
    ) -> list[dict[str, Any]]:
        self.prepare("read")
        rows = (
            self.session.execute(
                text("""
                SELECT b.id,b.revision,n.id AS number_id,n.number_text,n.kind,n.side,n.measure_m,
                       ST_X(ST_Transform(ST_PointOnSurface(f.geometry),:target_crs)) AS x,
                       ST_Y(ST_Transform(ST_PointOnSurface(f.geometry),:target_crs)) AS y
                FROM house_numbering.buildings b
                JOIN spatial.reference_features f
                  ON f.organization_id=b.organization_id AND f.project_id=b.project_id
                 AND f.source_id=b.linked_source_id AND f.feature_id=b.linked_feature_id
                LEFT JOIN LATERAL (
                    SELECT * FROM house_numbering.address_numbers n
                    WHERE n.organization_id=b.organization_id AND n.project_id=b.project_id
                      AND n.building_id=b.id AND n.retired_at IS NULL
                    ORDER BY CASE n.kind
                        WHEN 'approved' THEN 1 WHEN 'submitted' THEN 2 WHEN 'reserved' THEN 3
                        WHEN 'proposed' THEN 4 WHEN 'certificate' THEN 5 WHEN 'survey' THEN 6
                        WHEN 'cad' THEN 7 ELSE 8 END, n.created_at DESC LIMIT 1
                ) n ON true
                WHERE b.organization_id=:org AND b.project_id=:project
                  AND b.route_id=:route AND b.state='active' AND f.geometry_state='present'
            """),
                {
                    "org": self.org_id,
                    "project": self.project_id,
                    "route": route_id,
                    "target_crs": target_crs,
                },
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    def list_route_numbers(self, route_id: UUID) -> list[RowMapping]:
        self.prepare("read")
        return (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.address_numbers
                WHERE organization_id=:org AND project_id=:project AND route_id=:route
                  AND retired_at IS NULL
                ORDER BY measure_m NULLS LAST,created_at,id
            """),
                {"org": self.org_id, "project": self.project_id, "route": route_id},
            )
            .mappings()
            .all()
        )

    def create_preview(
        self,
        *,
        operation_id: UUID,
        rule_id: UUID,
        base_revisions: dict[str, int],
        changes: list[dict[str, Any]],
        warnings: list[str],
        expires_at: datetime,
    ) -> RowMapping:
        self.prepare("edit")
        existing = (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.previews
                WHERE organization_id=:org AND project_id=:project AND operation_id=:operation
            """),
                {
                    "org": self.org_id,
                    "project": self.project_id,
                    "operation": operation_id,
                },
            )
            .mappings()
            .first()
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        return (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.previews (
                    id,organization_id,project_id,operation_id,rule_id,base_revisions,
                    candidate_changes,warnings,expires_at,created_by_actor_id,created_at
                ) VALUES (
                    :id,:org,:project,:operation,:rule,CAST(:base AS jsonb),CAST(:changes AS jsonb),
                    CAST(:warnings AS jsonb),:expires,:actor,:now
                ) RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": self.org_id,
                    "project": self.project_id,
                    "operation": operation_id,
                    "rule": rule_id,
                    "base": json.dumps(base_revisions),
                    "changes": json.dumps(changes),
                    "warnings": json.dumps(warnings),
                    "expires": expires_at,
                    "actor": self.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )

    def get_preview(self, preview_id: UUID, *, for_update: bool = False) -> RowMapping:
        self.prepare("edit" if for_update else "read")
        lock = " FOR UPDATE" if for_update else ""
        row = (
            self.session.execute(
                text(
                    """
                SELECT * FROM house_numbering.previews
                WHERE organization_id=:org AND project_id=:project AND id=:id
            """
                    + lock
                ),
                {"org": self.org_id, "project": self.project_id, "id": preview_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("numbering preview not found")
        return row

    def proposed_number_for_building(self, building_id: UUID) -> RowMapping | None:
        self.prepare("read")
        return (
            self.session.execute(
                text("""
                SELECT * FROM house_numbering.address_numbers
                WHERE organization_id=:org AND project_id=:project AND building_id=:building
                  AND retired_at IS NULL AND kind IN ('proposed','submitted','approved')
                ORDER BY CASE kind WHEN 'approved' THEN 1 WHEN 'submitted' THEN 2 ELSE 3 END
                LIMIT 1
            """),
                {
                    "org": self.org_id,
                    "project": self.project_id,
                    "building": building_id,
                },
            )
            .mappings()
            .first()
        )

    def apply_preview(self, preview_id: UUID) -> list[RowMapping]:
        preview = self.get_preview(preview_id, for_update=True)
        if preview["applied_at"] is not None:
            changes = list(preview["candidate_changes"])
            ids = [
                UUID(str(change["result_number_id"]))
                for change in changes
                if change.get("result_number_id")
            ]
            if not ids:
                return []
            return (
                self.session.execute(
                    text("""
                    SELECT * FROM house_numbering.address_numbers
                    WHERE organization_id=:org AND project_id=:project AND id = ANY(:ids)
                    ORDER BY created_at,id
                """),
                    {"org": self.org_id, "project": self.project_id, "ids": ids},
                )
                .mappings()
                .all()
            )
        if preview["expires_at"] <= datetime.now(UTC):
            raise PlatformConflictError(
                "numbering preview expired", code="PREVIEW_EXPIRED"
            )
        base = dict(preview["base_revisions"])
        changes = [dict(item) for item in preview["candidate_changes"]]
        results: list[RowMapping] = []
        for change in changes:
            building_id = UUID(str(change["building_id"]))
            route_id = UUID(str(change["route_id"]))
            building = self.get_building(building_id, for_update=True)
            route = self.get_route(route_id, for_update=True)
            if int(building["revision"]) != int(base[f"building:{building_id}"]) or int(
                route["revision"]
            ) != int(base[f"route:{route_id}"]):
                raise PlatformConflictError(
                    "numbering preview is stale", code="STALE_PREVIEW"
                )
            if building["eligibility"] == "ineligible":
                raise PlatformConflictError(
                    "ineligible building cannot receive a number",
                    code="INELIGIBLE_BUILDING",
                )
            occupied = self.session.execute(
                text("""
                    SELECT 1 FROM house_numbering.address_numbers
                    WHERE organization_id=:org AND project_id=:project AND route_id=:route
                      AND number_text=:number AND retired_at IS NULL
                      AND kind IN ('submitted','approved','reserved') LIMIT 1
                """),
                {
                    "org": self.org_id,
                    "project": self.project_id,
                    "route": route_id,
                    "number": change["number"],
                },
            ).first()
            if occupied is not None:
                raise PlatformConflictError(
                    "number became occupied", code="NUMBER_OCCUPIED"
                )
            now = datetime.now(UTC)
            self.session.execute(
                text("""
                    UPDATE house_numbering.address_numbers SET retired_at=:now,
                        revision=revision+1,updated_by_actor_id=:actor,updated_at=:now
                    WHERE organization_id=:org AND project_id=:project AND building_id=:building
                      AND retired_at IS NULL AND kind='proposed'
                """),
                {
                    "now": now,
                    "actor": self.actor_id,
                    "org": self.org_id,
                    "project": self.project_id,
                    "building": building_id,
                },
            )
            number_id = uuid4()
            row = (
                self.session.execute(
                    text("""
                    INSERT INTO house_numbering.address_numbers (
                        id,organization_id,project_id,building_id,route_id,number_text,kind,
                        side,measure_m,rule_id,revision,created_by_actor_id,updated_by_actor_id,
                        created_at,updated_at
                    ) VALUES (
                        :id,:org,:project,:building,:route,:number,'proposed',:side,:measure,
                        :rule,1,:actor,:actor,:now,:now
                    ) RETURNING *
                """),
                    {
                        "id": number_id,
                        "org": self.org_id,
                        "project": self.project_id,
                        "building": building_id,
                        "route": route_id,
                        "number": change["number"],
                        "side": change["side"],
                        "measure": change["measure"],
                        "rule": preview["rule_id"],
                        "actor": self.actor_id,
                        "now": now,
                    },
                )
                .mappings()
                .one()
            )
            change["result_number_id"] = str(number_id)
            results.append(row)
        self.session.execute(
            text("""
                UPDATE house_numbering.previews
                SET candidate_changes=CAST(:changes AS jsonb),applied_at=:now
                WHERE organization_id=:org AND project_id=:project AND id=:id
            """),
            {
                "changes": json.dumps(changes),
                "now": datetime.now(UTC),
                "org": self.org_id,
                "project": self.project_id,
                "id": preview_id,
            },
        )
        self.audit(
            "house_numbering.preview.apply",
            "house_numbering_preview",
            preview_id,
            {"count": len(results)},
        )
        return results

    def create_proposal(
        self,
        *,
        scope_kind: str,
        scope_id: UUID,
        rule_id: UUID,
        building_ids: list[UUID],
    ) -> tuple[RowMapping, list[RowMapping]]:
        self.prepare("edit")
        if not building_ids:
            raise PlatformValidationError("proposal requires at least one building")
        self.get_rule(rule_id)
        number_rows: list[RowMapping] = []
        for building_id in building_ids:
            row = self.proposed_number_for_building(building_id)
            if row is None or row["kind"] != "proposed":
                raise PlatformConflictError(
                    "every proposal item needs a proposed number",
                    code="MISSING_PROPOSED_NUMBER",
                )
            number_rows.append(row)
        now = datetime.now(UTC)
        proposal_id = uuid4()
        proposal = (
            self.session.execute(
                text("""
                INSERT INTO house_numbering.proposals (
                    id,organization_id,project_id,scope_kind,scope_id,rule_id,status,revision,
                    created_by_actor_id,updated_by_actor_id,created_at,updated_at
                ) VALUES (:id,:org,:project,:kind,:scope,:rule,'draft',1,:actor,:actor,:now,:now)
                RETURNING *
            """),
                {
                    "id": proposal_id,
                    "org": self.org_id,
                    "project": self.project_id,
                    "kind": scope_kind,
                    "scope": scope_id,
                    "rule": rule_id,
                    "actor": self.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        items: list[RowMapping] = []
        for number in number_rows:
            items.append(
                self.session.execute(
                    text("""
                        INSERT INTO house_numbering.proposal_items (
                            id,organization_id,project_id,proposal_id,building_id,proposed_number,
                            source_number_id,created_at
                        ) VALUES (:id,:org,:project,:proposal,:building,:number,:source,:now)
                        RETURNING *
                    """),
                    {
                        "id": uuid4(),
                        "org": self.org_id,
                        "project": self.project_id,
                        "proposal": proposal_id,
                        "building": number["building_id"],
                        "number": number["number_text"],
                        "source": number["id"],
                        "now": now,
                    },
                )
                .mappings()
                .one()
            )
        self.audit(
            "house_numbering.proposal.create",
            "house_numbering_proposal",
            proposal_id,
            {"items": len(items)},
        )
        return proposal, items

    def proposal(
        self, proposal_id: UUID, *, for_update: bool = False
    ) -> tuple[RowMapping, list[RowMapping]]:
        self.prepare("edit" if for_update else "read")
        lock = " FOR UPDATE" if for_update else ""
        proposal = (
            self.session.execute(
                text(
                    """
                SELECT p.*,r.status AS rule_status,r.authority_ref
                FROM house_numbering.proposals p
                JOIN house_numbering.rules r
                  ON r.organization_id=p.organization_id AND r.project_id=p.project_id AND r.id=p.rule_id
                WHERE p.organization_id=:org AND p.project_id=:project AND p.id=:id
            """
                    + lock
                ),
                {"org": self.org_id, "project": self.project_id, "id": proposal_id},
            )
            .mappings()
            .first()
        )
        if proposal is None:
            raise PlatformNotFoundError("proposal not found")
        items = (
            self.session.execute(
                text("""
                SELECT i.*,b.eligibility,n.kind AS number_kind,n.route_id
                FROM house_numbering.proposal_items i
                JOIN house_numbering.buildings b
                  ON b.organization_id=i.organization_id AND b.project_id=i.project_id AND b.id=i.building_id
                LEFT JOIN house_numbering.address_numbers n
                  ON n.organization_id=i.organization_id AND n.project_id=i.project_id AND n.id=i.source_number_id
                WHERE i.organization_id=:org AND i.project_id=:project AND i.proposal_id=:id
                ORDER BY i.created_at,i.id
            """),
                {"org": self.org_id, "project": self.project_id, "id": proposal_id},
            )
            .mappings()
            .all()
        )
        return proposal, items

    def transition_proposal(
        self,
        proposal_id: UUID,
        *,
        expected_revision: int,
        action: str,
        comment: str | None,
        reviewer: bool,
    ) -> RowMapping:
        self.prepare("manage" if reviewer else "edit")
        proposal, items = self.proposal(proposal_id, for_update=True)
        if int(proposal["revision"]) != expected_revision:
            raise PlatformConflictError(
                "proposal revision is stale", code="STALE_PROPOSAL"
            )
        state = str(proposal["status"])
        now = datetime.now(UTC)
        if action == "submit" and state == "draft":
            if any(
                item["eligibility"] == "ineligible" or item["number_kind"] != "proposed"
                for item in items
            ):
                raise PlatformConflictError(
                    "proposal contains ineligible or stale items",
                    code="INVALID_PROPOSAL_ITEM",
                )
            self.session.execute(
                text("""
                    UPDATE house_numbering.address_numbers n SET kind='submitted',revision=revision+1,
                        updated_by_actor_id=:actor,updated_at=:now
                    FROM house_numbering.proposal_items i
                    WHERE i.organization_id=:org AND i.project_id=:project AND i.proposal_id=:proposal
                      AND n.organization_id=i.organization_id AND n.project_id=i.project_id
                      AND n.id=i.source_number_id AND n.kind='proposed'
                """),
                {
                    "actor": self.actor_id,
                    "now": now,
                    "org": self.org_id,
                    "project": self.project_id,
                    "proposal": proposal_id,
                },
            )
            new_state, submitted_at, decided_at = "submitted", now, None
        elif action == "reject" and state == "submitted" and reviewer:
            if not comment or not comment.strip():
                raise PlatformValidationError("rejection requires a reason")
            self.session.execute(
                text("""
                    UPDATE house_numbering.address_numbers n SET kind='proposed',revision=revision+1,
                        updated_by_actor_id=:actor,updated_at=:now
                    FROM house_numbering.proposal_items i
                    WHERE i.organization_id=:org AND i.project_id=:project AND i.proposal_id=:proposal
                      AND n.organization_id=i.organization_id AND n.project_id=i.project_id
                      AND n.id=i.source_number_id AND n.kind='submitted'
                """),
                {
                    "actor": self.actor_id,
                    "now": now,
                    "org": self.org_id,
                    "project": self.project_id,
                    "proposal": proposal_id,
                },
            )
            new_state, submitted_at, decided_at = "draft", None, now
        elif action == "approve" and state == "submitted" and reviewer:
            if (
                proposal["rule_status"] != "authoritative"
                or not proposal["authority_ref"]
            ):
                raise PlatformConflictError(
                    "approval requires authoritative rule",
                    code="RULE_NOT_AUTHORITATIVE",
                )
            if any(
                item["eligibility"] == "ineligible"
                or item["number_kind"] != "submitted"
                for item in items
            ):
                raise PlatformConflictError(
                    "proposal contains ineligible or stale items",
                    code="INVALID_PROPOSAL_ITEM",
                )
            self.session.execute(
                text("""
                    UPDATE house_numbering.address_numbers n SET kind='approved',revision=revision+1,
                        updated_by_actor_id=:actor,updated_at=:now
                    FROM house_numbering.proposal_items i
                    WHERE i.organization_id=:org AND i.project_id=:project AND i.proposal_id=:proposal
                      AND n.organization_id=i.organization_id AND n.project_id=i.project_id
                      AND n.id=i.source_number_id AND n.kind='submitted'
                """),
                {
                    "actor": self.actor_id,
                    "now": now,
                    "org": self.org_id,
                    "project": self.project_id,
                    "proposal": proposal_id,
                },
            )
            new_state, submitted_at, decided_at = (
                "approved",
                proposal["submitted_at"],
                now,
            )
        else:
            raise PlatformConflictError(
                "invalid proposal transition", code="INVALID_PROPOSAL_TRANSITION"
            )
        row = (
            self.session.execute(
                text("""
                UPDATE house_numbering.proposals
                SET status=:status,decision_comment=:comment,revision=revision+1,
                    updated_by_actor_id=:actor,submitted_at=:submitted,decided_at=:decided,updated_at=:now
                WHERE organization_id=:org AND project_id=:project AND id=:id
                RETURNING *
            """),
                {
                    "status": new_state,
                    "comment": comment,
                    "actor": self.actor_id,
                    "submitted": submitted_at,
                    "decided": decided_at,
                    "now": now,
                    "org": self.org_id,
                    "project": self.project_id,
                    "id": proposal_id,
                },
            )
            .mappings()
            .one()
        )
        self.audit(
            f"house_numbering.proposal.{action}",
            "house_numbering_proposal",
            proposal_id,
            {"state": new_state},
        )
        return row

    def enable_private_access(self) -> None:
        self.prepare("manage")
        set_extension_private_access(
            self.session, extension_key="house_numbering", enabled=True
        )
