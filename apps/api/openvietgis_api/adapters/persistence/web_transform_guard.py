"""Restricted SQL helpers for non-fixture-dependent R003 CRS transformations.

Only the independently verified Web Mercator direct edges are available in
these consumers. A registry edge requiring source provenance is NOT permission
to apply it to arbitrary imported/edited geometry.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.spatial.crs import (
    WEB_MERCATOR_GEOGRAPHIC_BOUNDS,
    WEB_MERCATOR_PROJECTED_BOUNDS,
    get_transformation_profile,
)


def web_transform_sql(
    expression: str, source_srid: int, target_srid: int, prefix: str
) -> tuple[str, dict[str, Any], str]:
    profile = get_transformation_profile(source_srid, target_srid)
    if (
        {source_srid, target_srid} != {4326, 3857}
        or profile is None
        or profile.requires_trusted_fixture
        or len(profile.steps) != 1
    ):
        raise PlatformValidationError(
            "no approved transformation for this operation; use a supported native CRS",
            code="UNSUPPORTED_TRANSFORMATION",
        )
    step = profile.steps[0]
    fn = "ST_InverseTransformPipeline" if step.inverse else "ST_TransformPipeline"
    return (
        f"{fn}({expression}, :{prefix}_pipeline, :{prefix}_target)",
        {f"{prefix}_pipeline": step.pipeline, f"{prefix}_target": target_srid},
        profile.operation_id,
    )


def require_web_domain(
    session: Session,
    *,
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    native_srid: int,
    expression: str = "geometry",
    expression_params: dict[str, Any] | None = None,
    expression_srid: int | None = None,
    margin: float = 0,
) -> None:
    """Fail the entire source when a native or transformed vertex is out of area.

    A rectangular bounds test on an actual geometry bbox includes every vertex;
    margin reserves the projected distance before an inverse buffer transform.
    Callers hold the current source/read scope and lock.
    """
    srid = native_srid if expression_srid is None else expression_srid
    if srid not in (4326, 3857):
        raise PlatformValidationError(
            "unsupported transform CRS", code="UNSUPPORTED_TRANSFORMATION"
        )
    bounds = WEB_MERCATOR_GEOGRAPHIC_BOUNDS if srid == 4326 else WEB_MERCATOR_PROJECTED_BOUNDS
    invalid = session.execute(
        text(f"""
            SELECT EXISTS (
                SELECT 1
                FROM spatial.reference_features
                WHERE organization_id=:org AND project_id=:proj AND source_id=:src
                AND (
                    CASE WHEN geometry_state='present' AND geometry IS NOT NULL
                        AND ST_SRID(geometry)=:native_srid AND ST_IsValid(geometry)
                        AND ST_Zmflag(geometry)=0 AND NOT ST_IsEmpty(geometry)
                    THEN (
                        ST_XMin({expression}) >= :min_x
                        AND ST_XMax({expression}) <= :max_x
                        AND ST_YMin({expression}) >= :min_y
                        AND ST_YMax({expression}) <= :max_y
                    ) ELSE false END
                ) IS NOT TRUE
            )
        """),
        {
            "org": organization_id,
            "proj": project_id,
            "src": source_id,
            "native_srid": native_srid,
            "min_x": bounds.min_x + margin,
            "min_y": bounds.min_y + margin,
            "max_x": bounds.max_x - margin,
            "max_y": bounds.max_y - margin,
            **(expression_params or {}),
        },
    ).scalar_one()
    if invalid:
        raise PlatformValidationError(
            "geometry is outside the verified transformation domain",
            code="TRANSFORMATION_OUT_OF_AREA",
        )
