"""HTTP runtime for the trusted official House Numbering module."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from openvietgis_api.module_sdk import (
    AuthenticatedRequest,
    authenticate_request,
    context_for,
    get_db_session,
    require_csrf,
)
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator
from sqlalchemy.orm import Session

from modules.house_numbering.application import HouseNumberingService

router = APIRouter(tags=["house-numbering"])
_PROJ = "/organizations/{organization_id}/projects/{project_id}/modules/house-numbering"


def _service(
    organization_id: UUID,
    project_id: UUID,
    auth: AuthenticatedRequest,
    session: Session,
) -> HouseNumberingService:
    return HouseNumberingService(
        session,
        context_for(auth, organization_id=organization_id, project_id=project_id),
    )


class RuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=1, max_length=64)
    status: Literal["draft", "authoritative"] = "draft"
    authority_ref: str | None = Field(default=None, max_length=500)
    left_odd: bool = True
    suffix_style: Literal["letters", "dash"] = "letters"
    max_distance_m: float = Field(default=150, gt=0, le=5000)


class AreaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["current", "historic", "custom"] = "current"
    parent_id: UUID | None = None
    source_id: UUID | None = None
    feature_id: str | None = Field(default=None, max_length=128)


class RouteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    route_type: Literal["street", "alley"] = "street"
    parent_route_id: UUID | None = None
    prefix: str | None = Field(default=None, max_length=100)
    source_id: UUID
    feature_id: str = Field(min_length=1, max_length=128)
    direction_state: Literal["forward", "reverse"] = "forward"
    source_label: str = Field(default="manual", min_length=1, max_length=200)
    status: Literal["draft", "confirmed"] = "draft"

    @field_validator("prefix")
    @classmethod
    def valid_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped or any(
            not part.isdigit() or int(part) <= 0 for part in stripped.split("/")
        ):
            raise ValueError("prefix must be positive slash-separated numbers")
        return stripped


class RouteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: PositiveInt
    name: str = Field(min_length=1, max_length=200)
    direction_state: Literal["forward", "reverse"]
    status: Literal["draft", "confirmed"]


class BuildingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route_id: UUID | None = None
    area_id: UUID | None = None
    parcel_ref: str | None = Field(default=None, max_length=200)
    source_id: UUID
    feature_id: str = Field(min_length=1, max_length=128)
    eligibility: Literal["unknown", "eligible", "ineligible"] = "unknown"
    ineligibility_reason: str | None = Field(default=None, max_length=500)


class EligibilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: PositiveInt
    eligibility: Literal["unknown", "eligible", "ineligible"]
    reason: str | None = Field(default=None, max_length=500)


class InspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float
    crs_code: int = Field(gt=0)
    route_id: UUID
    rule_id: UUID
    existing_building_id: UUID | None = None


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    building_ids: list[UUID] = Field(min_length=1, max_length=5000)
    rule_id: UUID
    operation_id: UUID


class ProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_kind: Literal["route", "area"]
    scope_id: UUID
    rule_id: UUID
    building_ids: list[UUID] = Field(min_length=1, max_length=5000)


class ProposalTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: PositiveInt
    action: Literal["submit", "approve", "reject"]
    comment: str | None = Field(default=None, max_length=1000)


@router.get(f"{_PROJ}/rules")
def list_rules(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return {"items": _service(organization_id, project_id, auth, session).list_rules()}


@router.post(f"{_PROJ}/rules", status_code=201)
def create_rule(
    organization_id: UUID,
    project_id: UUID,
    body: RuleCreate,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).create_rule(
        **body.model_dump()
    )


@router.get(f"{_PROJ}/areas")
def list_areas(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return {"items": _service(organization_id, project_id, auth, session).list_areas()}


@router.post(f"{_PROJ}/areas", status_code=201)
def create_area(
    organization_id: UUID,
    project_id: UUID,
    body: AreaCreate,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).create_area(
        **body.model_dump()
    )


@router.get(f"{_PROJ}/routes")
def list_routes(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return {"items": _service(organization_id, project_id, auth, session).list_routes()}


@router.post(f"{_PROJ}/routes", status_code=201)
def create_route(
    organization_id: UUID,
    project_id: UUID,
    body: RouteCreate,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).create_route(
        **body.model_dump()
    )


@router.put(f"{_PROJ}/routes/{{route_id}}")
def update_route(
    organization_id: UUID,
    project_id: UUID,
    route_id: UUID,
    body: RouteUpdate,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).update_route(
        route_id, **body.model_dump()
    )


@router.delete(f"{_PROJ}/routes/{{route_id}}", status_code=204)
def delete_route(
    organization_id: UUID,
    project_id: UUID,
    route_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    _service(organization_id, project_id, auth, session).delete_route(route_id)
    return Response(status_code=204)


@router.get(f"{_PROJ}/buildings")
def list_buildings(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    route_id: Annotated[UUID | None, Query()] = None,
) -> dict[str, object]:
    return {
        "items": _service(organization_id, project_id, auth, session).list_buildings(
            route_id=route_id
        )
    }


@router.post(f"{_PROJ}/buildings", status_code=201)
def create_building(
    organization_id: UUID,
    project_id: UUID,
    body: BuildingCreate,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).create_building(
        **body.model_dump()
    )


@router.patch(f"{_PROJ}/buildings/{{building_id}}/eligibility")
def set_eligibility(
    organization_id: UUID,
    project_id: UUID,
    building_id: UUID,
    body: EligibilityUpdate,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(
        organization_id, project_id, auth, session
    ).set_building_eligibility(
        building_id,
        expected_revision=body.expected_revision,
        eligibility=body.eligibility,
        reason=body.reason,
    )


@router.post(f"{_PROJ}/inspect")
def inspect_location(
    organization_id: UUID,
    project_id: UUID,
    body: InspectRequest,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).inspect(
        **body.model_dump()
    )


@router.post(f"{_PROJ}/previews", status_code=201)
def preview_numbering(
    organization_id: UUID,
    project_id: UUID,
    body: PreviewRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).preview_assignment(
        **body.model_dump()
    )


@router.post(f"{_PROJ}/previews/{{preview_id}}/apply")
def apply_numbering(
    organization_id: UUID,
    project_id: UUID,
    preview_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return {
        "items": _service(organization_id, project_id, auth, session).apply_preview(
            preview_id
        )
    }


@router.post(f"{_PROJ}/proposals", status_code=201)
def create_proposal(
    organization_id: UUID,
    project_id: UUID,
    body: ProposalCreate,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).create_proposal(
        **body.model_dump()
    )


@router.get(f"{_PROJ}/proposals/{{proposal_id}}")
def get_proposal(
    organization_id: UUID,
    project_id: UUID,
    proposal_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    return _service(organization_id, project_id, auth, session).get_proposal(
        proposal_id
    )


@router.post(f"{_PROJ}/proposals/{{proposal_id}}/transition")
def transition_proposal(
    organization_id: UUID,
    project_id: UUID,
    proposal_id: UUID,
    body: ProposalTransition,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    reviewer = body.action in {"approve", "reject"}
    return _service(organization_id, project_id, auth, session).transition_proposal(
        proposal_id,
        expected_revision=body.expected_revision,
        action=body.action,
        comment=body.comment,
        reviewer=reviewer,
    )
