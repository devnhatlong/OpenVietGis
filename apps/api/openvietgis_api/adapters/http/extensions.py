"""R014 Generic Internal Extension Framework HTTP adapter."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.extensions_repository import SqlExtensionsRepository
from openvietgis_api.domains.extensions.domain import (
    ExtensionDataRecord,
    ExtensionManifestRecord,
    ProjectActivationRecord,
)

router = APIRouter(tags=["extensions"])
_ORG = "/organizations/{organization_id}"
_PROJ = f"{_ORG}/projects/{{project_id}}"


def _manifest_wire(m: ExtensionManifestRecord) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "organization_id": str(m.organization_id),
        "extension_key": m.extension_key,
        "version": m.version,
        "api_compatibility": m.api_compatibility,
        "display_name": m.display_name,
        "description": m.description,
        "permissions": m.permissions,
        "commands": m.commands,
        "capabilities": m.capabilities,
        "entity_schemas": m.entity_schemas,
        "enabled": m.enabled,
        "created_at": m.created_at.isoformat(),
    }


def _act_wire(a: ProjectActivationRecord) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "manifest_id": str(a.manifest_id),
        "extension_key": a.extension_key,
        "status": a.status,
        "activated_at": a.activated_at.isoformat(),
    }


def _rec_wire(r: ExtensionDataRecord) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "extension_key": r.extension_key,
        "entity_name": r.entity_name,
        "payload": r.payload,
        "linked_layer_id": str(r.linked_layer_id) if r.linked_layer_id else None,
        "linked_feature_id": r.linked_feature_id,
        "created_at": r.created_at.isoformat(),
    }


class RegisterManifestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extension_key: str
    version: str
    api_compatibility: str = "1.x"
    display_name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)
    commands: list[dict[str, Any]] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    entity_schemas: dict[str, dict[str, Any]]


class ActivateExtensionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest_id: UUID


class CreateExtensionRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_name: str
    payload: dict[str, Any]
    linked_layer_id: UUID | None = None
    linked_feature_id: str | None = None


@router.post(f"{_ORG}/extensions/manifests", status_code=201)
def register_extension_manifest(
    organization_id: UUID,
    body: RegisterManifestRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id)
    rec = SqlExtensionsRepository(session).register_manifest(
        context=ctx,
        extension_key=body.extension_key,
        version=body.version,
        api_compatibility=body.api_compatibility,
        display_name=body.display_name,
        description=body.description,
        permissions=body.permissions,
        commands=body.commands,
        capabilities=body.capabilities,
        entity_schemas=body.entity_schemas,
    )
    return _manifest_wire(rec)


@router.get(f"{_ORG}/extensions/manifests")
def list_extension_manifests(
    organization_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id)
    items = SqlExtensionsRepository(session).list_manifests(context=ctx)
    return {"items": [_manifest_wire(m) for m in items]}


@router.post(f"{_PROJ}/extensions/activations", status_code=201)
def activate_project_extension(
    organization_id: UUID,
    project_id: UUID,
    body: ActivateExtensionRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _act_wire(
        SqlExtensionsRepository(session).activate_for_project(
            context=ctx, manifest_id=body.manifest_id
        )
    )


@router.post(f"{_PROJ}/extensions/activations/{{activation_id}}/deactivate")
def deactivate_project_extension(
    organization_id: UUID,
    project_id: UUID,
    activation_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _act_wire(
        SqlExtensionsRepository(session).deactivate_for_project(
            context=ctx, activation_id=activation_id
        )
    )


@router.get(f"{_PROJ}/extensions/activations")
def list_project_activations(
    organization_id: UUID,
    project_id: UUID,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    items = SqlExtensionsRepository(session).list_activations(context=ctx)
    return {"items": [_act_wire(a) for a in items]}


@router.post(f"{_PROJ}/extensions/{{extension_key}}/records", status_code=201)
def create_extension_record(
    organization_id: UUID,
    project_id: UUID,
    extension_key: str,
    body: CreateExtensionRecordRequest,
    auth: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    return _rec_wire(
        SqlExtensionsRepository(session).create_record(
            context=ctx,
            extension_key=extension_key,
            entity_name=body.entity_name,
            payload=body.payload,
            linked_layer_id=body.linked_layer_id,
            linked_feature_id=body.linked_feature_id,
        )
    )


@router.get(f"{_PROJ}/extensions/{{extension_key}}/records")
def list_extension_records(
    organization_id: UUID,
    project_id: UUID,
    extension_key: str,
    auth: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    entity_name: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    ctx = context_for(auth, organization_id=organization_id, project_id=project_id)
    items = SqlExtensionsRepository(session).list_records(
        context=ctx, extension_key=extension_key, entity_name=entity_name
    )
    return {"items": [_rec_wire(r) for r in items]}
