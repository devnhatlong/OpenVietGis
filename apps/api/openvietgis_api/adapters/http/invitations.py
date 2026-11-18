from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    get_db_session,
    require_csrf,
)
from openvietgis_api.adapters.http.tenant_access import human_actor_id, require_human_permission
from openvietgis_api.adapters.http.tenant_serialization import (
    serialize_grant,
    serialize_membership,
)
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlResourceGrantRepository,
)
from openvietgis_api.adapters.persistence.identity_repository import SqlIdentityRepository
from openvietgis_api.adapters.persistence.rls import set_request_context
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import ORGANIZATION_ROLE_PERMISSIONS
from openvietgis_api.domains.authorization.service import AuthorizationDeniedError
from openvietgis_api.domains.tenancy.domain import (
    InvitationTargetKind,
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    ResourceRole,
    ResourceScopeKind,
)
from openvietgis_api.domains.tenancy.service import (
    InvalidInvitationError,
    InvitationNotFoundError,
    InvitationService,
    InvitationTargetMismatchError,
)

router = APIRouter(tags=["invitations"])


class EmailTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["email"]
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+$")


class UserTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["user"]
    user_id: UUID


class ExternalIdentityTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["external_identity"]
    issuer: str = Field(min_length=1, max_length=2048)
    subject: str = Field(min_length=1, max_length=1024)


class InvitationResourceGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_kind: ResourceScopeKind
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    role: ResourceRole


class CreateInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Annotated[
        EmailTarget | UserTarget | ExternalIdentityTarget, Field(discriminator="kind")
    ]
    organization_role: MembershipRole
    resource_grant: InvitationResourceGrant | None = None
    expires_at: AwareDatetime


class AcceptInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    invitation_id: UUID
    secret: str = Field(min_length=32, max_length=512, repr=False)


def _service(session: Session) -> InvitationService:
    return InvitationService(
        SqlTenancyRepository(session),
        SqlIdentityRepository(session),
        SqlResourceGrantRepository(session),
        SqlAuditRepository(session),
    )


@router.post("/organizations/{organization_id}/invitations", status_code=201)
def create_invitation(
    organization_id: UUID,
    payload: CreateInvitationRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    member = require_human_permission(
        session, authentication, organization_id, Permission.INVITATION_MANAGE, lock=True
    )
    if (
        payload.organization_role == MembershipRole.OWNER
        and Permission.ORGANIZATION_OWNER_TRANSFER not in ORGANIZATION_ROLE_PERMISSIONS[
            member.role
        ]
    ):
        raise AuthorizationDeniedError("Owner authority is required to invite an Owner")
    target = payload.target
    resource = payload.resource_grant
    issued = _service(session).issue(
        actor=authentication.actor,
        organization_id=organization_id,
        target_kind=InvitationTargetKind(target.kind),
        organization_role=payload.organization_role,
        expires_at=payload.expires_at,
        target_email=target.email if isinstance(target, EmailTarget) else None,
        target_user_id=target.user_id if isinstance(target, UserTarget) else None,
        target_issuer=target.issuer if isinstance(target, ExternalIdentityTarget) else None,
        target_subject=target.subject if isinstance(target, ExternalIdentityTarget) else None,
        resource_scope_kind=resource.scope_kind if resource else None,
        resource_workspace_id=resource.workspace_id if resource else None,
        resource_project_id=resource.project_id if resource else None,
        resource_role=resource.role if resource else None,
    )
    return {
        "id": issued.invitation.id,
        "organization_id": issued.invitation.organization_id,
        "status": issued.invitation.status.value,
        "secret": issued.secret,
    }


@router.post(
    "/organizations/{organization_id}/invitations/{invitation_id}/revoke", status_code=204
)
def revoke_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> Response:
    require_human_permission(
        session, authentication, organization_id, Permission.INVITATION_MANAGE, lock=True
    )
    _service(session).revoke(
        actor=authentication.actor,
        organization_id=organization_id,
        invitation_id=invitation_id,
    )
    return Response(status_code=204)


@router.post("/invitations/accept")
def accept_invitation(
    payload: AcceptInvitationRequest,
    authentication: Annotated[AuthenticatedRequest, Depends(require_csrf)],
    session: Annotated[Session, Depends(get_db_session, scope="function")],
) -> dict[str, object]:
    user_id = human_actor_id(authentication)
    # This is the intentional pre-membership exception. The domain service must verify the
    # one-time secret AND the intended identity before granting any membership.
    set_request_context(
        session, organization_id=payload.organization_id, actor_user_id=user_id
    )
    repository = SqlTenancyRepository(session)
    organization = repository.get_organization(payload.organization_id, for_update=True)
    if organization is None or organization.status != OrganizationStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="invalid invitation")
    existing = repository.get_membership_for_user(
        organization_id=payload.organization_id,
        user_id=user_id,
        for_update=True,
    )
    try:
        membership, grant = _service(session).accept(
            actor=authentication.actor,
            user_id=user_id,
            organization_id=payload.organization_id,
            invitation_id=payload.invitation_id,
            secret=payload.secret,
        )
        if (
            existing is not None
            and existing.role == MembershipRole.OWNER
            and existing.status == MembershipStatus.ACTIVE
            and membership.role != MembershipRole.OWNER
        ):
            # No invitation can demote an active Owner. Raising rolls back the
            # invitation/membership/grant/audit transaction as a single unit.
            raise InvalidInvitationError("invitation cannot change existing Owner authority")
    except (
        InvitationNotFoundError,
        InvalidInvitationError,
        InvitationTargetMismatchError,
    ):
        # The same response covers absent, wrong-tenant, expired, revoked, reused and
        # wrong-recipient invitations. Do not expose recipient or secret information.
        raise HTTPException(status_code=400, detail="invalid invitation") from None
    return {
        "membership": serialize_membership(membership),
        "grant": serialize_grant(grant) if grant is not None else None,
    }
