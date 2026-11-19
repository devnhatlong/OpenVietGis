"""Authorized revision-pinned presentation reads; never general spatial queries."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
)
from openvietgis_api.adapters.persistence.map_viewport import SqlMapViewportRepository
from openvietgis_api.domains.maps.viewport import ViewportBounds
from openvietgis_api.domains.spatial.domain import SpatialValidationError
from openvietgis_api.domains.spatial.ports import SpatialInvalidFeatureRequestError


def _bounds(west: float, south: float, east: float, north: float) -> ViewportBounds:
    try:
        return ViewportBounds(west, south, east, north)
    except SpatialValidationError:
        raise SpatialInvalidFeatureRequestError("invalid viewport") from None


router = APIRouter(tags=["map-workspace"])
_LAYER = "/organizations/{organization_id}/projects/{project_id}/layers/{layer_id}"
_ReadPin = Annotated[str, Query(pattern=r"^[a-f0-9]{64}$")]
_Coordinate = Annotated[float, Query(allow_inf_nan=False)]


@router.get(_LAYER + "/viewport", operation_id="getMapViewport")
def get_map_viewport(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    response: Response,
    content_revision: _ReadPin,
    schema_revision: _ReadPin,
    west: _Coordinate,
    south: _Coordinate,
    east: _Coordinate,
    north: _Coordinate,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return dict(
        SqlMapViewportRepository(session).viewport(
            context=context,
            layer_id=layer_id,
            content_revision=content_revision,
            schema_revision=schema_revision,
            bounds=_bounds(west, south, east, north),
            limit=limit,
        )
    )


@router.get(_LAYER + "/display-extent", operation_id="getMapDisplayExtent")
def get_map_display_extent(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    response: Response,
    content_revision: _ReadPin,
    schema_revision: _ReadPin,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return dict(
        SqlMapViewportRepository(session).display_extent(
            context=context,
            layer_id=layer_id,
            content_revision=content_revision,
            schema_revision=schema_revision,
        )
    )
