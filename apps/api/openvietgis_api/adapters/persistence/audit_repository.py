from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from openvietgis_api.domains.audit.domain import AuditEvent


class SqlAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> None:
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
                "metadata": __import__("json").dumps(event.metadata),
                "created_at": event.created_at,
            },
        )