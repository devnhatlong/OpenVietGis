"""Pinned R004 presentation reads using approved fixed PostGIS operations only."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.spatial_repository import (
    SqlSpatialRepository,
    _read_native_wkb,
)
from openvietgis_api.adapters.persistence.spatial_transform import _provenance
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.maps.viewport import (
    MAP_STATEMENT_TIMEOUT_MS,
    MAX_RENDER_SOURCE_FEATURES,
    MAX_VIEWPORT_POSITIONS,
    DisplayExtentWire,
    MapReadUnavailableError,
    RenderFeature,
    ViewportBounds,
    ViewportWire,
    build_viewport_response,
)
from openvietgis_api.domains.spatial.crs import (
    WEB_MERCATOR_MAX_LATITUDE,
    get_transformation_profile,
)
from openvietgis_api.domains.spatial.domain import (
    SUPPORTED_FAMILIES,
    DataSource,
    GeometryDimensions,
    SourceKind,
    SpatialValidationError,
)
from openvietgis_api.domains.spatial.ports import (
    SpatialTransformationOutOfAreaError,
    SpatialUnsupportedTransformationError,
)
from openvietgis_api.domains.spatial.service import (
    FeatureReadContextWire,
    SpatialFeatureService,
)


def _display_ctes(source: DataSource) -> tuple[str, dict[str, object]]:
    """Build identifiers from fixed code only; all pipeline values are bound."""
    profile = (
        get_transformation_profile(source.stored_crs, 4326)
        if source.stored_crs is not None and source.stored_crs != 4326
        else None
    )
    if source.stored_crs != 4326 and profile is None:
        raise SpatialUnsupportedTransformationError("no approved geographic presentation edge")
    params: dict[str, object] = {}
    ctes = [
        """
        native AS NOT MATERIALIZED (
            SELECT feature_id,geometry,
                content_revision=:content AND schema_revision=:schema
                AND geometry_state='present'
                AND ST_SRID(geometry)=:native_srid AND ST_Zmflag(geometry)=0
                AND ST_GeometryType(geometry)=:geometry_type
                AND ST_NPoints(geometry) BETWEEN 1 AND 4096
                AND NOT ST_IsEmpty(geometry) AND ST_IsValid(geometry) AS valid
            FROM spatial.reference_features
            WHERE organization_id=:organization AND project_id=:project AND source_id=:source
            ORDER BY feature_id COLLATE "C" LIMIT 10001
        )
    """
    ]
    previous = "native"
    current_code = source.stored_crs
    for index, step in enumerate(profile.steps if profile is not None else ()):
        assert profile is not None
        function = "ST_InverseTransformPipeline" if step.inverse else "ST_TransformPipeline"
        # Check every geographic intermediate before the following fixed step.
        check = "valid"
        if current_code in (4326, 4756):
            bounds = profile.geographic_bounds
            params |= {
                f"minx{index}": bounds.min_x,
                f"miny{index}": bounds.min_y,
                f"maxx{index}": bounds.max_x,
                f"maxy{index}": bounds.max_y,
            }
            check += (
                " AND ST_CoveredBy(geometry,ST_MakeEnvelope("
                f":minx{index},:miny{index},:maxx{index},:maxy{index},{current_code}))"
            )
        params |= {f"pipeline{index}": step.pipeline, f"target{index}": step.target_code}
        name = f"step{index}"
        ctes.append(f"""
            {name} AS NOT MATERIALIZED (
                SELECT feature_id,CASE WHEN {check}
                    THEN {function}(geometry,:pipeline{index},:target{index}) END AS geometry,
                    {check} AS valid FROM {previous}
            )
        """)
        previous = name
        current_code = step.target_code
    display_check = (
        "valid AND geometry IS NOT NULL AND ST_SRID(geometry)=4326"
        " AND ST_Zmflag(geometry)=0 AND ST_NPoints(geometry) BETWEEN 1 AND 4096"
        " AND NOT ST_IsEmpty(geometry) AND ST_IsValid(geometry)"
        " AND ST_CoveredBy(geometry,ST_MakeEnvelope(-180,:display_south,180,:display_north,4326))"
    )
    params |= {
        "display_south": -WEB_MERCATOR_MAX_LATITUDE,
        "display_north": WEB_MERCATOR_MAX_LATITUDE,
    }
    if profile is not None:
        bounds = profile.geographic_bounds
        params |= {
            "area_west": bounds.min_x,
            "area_south": bounds.min_y,
            "area_east": bounds.max_x,
            "area_north": bounds.max_y,
        }
        display_check += (
            " AND ST_CoveredBy(geometry,ST_MakeEnvelope("
            ":area_west,:area_south,:area_east,:area_north,4326))"
        )
    ctes.append(f"""
        display AS NOT MATERIALIZED (
            SELECT feature_id,geometry,{display_check} AS valid FROM {previous}
        )
    """)
    return "WITH " + ",".join(ctes), params


class SqlMapViewportRepository(SqlSpatialRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def _snapshot(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        content_revision: str,
        schema_revision: str,
    ) -> tuple[DataSource, FeatureReadContextWire, str, dict[str, object]]:
        self._session.execute(
            text("SELECT set_config('statement_timeout',:timeout,true)"),
            {"timeout": f"{MAP_STATEMENT_TIMEOUT_MS}ms"},
        )
        detail, wire = SpatialFeatureService(self)._snapshot(
            context=context,
            layer_id=layer_id,
            content_revision=content_revision,
            schema_revision=schema_revision,
            include_geometry=True,
            response_crs=4326,
        )
        source = detail.source
        if (
            source.kind
            not in (
                SourceKind.REFERENCE_FIXTURE,
                SourceKind.IMPORTED_FILE,
                SourceKind.DERIVED_PROCESSING,
            )
            or source.dimensions != GeometryDimensions.XY
            or source.geometry_family not in SUPPORTED_FAMILIES
            or source.feature_count is None
            or source.feature_count > MAX_RENDER_SOURCE_FEATURES
        ):
            raise SpatialUnsupportedTransformationError("source exceeds supported render profile")
        if source.stored_crs != 4326:
            assert source.stored_crs is not None
            profile = get_transformation_profile(source.stored_crs, 4326)
            if profile is None:
                raise SpatialUnsupportedTransformationError("no approved direct operation")
            _provenance(source, profile)
        ctes, params = _display_ctes(source)
        params |= dict(self._scope(context, permission=Permission.PROJECT_READ))
        params |= {
            "source": source.id,
            "content": content_revision,
            "schema": schema_revision,
            "native_srid": source.stored_crs,
            "geometry_type": "ST_" + source.geometry_family.value,
        }
        # A bounded trusted source is checked in full, including geometry outside
        # this viewport, before returning any apparently authoritative subset.
        checked = (
            self._session.execute(
                text(
                    ctes + " SELECT count(*) AS count,"
                    "COALESCE(bool_and(valid IS TRUE),true) AS valid"
                    " FROM display"
                ),
                params,
            )
            .mappings()
            .one()
        )
        if (
            checked["count"] != source.feature_count
            or checked["count"] > MAX_RENDER_SOURCE_FEATURES
        ):
            raise SpatialValidationError("render snapshot count disagrees")
        if not checked["valid"]:
            raise SpatialTransformationOutOfAreaError("source is outside approved display evidence")
        return source, wire, ctes, params

    def viewport(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        content_revision: str,
        schema_revision: str,
        bounds: ViewportBounds,
        limit: int = 500,
    ) -> ViewportWire:
        try:
            _, wire, ctes, params = self._snapshot(
                context=context,
                layer_id=layer_id,
                content_revision=content_revision,
                schema_revision=schema_revision,
            )
            # LIMIT first bounds candidate cardinality. Window only counts
            # positions; WKB is encoded only for the <=20000-position prefix,
            # plus a metadata-only first over-budget marker. No all-row WKB.
            query = (
                ctes
                + """
                ,candidate AS MATERIALIZED (
                    SELECT feature_id,ST_NPoints(geometry) AS positions
                    FROM display
                    WHERE valid AND ST_Intersects(geometry,
                        ST_MakeEnvelope(:west,:south,:east,:north,4326))
                    ORDER BY feature_id COLLATE "C" LIMIT :lookahead
                ),prefix AS MATERIALIZED (
                    SELECT *,SUM(positions) OVER (
                        ORDER BY feature_id COLLATE "C" ROWS UNBOUNDED PRECEDING
                    ) AS total_positions FROM candidate
                )
                SELECT prefix.feature_id,positions,
                    CASE WHEN total_positions<=:position_budget
                        THEN ST_AsBinary(display.geometry,'NDR') END AS wkb
                FROM prefix JOIN display ON display.feature_id=prefix.feature_id
                WHERE total_positions-positions<=:position_budget
                ORDER BY prefix.feature_id COLLATE "C"
            """
            )
            rows = self._session.execute(
                text(query),
                params
                | {
                    "west": bounds.west,
                    "south": bounds.south,
                    "east": bounds.east,
                    "north": bounds.north,
                    "lookahead": limit + 1,
                    "position_budget": MAX_VIEWPORT_POSITIONS,
                },
            ).mappings()

            def features() -> Iterator[RenderFeature]:
                for row in rows:
                    wkb = row["wkb"]
                    yield RenderFeature(
                        row["feature_id"],
                        _read_native_wkb(bytes(wkb), 4326) if wkb is not None else None,
                        row["positions"],
                    )

            return build_viewport_response(wire, features(), limit=limit)
        except SQLAlchemyError:
            self._session.rollback()
            raise MapReadUnavailableError("bounded map read unavailable") from None

    def display_extent(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        content_revision: str,
        schema_revision: str,
    ) -> DisplayExtentWire:
        try:
            _, wire, ctes, params = self._snapshot(
                context=context,
                layer_id=layer_id,
                content_revision=content_revision,
                schema_revision=schema_revision,
            )
            row = (
                self._session.execute(
                    text(
                        ctes
                        + """
                    SELECT ST_XMin(extent) AS west,ST_YMin(extent) AS south,
                        ST_XMax(extent) AS east,ST_YMax(extent) AS north
                    FROM (SELECT ST_Extent(geometry) AS extent FROM display) AS actual
                """
                    ),
                    params,
                )
                .mappings()
                .one()
            )
            if row["west"] is None:
                return {"context": wire, "state": "empty", "bounds": None}
            return {
                "context": wire,
                "state": "available",
                "bounds": (row["west"], row["south"], row["east"], row["north"]),
            }
        except SQLAlchemyError:
            self._session.rollback()
            raise MapReadUnavailableError("bounded map extent unavailable") from None
