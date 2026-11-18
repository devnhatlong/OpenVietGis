from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import (
    require_member_context,
    require_service_audit_context,
)
from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.audit.service import redact_audit_metadata
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.tenancy.domain import ActorType


def _event_from_row(row: RowMapping) -> AuditEvent:
    return AuditEvent(
        id=row["id"],
        organization_id=row["organization_id"],
        actor_type=ActorType(row["actor_type"]),
        actor_id=row["actor_id"],
        actor_display_snapshot=row["actor_display_snapshot"],
        action=row["action"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        outcome=AuditOutcome(row["outcome"]),
        metadata=dict(row["metadata"]),
        created_at=row["created_at"],
    )


class SqlAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> None:
        if event.organization_id is not None:
            if event.actor_type == ActorType.HUMAN:
                context = AuthorizationContext(
                    actor=Actor("human", event.actor_id, event.actor_display_snapshot),
                    organization_id=event.organization_id,
                )
                require_member_context(self._session, context, event.organization_id)
            elif event.actor_type == ActorType.SERVICE_PRINCIPAL:
                require_service_audit_context(
                    self._session,
                    Actor("service_principal", event.actor_id, event.actor_display_snapshot),
                    event.organization_id,
                )
            else:
                raise PermissionError("tenant audit append requires an authenticated actor")
        self._session.execute(
            text(
                """
                INSERT INTO audit.audit_events (
                    id, organization_id, actor_type, actor_id, actor_display_snapshot,
                    action, resource_type, resource_id, outcome, metadata, created_at
                )
                VALUES (
                    :id, :organization_id, :actor_type, :actor_id, :actor_display_snapshot,
                    :action, :resource_type, :resource_id, :outcome,
                    CAST(:metadata AS jsonb), :created_at
                )
                """
            ),
            {
                "id": event.id,
                "organization_id": event.organization_id,
                "actor_type": event.actor_type.value,
                "actor_id": event.actor_id,
                "actor_display_snapshot": event.actor_display_snapshot,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "outcome": event.outcome.value,
                "metadata": json.dumps(redact_audit_metadata(event.metadata)),
                "created_at": event.created_at,
            },
        )

    def list_for_organization(
        self,
        organization_id: UUID,
        *,
        context: AuthorizationContext,
        limit: int,
    ) -> list[AuditEvent]:
        require_member_context(self._session, context, organization_id)
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT id, organization_id, actor_type, actor_id, actor_display_snapshot,
                           action, resource_type, resource_id, outcome, metadata, created_at
                    FROM audit.audit_events
                    WHERE organization_id = :organization_id
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                {"organization_id": organization_id, "limit": limit},
            )
            .mappings()
            .all()
        )
        return [_event_from_row(row) for row in rows]
