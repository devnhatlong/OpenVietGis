from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import SqlResourceGrantRepository
from openvietgis_api.adapters.persistence.identity_repository import SqlIdentityRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.tenancy.domain import (
    InvitationStatus,
    InvitationTargetKind,
    MembershipRole,
    ResourceRole,
    ResourceScopeKind,
)
from openvietgis_api.domains.tenancy.service import (
    InvalidInvitationError,
    InvitationService,
    InvitationTargetMismatchError,
)
from tests.fixtures.db_admin import get_admin_session_factory
from tests.fixtures.identity_tenancy import seed_access_world


def _service(session):
    return InvitationService(
        SqlTenancyRepository(session),
        SqlIdentityRepository(session),
        SqlResourceGrantRepository(session),
        SqlAuditRepository(session),
    )


def test_invitation_recipient_binding_accept_once_and_optional_grant(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    session = get_admin_session_factory()()
    owner = Actor(actor_type="human", actor_id=world.owner_user_id, display_name="Owner")
    wrong = Actor(actor_type="human", actor_id=world.wrong_user_id, display_name="Wrong")
    member = Actor(actor_type="human", actor_id=world.member_user_id, display_name="Member")
    now = datetime.now(UTC)
    try:
        service = _service(session)
        issued = service.issue(
            actor=owner,
            organization_id=world.organization_id,
            target_kind=InvitationTargetKind.EMAIL,
            target_email="member-a@example.test",
            organization_role=MembershipRole.MEMBER,
            resource_scope_kind=ResourceScopeKind.PROJECT,
            resource_project_id=world.project_id,
            resource_role=ResourceRole.VIEWER,
            expires_at=now + timedelta(hours=1),
            now=now,
        )

        with pytest.raises(InvitationTargetMismatchError):
            service.accept(
                actor=wrong,
                user_id=world.wrong_user_id,
                identity_link_id=SqlIdentityRepository(session).list_identity_links(world.wrong_user_id)[0].id,
                organization_id=world.organization_id,
                invitation_id=issued.invitation.id,
                secret=issued.secret,
                now=now + timedelta(seconds=1),
            )

        membership, grant = service.accept(
            actor=member,
            user_id=world.member_user_id,
            identity_link_id=SqlIdentityRepository(session).list_identity_links(world.member_user_id)[0].id,
            organization_id=world.organization_id,
            invitation_id=issued.invitation.id,
            secret=issued.secret,
            now=now + timedelta(seconds=2),
        )
        assert membership.status.value == "active"
        assert grant is not None
        assert grant.project_id == world.project_id
        assert grant.role == ResourceRole.VIEWER

        with pytest.raises(InvalidInvitationError):
            service.accept(
                actor=member,
                user_id=world.member_user_id,
                identity_link_id=SqlIdentityRepository(session).list_identity_links(world.member_user_id)[0].id,
                organization_id=world.organization_id,
                invitation_id=issued.invitation.id,
                secret=issued.secret,
                now=now + timedelta(seconds=3),
            )
        session.commit()

        stored = SqlTenancyRepository(session).get_invitation(
            organization_id=world.organization_id,
            invitation_id=issued.invitation.id,
        )
        assert stored is not None
        assert stored.status == InvitationStatus.ACCEPTED
    finally:
        session.close()


def test_invitation_expiry_and_revocation_are_rejected(migrated_database: None) -> None:
    world = seed_access_world()
    session = get_admin_session_factory()()
    owner = Actor(actor_type="human", actor_id=world.owner_user_id, display_name="Owner")
    member = Actor(actor_type="human", actor_id=world.member_user_id, display_name="Member")
    now = datetime.now(UTC)
    try:
        service = _service(session)
        expiring = service.issue(
            actor=owner,
            organization_id=world.organization_id,
            target_kind=InvitationTargetKind.USER,
            target_user_id=world.member_user_id,
            organization_role=MembershipRole.MEMBER,
            expires_at=now + timedelta(seconds=1),
            now=now,
        )
        with pytest.raises(InvalidInvitationError, match="expired"):
            service.accept(
                actor=member,
                user_id=world.member_user_id,
                organization_id=world.organization_id,
                invitation_id=expiring.invitation.id,
                secret=expiring.secret,
                now=now + timedelta(seconds=2),
            )

        revoked_issue = service.issue(
            actor=owner,
            organization_id=world.organization_id,
            target_kind=InvitationTargetKind.USER,
            target_user_id=world.member_user_id,
            organization_role=MembershipRole.MEMBER,
            expires_at=now + timedelta(hours=1),
            now=now,
        )
        revoked = service.revoke(
            actor=owner,
            organization_id=world.organization_id,
            invitation_id=revoked_issue.invitation.id,
            now=now + timedelta(seconds=2),
        )
        assert revoked.status == InvitationStatus.REVOKED
        with pytest.raises(InvalidInvitationError):
            service.accept(
                actor=member,
                user_id=world.member_user_id,
                organization_id=world.organization_id,
                invitation_id=revoked_issue.invitation.id,
                secret=revoked_issue.secret,
                now=now + timedelta(seconds=3),
            )
        session.commit()
    finally:
        session.close()
