from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session, SessionTransaction

from openvietgis_api.domains.authorization.context import (
    Actor,
    AuthorizationContext,
    InvitationAcceptanceContext,
    TenantContext,
)
from openvietgis_api.domains.authorization.service import TenantResourceNotFoundError

_STATE_KEY = "openvietgis.transaction_authorization"


@dataclass(slots=True)
class _TransactionScope:
    transaction: SessionTransaction
    authenticated_user_id: UUID | None = None
    authenticated_organization_id: UUID | None = None
    authenticated_service_principal_id: UUID | None = None
    authenticated_credential_id: UUID | None = None
    nested_transaction: SessionTransaction | None = None
    organization_id: UUID | None = None
    actor_user_id: UUID | None = None
    member_verified: bool = False
    invitation_id: UUID | None = None


def _state(session: Session) -> _TransactionScope:
    transaction = session.get_transaction()
    if transaction is None:
        transaction = session.begin()
    current = session.info.get(_STATE_KEY)
    if not isinstance(current, _TransactionScope) or current.transaction is not transaction:
        current = _TransactionScope(transaction=transaction)
        session.info[_STATE_KEY] = current
    nested = session.get_nested_transaction()
    if nested is not current.nested_transaction:
        # PostgreSQL rolls SET LOCAL back with savepoints. Never reuse an
        # authorization proof established in a different savepoint.
        current.nested_transaction = nested
        current.organization_id = None
        current.actor_user_id = None
        current.member_verified = False
        current.invitation_id = None
    return current


def set_request_context(
    session: Session,
    *,
    organization_id: UUID | None,
    actor_user_id: UUID | None = None,
) -> None:
    """Low-level transaction-local RLS primitive; it does not authorize repositories."""
    state = _state(session)
    if state.authenticated_user_id is not None and actor_user_id != state.authenticated_user_id:
        raise PermissionError("transaction actor mismatch")
    if state.authenticated_organization_id is not None and organization_id not in (
        None,
        state.authenticated_organization_id,
    ):
        raise TenantResourceNotFoundError("resource not found")
    session.execute(
        text(
            "SELECT set_config('openvietgis.organization_id', :organization, true), "
            "set_config('openvietgis.actor_user_id', :actor, true)"
        ),
        {
            "organization": str(organization_id) if organization_id else "",
            "actor": str(actor_user_id) if actor_user_id else "",
        },
    )
    # Raw context changes must never preserve an earlier repository authorization.
    state = _state(session)
    state.organization_id = organization_id
    state.actor_user_id = actor_user_id
    state.member_verified = False
    state.invitation_id = None


def bind_authenticated_actor(session: Session, actor: Actor) -> None:
    """Pin the authenticated human identity for the request transaction."""
    actor_id = _human_id(actor)
    state = _state(session)
    if state.authenticated_service_principal_id is not None:
        raise PermissionError("transaction actor mismatch")
    if state.authenticated_user_id not in (None, actor_id):
        raise PermissionError("transaction actor mismatch")
    set_request_context(session, organization_id=None, actor_user_id=actor_id)
    state.authenticated_user_id = actor_id


def prepare_service_credential_lookup(session: Session, organization_id: UUID) -> None:
    """Bind only the caller-selected tenant before a bearer credential is verified."""
    state = _state(session)
    if (
        state.authenticated_user_id is not None
        or state.authenticated_service_principal_id is not None
    ):
        raise PermissionError("transaction actor already authenticated")
    set_request_context(session, organization_id=organization_id, actor_user_id=None)


def bind_authenticated_service_actor(
    session: Session,
    actor: Actor,
    *,
    organization_id: UUID,
    credential_id: UUID,
) -> None:
    """Pin a verified service credential to exactly one tenant for this request."""
    if actor.actor_type != "service_principal" or actor.actor_id is None:
        raise PermissionError("service principal actor required")
    state = _state(session)
    if state.authenticated_user_id is not None:
        raise PermissionError("transaction actor mismatch")
    if state.authenticated_service_principal_id not in (None, actor.actor_id):
        raise PermissionError("transaction actor mismatch")
    if state.authenticated_credential_id not in (None, credential_id):
        raise PermissionError("transaction credential mismatch")
    if state.authenticated_organization_id not in (None, organization_id):
        raise TenantResourceNotFoundError("resource not found")
    if state.organization_id != organization_id or state.actor_user_id is not None:
        set_request_context(session, organization_id=organization_id, actor_user_id=None)
    state.authenticated_service_principal_id = actor.actor_id
    state.authenticated_credential_id = credential_id
    state.authenticated_organization_id = organization_id


def _human_id(actor: Actor) -> UUID:
    if actor.actor_type != "human" or actor.actor_id is None:
        raise PermissionError("P1 repository requires human actor")
    return actor.actor_id


def _validate_target(
    session: Session,
    context: TenantContext,
    organization_id: UUID,
) -> tuple[_TransactionScope, UUID]:
    if context.organization_id != organization_id:
        raise TenantResourceNotFoundError("resource not found")
    actor_id = _human_id(context.actor)
    state = _state(session)
    if state.authenticated_user_id not in (None, actor_id):
        raise PermissionError("transaction actor mismatch")
    if state.authenticated_user_id is not None and state.authenticated_organization_id not in (
        None,
        organization_id,
    ):
        raise TenantResourceNotFoundError("resource not found")
    return state, actor_id


def prepare_self_membership_lookup(session: Session, actor: Actor) -> None:
    """Discovery is actor-only; no tenant setting is needed to read own memberships."""
    actor_id = _human_id(actor)
    state = _state(session)
    if state.authenticated_user_id not in (None, actor_id):
        raise PermissionError("transaction actor mismatch")
    if state.organization_id is not None and state.authenticated_user_id is not None:
        # A second membership check within an already authorized request keeps
        # the same actor/org context. It must not clear the tenant pin.
        if state.actor_user_id != actor_id:
            raise PermissionError("transaction actor mismatch")
        return
    if state.actor_user_id != actor_id or state.organization_id is not None:
        set_request_context(session, organization_id=None, actor_user_id=actor_id)


def confirm_member_context(session: Session, context: AuthorizationContext) -> None:
    """Called only after the live active membership has been resolved."""
    state, actor_id = _validate_target(session, context, context.organization_id)
    if state.organization_id != context.organization_id or state.actor_user_id != actor_id:
        set_request_context(
            session, organization_id=context.organization_id, actor_user_id=actor_id
        )
    if state.authenticated_user_id is not None:
        state.authenticated_organization_id = context.organization_id
    state.member_verified = True
    state.invitation_id = None


def require_service_audit_context(
    session: Session,
    actor: Actor,
    organization_id: UUID,
) -> None:
    """Audit only a service principal bound to this transaction and tenant."""
    state = _state(session)
    if actor.actor_type != "service_principal" or state.authenticated_credential_id is None:
        raise PermissionError("authenticated service credential required")
    require_member_context(
        session,
        AuthorizationContext(
            actor, organization_id, credential_id=state.authenticated_credential_id
        ),
        organization_id,
    )


def require_member_context(
    session: Session,
    context: AuthorizationContext,
    organization_id: UUID,
) -> None:
    """Authorize a protected repository call for a verified human or service actor."""
    if not isinstance(context, AuthorizationContext):
        raise PermissionError("authorization context required")
    if context.actor.actor_type == "service_principal":
        actor_id = context.actor.actor_id
        credential_id = context.credential_id
        state = _state(session)
        if actor_id is None or credential_id is None:
            raise PermissionError("service credential context required")
        if context.organization_id != organization_id:
            raise TenantResourceNotFoundError("resource not found")
        if (
            state.authenticated_service_principal_id != actor_id
            or state.authenticated_credential_id != credential_id
            or state.authenticated_organization_id != organization_id
        ):
            raise PermissionError("service actor is not authenticated for tenant")
        if state.organization_id != organization_id or state.actor_user_id is not None:
            set_request_context(session, organization_id=organization_id, actor_user_id=None)
        state.member_verified = False
        state.invitation_id = None
        return
    state, actor_id = _validate_target(session, context, organization_id)
    if (
        state.organization_id == organization_id
        and state.actor_user_id == actor_id
        and state.member_verified
    ):
        return
    # Standalone domain calls (and future job restoration) cannot merely set
    # a tenant ID: re-resolve current membership before binding the scope.
    prepare_self_membership_lookup(session, context.actor)
    active = session.execute(
        text(
            "SELECT id FROM org.organization_memberships "
            "WHERE organization_id = :organization_id AND user_id = :user_id "
            "AND status = 'active'"
        ),
        {"organization_id": organization_id, "user_id": actor_id},
    ).scalar_one_or_none()
    if active is None:
        raise TenantResourceNotFoundError("organization not found")
    confirm_member_context(session, context)


def require_invitation_context(
    session: Session,
    context: InvitationAcceptanceContext,
    organization_id: UUID,
    *,
    invitation_id: UUID | None = None,
    require_verified: bool = False,
) -> None:
    """Only exact-ID invitation preflight/verified acceptance may cross pre-membership."""
    if invitation_id is not None and context.invitation_id != invitation_id:
        raise TenantResourceNotFoundError("invitation not found")
    if require_verified and not context.verified:
        raise PermissionError("verified invitation acceptance required")
    state, actor_id = _validate_target(session, context, organization_id)
    if state.authenticated_user_id is not None and state.invitation_id not in (
        None,
        context.invitation_id,
    ):
        raise TenantResourceNotFoundError("invitation not found")
    if state.organization_id != organization_id or state.actor_user_id != actor_id:
        set_request_context(session, organization_id=organization_id, actor_user_id=actor_id)
    if state.authenticated_user_id is not None:
        state.authenticated_organization_id = organization_id
    state.invitation_id = context.invitation_id
    # An invitation context does not validate ordinary tenant membership.
    state.member_verified = False


def bind_new_organization_context(session: Session, context: AuthorizationContext) -> None:
    """Narrow creation path after a server-generated organization is inserted."""
    state, actor_id = _validate_target(session, context, context.organization_id)
    set_request_context(session, organization_id=context.organization_id, actor_user_id=actor_id)
    if state.authenticated_user_id is not None:
        state.authenticated_organization_id = context.organization_id
    state.member_verified = False


def clear_request_context(session: Session) -> None:
    set_request_context(session, organization_id=None, actor_user_id=None)