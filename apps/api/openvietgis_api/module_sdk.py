"""Stable internal SDK surface for trusted official modules.

Vertical modules depend on this file rather than persistence/http internals. Third-party
code is not auto-loaded by the official-module runtime.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.authorization import context_for
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.persistence.scope_helper import (
    append_project_audit,
    prepare_project_scope,
)
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission

__all__ = [
    "AuthenticatedRequest",
    "AuthorizationContext",
    "append_project_audit",
    "authenticate_request",
    "context_for",
    "get_db_session",
    "prepare_module_scope",
    "require_csrf",
    "set_private_data_access",
]


def prepare_module_scope(
    session: Session,
    context: AuthorizationContext,
    *,
    access: Literal["read", "edit", "manage"],
) -> None:
    permission = {
        "read": Permission.PROJECT_READ,
        "edit": Permission.PROJECT_EDIT,
        "manage": Permission.PROJECT_MANAGE,
    }[access]
    prepare_project_scope(session, context, permission=permission)


def set_private_data_access(session: Session, *, enabled: bool) -> None:
    """Explicit transaction-local guard used by private module tables' RLS policy."""
    session.execute(
        text("SELECT set_config('openvietgis.house_numbering_private_access', :flag, true)"),
        {"flag": "on" if enabled else "off"},
    )
