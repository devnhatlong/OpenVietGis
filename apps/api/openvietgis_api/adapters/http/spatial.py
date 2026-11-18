"""R003 Project-scoped spatial catalog HTTP adapter.

Authorization, lifecycle, optimistic concurrency, and durable evidence belong
to the service and transaction-bound repository. HTTP validates the frozen
wire contract and exposes only logical metadata, never a physical binding.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.domains.spatial.crs import (
    CRSProfileWire,
    get_coordinate_reference,
    get_crs_profile,
)
from openvietgis_api.domains.spatial.domain import (
    MAX_REVISION,
    CatalogChange,
    Extent,
    SourceField,
)
from openvietgis_api.domains.spatial.service import (
    LayerDetail,
    LayerMutationResult,
    SourceDetail,
    SourceMutationResult,
    SpatialCatalogService,
    SpatialFeatureService,
    SpatialHistoryService,
    SpatialLayerService,
)

router = APIRouter(tags=["spatial"])
_SOURCE_PATH = "/organizations/{organization_id}/projects/{project_id}/spatial/sources"

SourceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ReferenceKey = Annotated[
    str, StringConstraints(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
]
ExpectedRevision = Annotated[int, Field(strict=True, ge=1, le=MAX_REVISION)]


def _safe_name(value: str) -> str:
    # The database and JSON transport require valid UTF-8 and cannot store NUL.
    # Reject before constructing a domain object, without reflecting user text.
    if "\x00" in value:
        raise ValueError("invalid source name")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("invalid source name") from None
    return value


class RegisterSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reference_key: ReferenceKey
    name: SourceName

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_name(value)


class DeclaredCRSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    authority: Literal["EPSG"]
    code: Annotated[int, Field(strict=True, ge=1, le=2**31 - 1)]
    coordinate_order: Literal["xy"]


class UpdateSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: ExpectedRevision
    name: SourceName | None = None
    declared_crs: DeclaredCRSRequest | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return _safe_name(value) if value is not None else None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not (self.model_fields_set & {"name", "declared_crs"}):
            raise ValueError("at least one source change required")
        if ("name" in self.model_fields_set and self.name is None) or (
            "declared_crs" in self.model_fields_set and self.declared_crs is None
        ):
            raise ValueError("source changes cannot be null")
        return self


class RetireSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: ExpectedRevision


def _service(session: Session) -> SpatialCatalogService:
    # R002 authentication binds this same session. The service's prepare_scope
    # checks the live tenant, Project, permission ceiling and project RLS proof.
    return SpatialCatalogService(SqlSpatialRepository(session))


def _profile(code: int | None) -> CRSProfileWire | None:
    if code is None:
        return None
    profile = get_crs_profile(code)
    if profile is None:
        raise RuntimeError("unknown persisted CRS definition")
    return profile.to_wire()


def _extent(extent: Extent | None) -> dict[str, object] | None:
    if extent is None:
        return None
    reference = get_coordinate_reference(extent.crs_code)
    if reference is None:
        raise RuntimeError("extent has no readable coordinate reference")
    return {
        "min_x": extent.min_x,
        "min_y": extent.min_y,
        "max_x": extent.max_x,
        "max_y": extent.max_y,
        "coordinate_reference": reference.to_wire(),
    }


def _field(field: SourceField) -> dict[str, object]:
    return {
        "field_id": field.field_id,
        "name": field.name,
        "ordinal": field.ordinal,
        "type": field.type.value,
        "nullable": field.nullable,
    }


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat().removesuffix("+00:00") + "Z" if value is not None else None


def _source(detail: SourceDetail) -> dict[str, object]:
    source = detail.source
    return {
        "id": source.id,
        "organization_id": source.organization_id,
        "project_id": source.project_id,
        "name": source.name,
        "kind": source.kind.value,
        "provenance": {
            "reference_key": source.reference_key,
            "fixture_version": source.fixture_version,
            "manifest_digest": source.manifest_digest,
            "source_asset_id": source.source_asset_id,
        },
        "lifecycle": source.lifecycle.value,
        "validation_state": source.validation_state.value,
        "validation_reason": (
            source.validation_reason.to_wire() if source.validation_reason else None
        ),
        "source_crs": _profile(source.source_crs),
        "stored_crs": _profile(source.stored_crs),
        "schema": {
            "schema_revision": source.schema_revision,
            "fields": [_field(field) for field in detail.fields],
            "geometry_family": source.geometry_family.value,
            "dimensions": source.dimensions.value,
            "state": source.schema_state.value,
        },
        "feature_count_state": source.feature_count_state.value,
        "feature_count": source.feature_count,
        "extent_state": source.extent_state.value,
        "extent": _extent(source.extent),
        "catalog_revision": source.catalog_revision,
        "content_revision": source.content_revision,
        "schema_revision": source.schema_revision,
        "created_at": _timestamp(source.created_at),
        "updated_at": _timestamp(source.updated_at),
        "retired_at": _timestamp(source.retired_at),
    }


def _mutation(result: SourceMutationResult) -> dict[str, object]:
    source, change = result.source, result.change
    # project.edit/manage may be allowed without project.read. Do not use the
    # detail serializer here, or disclose source attributes, schema, or extent.
    return {
        "organization_id": source.organization_id,
        "project_id": source.project_id,
        "resource_type": "data_source",
        "resource_id": source.id,
        "change_id": change.id,
        "prior_revision": change.prior_revision.to_wire() if change.prior_revision else None,
        "new_revision": change.new_revision.to_wire(),
        "lifecycle": source.lifecycle.value,
        "validation_state": source.validation_state.value,
        "validation_reason": (
            source.validation_reason.to_wire() if source.validation_reason else None
        ),
    }


@router.get(_SOURCE_PATH, operation_id="listSpatialSources")
def list_sources(
    organization_id: UUID,
    project_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    after_id: UUID | None = None,
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    page = _service(session).list_sources(context=context, after_id=after_id, limit=limit)
    return {
        "organization_id": organization_id,
        "project_id": project_id,
        "items": [_source(item) for item in page.items],
        "next_after_id": page.next_after_id,
    }


@router.post(_SOURCE_PATH, operation_id="registerSpatialSource", status_code=201)
def register_source(
    organization_id: UUID,
    project_id: UUID,
    payload: RegisterSourceRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _mutation(
        _service(session).register_source(
            context=context, reference_key=payload.reference_key, name=payload.name
        )
    )


@router.get(_SOURCE_PATH + "/{source_id}", operation_id="getSpatialSource")
def get_source(
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _source(_service(session).get_source(context=context, source_id=source_id))


@router.patch(_SOURCE_PATH + "/{source_id}", operation_id="updateSpatialSource")
def update_source(
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    payload: UpdateSourceRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _mutation(
        _service(session).update_source(
            context=context,
            source_id=source_id,
            expected_revision=payload.expected_revision,
            name=payload.name,
            declared_crs=payload.declared_crs.code if payload.declared_crs else None,
        )
    )


@router.post(_SOURCE_PATH + "/{source_id}/retire", operation_id="retireSpatialSource")
def retire_source(
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    payload: RetireSourceRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _mutation(
        _service(session).retire_source(
            context=context, source_id=source_id, expected_revision=payload.expected_revision
        )
    )


_LAYER_PATH = "/organizations/{organization_id}/projects/{project_id}/layers"


class CreateLayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: Annotated[UUID, Field(strict=False)]
    name: SourceName

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("source identifier must be text")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_name(value)


class RenameLayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision: ExpectedRevision
    name: SourceName

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_name(value)


def _layer_service(session: Session) -> SpatialLayerService:
    return SpatialLayerService(SqlSpatialRepository(session))


def _layer(detail: LayerDetail) -> dict[str, object]:
    layer = detail.layer
    return {
        "id": layer.id,
        "organization_id": layer.organization_id,
        "project_id": layer.project_id,
        "name": layer.name,
        "source_id": layer.source_id,
        "lifecycle": layer.lifecycle.value,
        "layer_revision": layer.layer_revision,
        "source": _source(detail.source),
        "capabilities": [
            {
                "name": capability.name,
                "technical_supported": capability.technical_supported,
                "available": capability.available,
                "required_permission": capability.required_permission,
                "actor_authorized": capability.actor_authorized,
            }
            for capability in detail.capabilities
        ],
        "created_at": _timestamp(layer.created_at),
        "updated_at": _timestamp(layer.updated_at),
        "retired_at": _timestamp(layer.retired_at),
    }


def _layer_mutation(result: LayerMutationResult) -> dict[str, object]:
    layer, change = result.layer, result.change
    return {
        "organization_id": layer.organization_id,
        "project_id": layer.project_id,
        "resource_type": "layer",
        "resource_id": layer.id,
        "change_id": change.id,
        "prior_revision": change.prior_revision.to_wire() if change.prior_revision else None,
        "new_revision": change.new_revision.to_wire(),
        "lifecycle": layer.lifecycle.value,
    }


@router.get(_LAYER_PATH, operation_id="listSpatialLayers")
def list_layers(
    organization_id: UUID,
    project_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    after_id: UUID | None = None,
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    page = _layer_service(session).list_layers(context=context, after_id=after_id, limit=limit)
    return {
        "organization_id": organization_id,
        "project_id": project_id,
        "items": [_layer(detail) for detail in page.items],
        "next_after_id": page.next_after_id,
    }


@router.post(_LAYER_PATH, operation_id="createSpatialLayer", status_code=201)
def create_layer(
    organization_id: UUID,
    project_id: UUID,
    payload: CreateLayerRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _layer_mutation(
        _layer_service(session).create_layer(
            context=context, source_id=payload.source_id, name=payload.name
        )
    )


@router.get(_LAYER_PATH + "/{layer_id}", operation_id="getSpatialLayer")
def get_layer(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _layer(_layer_service(session).get_layer(context=context, layer_id=layer_id))


@router.patch(_LAYER_PATH + "/{layer_id}", operation_id="renameSpatialLayer")
def rename_layer(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    payload: RenameLayerRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _layer_mutation(
        _layer_service(session).rename_layer(
            context=context,
            layer_id=layer_id,
            expected_revision=payload.expected_revision,
            name=payload.name,
        )
    )


@router.post(_LAYER_PATH + "/{layer_id}/retire", operation_id="retireSpatialLayer")
def retire_layer(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    payload: RetireSourceRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    return _layer_mutation(
        _layer_service(session).retire_layer(
            context=context, layer_id=layer_id, expected_revision=payload.expected_revision
        )
    )


_FEATURE_PATH = _LAYER_PATH + "/{layer_id}/features"
_ReadPin = Annotated[str, Query(pattern=r"^[a-f0-9]{64}$")]
_ResponseCRS = Annotated[int, Query(ge=1, le=2147483647)]
_AfterFeature = Annotated[str, Query(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
_FeatureID = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


@router.get(_FEATURE_PATH, operation_id="pageSpatialFeatures")
def read_features(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    content_revision: _ReadPin,
    schema_revision: _ReadPin,
    include_geometry: bool = True,
    response_crs: _ResponseCRS | None = None,
    after_feature_id: _AfterFeature | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    service = SpatialFeatureService(SqlSpatialRepository(session))
    return dict(
        service.read_features(
            context=context,
            layer_id=layer_id,
            content_revision=content_revision,
            schema_revision=schema_revision,
            include_geometry=include_geometry,
            response_crs=response_crs,
            after_feature_id=after_feature_id,
            limit=limit,
        )
    )


@router.get(_FEATURE_PATH + "/{feature_id}", operation_id="getSpatialFeature")
def get_feature(
    organization_id: UUID,
    project_id: UUID,
    layer_id: UUID,
    feature_id: _FeatureID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    content_revision: _ReadPin,
    schema_revision: _ReadPin,
    include_geometry: bool = True,
    response_crs: _ResponseCRS | None = None,
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    service = SpatialFeatureService(SqlSpatialRepository(session))
    return dict(
        service.get_feature(
            context=context,
            layer_id=layer_id,
            feature_id=feature_id,
            content_revision=content_revision,
            schema_revision=schema_revision,
            include_geometry=include_geometry,
            response_crs=response_crs,
        )
    )


_CHANGE_PATH = "/organizations/{organization_id}/projects/{project_id}/spatial/changes"


def _catalog_change(change: CatalogChange) -> dict[str, object]:
    # Internal scoped FKs, raw attributes, native geometry and storage locators
    # are not part of this public history wire contract.
    return {
        "id": change.id,
        "organization_id": change.organization_id,
        "project_id": change.project_id,
        "resource_type": change.resource_type.value,
        "resource_id": change.resource_id,
        "actor_type": change.actor_type.value,
        "actor_id": change.actor_id,
        "actor_display_snapshot": change.actor_display_snapshot,
        "operation": change.operation.value,
        "created_at": _timestamp(change.created_at),
        "audit_event_id": change.audit_event_id,
        "prior_revision": change.prior_revision.to_wire() if change.prior_revision else None,
        "new_revision": change.new_revision.to_wire(),
        "changes": [value.to_wire() for value in change.changes],
    }


@router.get(_CHANGE_PATH, operation_id="listSpatialCatalogChanges")
def list_changes(
    organization_id: UUID,
    project_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    after_id: UUID | None = None,
) -> dict[str, object]:
    context = context_for(authentication, organization_id=organization_id, project_id=project_id)
    page = SpatialHistoryService(SqlSpatialRepository(session)).list_changes(
        context=context, after_id=after_id, limit=limit
    )
    return {
        "organization_id": organization_id,
        "project_id": project_id,
        "items": [_catalog_change(change) for change in page.items],
        "next_after_id": page.next_after_id,
    }
