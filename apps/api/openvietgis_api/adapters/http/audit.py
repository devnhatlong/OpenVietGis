from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
)
from openvietgis_api.adapters.http.tenant_access import require_human_permission
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.domains.audit.domain import AuditEvent
from openvietgis_api.domains.audit.service import AuditService
from openvietgis_api.domains.authorization.permissions import Permission

router = APIRouter(tags=["audit"])


def _serialize(event: AuditEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "organization_id": event.organization_id,
        "actor_type": event.actor_type.value,
        "actor_id": event.actor_id,
        "actor_display_snapshot": event.actor_display_snapshot,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "outcome": event.outcome.value,
        "metadata": event.metadata,
        "created_at": event.created_at,
    }


@router.get("/organizations/{organization_id}/audit-events")
def list_audit_events(
    organization_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(authenticate_request)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    require_human_permission(
        session,
        authentication,
        organization_id,
        Permission.AUDIT_READ,
    )
    context = context_for(authentication, organization_id=organization_id)
    events = AuditService(SqlAuditRepository(session)).list_events(
        context=context,
        organization_id=organization_id,
        limit=limit,
    )
    return [_serialize(event) for event in events]
