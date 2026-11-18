from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.tenancy.domain import MembershipRole
from openvietgis_api.domains.tenancy.service import LastOwnerError, TenancyService
from tests.fixtures.db_admin import get_admin_session_factory
from tests.fixtures.identity_tenancy import seed_access_world


def _service(session):
    return TenancyService(
        SqlTenancyRepository(session),
        SqlPlatformRepository(session),
        SqlAuditRepository(session),
    )


def test_concurrent_owner_downgrades_never_leave_zero_active_owners(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    setup = get_admin_session_factory()()
    try:
        member = SqlTenancyRepository(setup).get_membership(
            organization_id=world.organization_id,
            membership_id=world.member_membership_id,
            for_update=True,
        )
        assert member is not None
        from dataclasses import replace

        SqlTenancyRepository(setup).update_membership(
            replace(member, role=MembershipRole.OWNER)
        )
        setup.commit()
    finally:
        setup.close()

    def downgrade(user_id, membership_id, name: str) -> str:
        session = get_admin_session_factory()()
        try:
            service = _service(session)
            actor = Actor(actor_type="human", actor_id=user_id, display_name=name)
            try:
                service.update_membership(
                    actor=actor,
                    organization_id=world.organization_id,
                    membership_id=membership_id,
                    role=MembershipRole.ADMIN,
                )
            except LastOwnerError:
                session.rollback()
                return "rejected"
            session.commit()
            return "updated"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            downgrade,
            world.owner_user_id,
            world.owner_membership_id,
            "Owner",
        )
        second = pool.submit(
            downgrade,
            world.member_user_id,
            world.member_membership_id,
            "Member Owner",
        )
        results = [first.result(), second.result()]

    assert sorted(results) == ["rejected", "updated"]
