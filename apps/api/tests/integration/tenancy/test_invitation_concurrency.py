from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import SqlResourceGrantRepository
from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.identity_repository import SqlIdentityRepository
from openvietgis_api.adapters.persistence.rls import set_request_context
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.tenancy.domain import InvitationTargetKind, MembershipRole
from openvietgis_api.domains.tenancy.service import InvalidInvitationError, InvitationService
from tests.fixtures.db_admin import get_admin_session_factory
from tests.fixtures.identity_tenancy import seed_access_world


def _service(session):
    return InvitationService(
        SqlTenancyRepository(session),
        SqlIdentityRepository(session),
        SqlResourceGrantRepository(session),
        SqlAuditRepository(session),
    )


def test_concurrent_double_accept_commits_exactly_once(migrated_database: None) -> None:
    world = seed_access_world()
    now = datetime.now(UTC)
    owner = Actor(actor_type="human", actor_id=world.owner_user_id, display_name="Owner")
    member = Actor(actor_type="human", actor_id=world.member_user_id, display_name="Member")

    setup = get_admin_session_factory()()
    try:
        issued = _service(setup).issue(
            actor=owner,
            organization_id=world.organization_id,
            target_kind=InvitationTargetKind.USER,
            target_user_id=world.member_user_id,
            organization_role=MembershipRole.MEMBER,
            expires_at=now + timedelta(hours=1),
            now=now,
        )
        setup.commit()
    finally:
        setup.close()

    start = Barrier(2)

    def accept_once() -> str:
        session = get_session_factory()()
        try:
            set_request_context(
                session, organization_id=world.organization_id, actor_user_id=world.member_user_id
            )
            start.wait(timeout=10)
            service = _service(session)
            try:
                service.accept(
                    actor=member,
                    user_id=world.member_user_id,
                    organization_id=world.organization_id,
                    invitation_id=issued.invitation.id,
                    secret=issued.secret,
                    now=now + timedelta(seconds=1),
                )
            except InvalidInvitationError:
                session.rollback()
                return "rejected"
            session.commit()
            return "accepted"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept_once(), range(2)))

    assert sorted(results) == ["accepted", "rejected"]
