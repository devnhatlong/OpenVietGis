from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def set_request_context(
    session: Session,
    *,
    organization_id: UUID | None,
    actor_user_id: UUID | None = None,
) -> None:
    session.execute(
        text("SELECT set_config('openvietgis.organization_id', :value, true)"),
        {"value": str(organization_id) if organization_id else ""},
    )
    session.execute(
        text("SELECT set_config('openvietgis.actor_user_id', :value, true)"),
        {"value": str(actor_user_id) if actor_user_id else ""},
    )


def clear_request_context(session: Session) -> None:
    set_request_context(session, organization_id=None, actor_user_id=None)
