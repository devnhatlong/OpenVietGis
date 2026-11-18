from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from openvietgis_api.domains.audit.ports import AuditRepository
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.authorization.ports import ResourceGrantRepository
from openvietgis_api.domains.identity.domain import IdentityLink, User, UserStatus
from openvietgis_api.domains.identity.ports import IdentityRepository
from openvietgis_api.domains.tenancy.domain import (
    ActorType,
    Invitation,
    InvitationStatus,
    InvitationTargetKind,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
)
from openvietgis_api.domains.tenancy.ports import InstallationStateReader, TenancyRepository
from openvietgis_api.domains.tenancy.service import (
    InvalidInvitationError,
    InvalidLifecycleTransitionError,
    InvitationService,
    InvitationTargetMismatchError,
    LastOwnerError,
    OwnerRequiredError,
    TenancyService,
)
from openvietgis_api.security.secrets import digest_secret, generate_secret, safe_prefix


def _membership(org: UUID, user: UUID, role: MembershipRole) -> OrganizationMembership:
    now = datetime.now(UTC)
    return OrganizationMembership(
        id=uuid4(),
        organization_id=org,
        user_id=user,
        role=role,
        status=MembershipStatus.ACTIVE,
        created_at=now,
        activated_at=now,
        suspended_at=None,
        revoked_at=None,
    )


class World:
    def __init__(self) -> None:
        self.org_id = uuid4()
        now = datetime.now(UTC)
        self.owner = _membership(self.org_id, uuid4(), MembershipRole.OWNER)
        self.admin = _membership(self.org_id, uuid4(), MembershipRole.ADMIN)
        self.member = _membership(self.org_id, uuid4(), MembershipRole.MEMBER)
        self.repo = Mock(spec=TenancyRepository)
        self.organization = Organization(
            id=self.org_id,
            name="Test organization",
            slug="test-organization",
            status=OrganizationStatus.ACTIVE,
            created_by_actor_type=ActorType.HUMAN,
            created_by_actor_id=self.owner.user_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.repo.get_organization.return_value = self.organization
        members = {m.user_id: m for m in (self.owner, self.admin, self.member)}
        self.repo.get_membership_for_user.side_effect = (
            lambda *, organization_id, user_id, for_update: members.get(user_id)
        )
        self.repo.get_membership.side_effect = (
            lambda *, organization_id, membership_id, for_update: next(
                (m for m in members.values() if m.id == membership_id), None
            )
        )
        self.audit = Mock(spec=AuditRepository)
        self.identity = Mock(spec=IdentityRepository)
        self.grants = Mock(spec=ResourceGrantRepository)
        self.tenancy = TenancyService(
            self.repo, Mock(spec=InstallationStateReader), self.audit
        )
        self.invites = InvitationService(
            self.repo, self.identity, self.grants, self.audit
        )
        self.secret = generate_secret("inv", bytes_of_entropy=32)
        self.now = now

    def actor(self, membership: OrganizationMembership) -> Actor:
        return Actor(actor_type="human", actor_id=membership.user_id, display_name="User")

    def invite(
        self, target: OrganizationMembership, role: MembershipRole,
    ) -> Invitation:
        return Invitation(
            id=uuid4(),
            organization_id=self.org_id,
            status=InvitationStatus.PENDING,
            target_kind=InvitationTargetKind.USER,
            target_email_normalized=None,
            target_user_id=target.user_id,
            target_issuer=None,
            target_subject=None,
            organization_role=role,
            resource_scope_kind=None,
            resource_workspace_id=None,
            resource_project_id=None,
            resource_role=None,
            token_hash=digest_secret(self.secret),
            token_prefix=safe_prefix(self.secret),
            expires_at=self.now + timedelta(hours=1),
            created_at=self.now,
            created_by_actor_type=ActorType.HUMAN,
            created_by_actor_id=self.owner.user_id,
            accepted_at=None,
            accepted_by_user_id=None,
            revoked_at=None,
        )

    def prepare_accept(self, target: OrganizationMembership, invitation: Invitation) -> None:
        self.repo.get_invitation.return_value = invitation
        self.identity.get_user.return_value = User(
            id=target.user_id,
            display_name="User",
            email_snapshot=None,
            status=UserStatus.ACTIVE,
            created_at=self.now,
            updated_at=self.now,
        )

    def accept(
        self, target: OrganizationMembership, invitation: Invitation,
        *, identity_link_id: UUID | None = None,
    ):
        return self.invites.accept(
            actor=self.actor(target),
            organization_id=self.org_id,
            user_id=target.user_id,
            invitation_id=invitation.id,
            secret=self.secret,
            identity_link_id=identity_link_id,
            now=self.now,
        )

    def assert_no_writes(self) -> None:
        self.repo.update_membership.assert_not_called()
        self.repo.create_membership.assert_not_called()
        self.repo.update_invitation.assert_not_called()
        self.grants.create.assert_not_called()
        self.audit.append.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"role": MembershipRole.OWNER},
        {"status": MembershipStatus.REVOKED},
        {"status": MembershipStatus.SUSPENDED},
    ],
)
def test_admin_cannot_promote_self_or_revoke_owner(change) -> None:
    world = World()
    target = world.admin if "role" in change else world.owner
    with pytest.raises(OwnerRequiredError):
        world.tenancy.update_membership(
            actor=world.actor(world.admin),
            organization_id=world.org_id,
            membership_id=target.id,
            **change,
        )
    world.assert_no_writes()


def test_last_owner_downgrade_rejected_while_holding_organization_lock() -> None:
    world = World()
    world.repo.count_other_active_owners.return_value = 0
    with pytest.raises(LastOwnerError):
        world.tenancy.update_membership(
            actor=world.actor(world.owner),
            organization_id=world.org_id,
            membership_id=world.owner.id,
            role=MembershipRole.ADMIN,
        )
    assert world.repo.method_calls[0].args == (world.org_id,)
    assert world.repo.method_calls[0].kwargs == {"for_update": True}
    world.assert_no_writes()


def test_owner_transfer_promotes_before_demoting_and_audits_once() -> None:
    world = World()
    demoted, promoted = world.tenancy.transfer_ownership(
        actor=world.actor(world.owner),
        organization_id=world.org_id,
        target_membership_id=world.member.id,
        now=world.now,
    )
    assert demoted.role == MembershipRole.ADMIN
    assert promoted.role == MembershipRole.OWNER
    assert [call.args[0].role for call in world.repo.update_membership.call_args_list] == [
        MembershipRole.OWNER, MembershipRole.ADMIN,
    ]
    world.audit.append.assert_called_once()
    event = world.audit.append.call_args.args[0]
    assert event.actor_id == world.owner.user_id
    assert event.organization_id == world.org_id
    assert event.action == "organization.owner.transfer"


def test_member_and_disabled_admin_cannot_update_org_settings() -> None:
    world = World()
    with pytest.raises(OwnerRequiredError):
        world.tenancy.update_organization(
            actor=world.actor(world.member),
            organization_id=world.org_id,
            name="Unauthorized",
        )
    world.repo.get_membership_for_user.side_effect = None
    world.repo.get_membership_for_user.return_value = replace(
        world.admin, status=MembershipStatus.SUSPENDED
    )
    with pytest.raises(OwnerRequiredError):
        world.tenancy.update_organization(
            actor=world.actor(world.admin),
            organization_id=world.org_id,
            name="Unauthorized",
        )
    world.repo.update_organization.assert_not_called()
    world.audit.append.assert_not_called()


@pytest.mark.parametrize("status", [OrganizationStatus.SUSPENDED, OrganizationStatus.DELETED])
def test_inactive_organization_rejects_invite_acceptance_and_normal_mutation(status) -> None:
    world = World()
    world.repo.get_organization.return_value = replace(world.organization, status=status)
    invitation = world.invite(world.member, MembershipRole.MEMBER)
    world.prepare_accept(world.member, invitation)
    with pytest.raises(InvalidInvitationError):
        world.accept(world.member, invitation)
    with pytest.raises(InvalidLifecycleTransitionError):
        world.tenancy.create_workspace(
            actor=world.actor(world.owner),
            organization_id=world.org_id,
            name="Blocked workspace",
            slug="blocked-workspace",
        )
    world.repo.get_invitation.assert_not_called()
    world.repo.create_workspace.assert_not_called()
    world.assert_no_writes()


def test_admin_cannot_issue_owner_invitation() -> None:
    world = World()
    with pytest.raises(OwnerRequiredError):
        world.invites.issue(
            actor=world.actor(world.admin),
            organization_id=world.org_id,
            target_kind=InvitationTargetKind.USER,
            target_user_id=world.admin.user_id,
            organization_role=MembershipRole.OWNER,
            expires_at=world.now + timedelta(hours=1),
            now=world.now,
        )
    world.repo.create_invitation.assert_not_called()
    world.assert_no_writes()


def test_owner_invitation_cannot_be_revoked_by_admin() -> None:
    world = World()
    invitation = world.invite(world.member, MembershipRole.OWNER)
    world.repo.get_invitation.return_value = invitation
    with pytest.raises(OwnerRequiredError):
        world.invites.revoke(
            actor=world.actor(world.admin),
            organization_id=world.org_id,
            invitation_id=invitation.id,
            now=world.now,
        )
    world.assert_no_writes()


def test_invitation_cannot_downgrade_current_owner() -> None:
    world = World()
    invitation = world.invite(world.owner, MembershipRole.GUEST)
    world.prepare_accept(world.owner, invitation)
    with pytest.raises(InvalidInvitationError, match="downgrade"):
        world.accept(world.owner, invitation)
    world.assert_no_writes()


def test_stale_owner_invitation_requires_current_owner_authority() -> None:
    world = World()
    invitation = replace(
        world.invite(world.member, MembershipRole.OWNER),
        created_by_actor_id=world.admin.user_id,
    )
    world.prepare_accept(world.member, invitation)
    with pytest.raises(InvalidInvitationError, match="authority"):
        world.accept(world.member, invitation)
    world.assert_no_writes()


def test_acceptance_requires_same_authenticated_human_as_target_user() -> None:
    world = World()
    invitation = world.invite(world.member, MembershipRole.GUEST)
    world.prepare_accept(world.member, invitation)
    for actor in (
        world.actor(world.admin),
        Actor(actor_type="service_principal", actor_id=world.member.user_id, display_name="Bot"),
    ):
        with pytest.raises(InvitationTargetMismatchError):
            world.invites.accept(
                actor=actor, user_id=world.member.user_id, organization_id=world.org_id,
                invitation_id=invitation.id, secret=world.secret, now=world.now,
            )
    world.repo.get_invitation.assert_not_called()
    world.assert_no_writes()


def _identity_link(world: World, user_id: UUID, *, email: str, verified: bool) -> IdentityLink:
    return IdentityLink(
        id=uuid4(), user_id=user_id, issuer="https://issuer.example",
        subject="subject", email_snapshot=email, email_verified=verified,
        display_name_snapshot="User", created_at=world.now, last_login_at=world.now,
    )


def test_email_invitation_requires_current_verified_matching_identity_link() -> None:
    world = World()
    invitation = replace(
        world.invite(world.member, MembershipRole.MEMBER),
        target_kind=InvitationTargetKind.EMAIL,
        target_user_id=None,
        target_email_normalized="target@example.test",
    )
    world.prepare_accept(world.member, invitation)
    good = _identity_link(world, world.member.user_id, email="TARGET@example.test", verified=True)
    wrong = replace(good, id=uuid4(), email_snapshot="different@example.test")
    unverified = replace(good, id=uuid4(), email_verified=False)
    world.identity.list_identity_links.return_value = [good, wrong, unverified]
    for identity_link_id in (None, wrong.id, unverified.id):
        with pytest.raises(InvitationTargetMismatchError):
            world.accept(world.member, invitation, identity_link_id=identity_link_id)
    world.assert_no_writes()

    membership, grant = world.accept(world.member, invitation, identity_link_id=good.id)
    assert membership.status == MembershipStatus.ACTIVE
    assert grant is None
    assert world.repo.update_invitation.call_args.args[0].status == InvitationStatus.ACCEPTED
    world.audit.append.assert_called_once()
    event = world.audit.append.call_args.args[0]
    assert event.actor_id == world.member.user_id
    assert event.action == "invitation.accept"
    assert world.secret not in str(event.metadata)


def test_external_identity_invitation_matches_exact_current_issuer_subject() -> None:
    world = World()
    link = _identity_link(world, world.member.user_id, email="member@example.test", verified=True)
    invitation = replace(
        world.invite(world.member, MembershipRole.MEMBER),
        target_kind=InvitationTargetKind.EXTERNAL_IDENTITY,
        target_user_id=None,
        target_issuer=link.issuer + "/",
        target_subject=link.subject,
    )
    world.prepare_accept(world.member, invitation)
    world.identity.list_identity_links.return_value = [link]
    with pytest.raises(InvitationTargetMismatchError):
        world.accept(world.member, invitation, identity_link_id=link.id)
    world.assert_no_writes()
