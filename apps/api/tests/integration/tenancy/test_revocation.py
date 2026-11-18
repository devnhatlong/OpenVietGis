from __future__ import annotations

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlEffectivePermissionProvider,
    SqlResourceGrantRepository,
)
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import GrantService
from openvietgis_api.domains.tenancy.domain import (
    MembershipStatus,
    ResourceRole,
    ResourceScopeKind,
)
from openvietgis_api.domains.tenancy.service import TenancyService
from tests.fixtures.db_admin import get_admin_session_factory
from tests.fixtures.identity_tenancy import seed_access_world


def test_grant_and_membership_revocation_apply_on_next_authorization(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    owner = Actor(actor_type="human", actor_id=world.owner_user_id, display_name="Owner")
    member = Actor(actor_type="human", actor_id=world.member_user_id, display_name="Member")
    context = AuthorizationContext(
        actor=member,
        organization_id=world.organization_id,
        project_id=world.project_id,
    )

    session = get_admin_session_factory()()
    try:
        tenancy = SqlTenancyRepository(session)
        grants = SqlResourceGrantRepository(session)
        audit = SqlAuditRepository(session)
        grant_service = GrantService(grants, tenancy, audit)

        workspace_grant = grant_service.create_membership_grant(
            actor=owner,
            organization_id=world.organization_id,
            membership_id=world.member_membership_id,
            scope_kind=ResourceScopeKind.WORKSPACE,
            workspace_id=world.workspace_a_id,
            role=ResourceRole.VIEWER,
        )
        session.commit()
    finally:
        session.close()

    session = get_admin_session_factory()()
    try:
        provider = SqlEffectivePermissionProvider(session)
        assert Permission.PROJECT_READ in provider.resolve(context)
        session.rollback()
    finally:
        session.close()

    session = get_admin_session_factory()()
    try:
        GrantService(
            SqlResourceGrantRepository(session),
            SqlTenancyRepository(session),
            SqlAuditRepository(session),
        ).revoke(
            actor=owner,
            organization_id=world.organization_id,
            grant_id=workspace_grant.id,
        )
        session.commit()
    finally:
        session.close()

    session = get_admin_session_factory()()
    try:
        provider = SqlEffectivePermissionProvider(session)
        assert Permission.PROJECT_READ not in provider.resolve(context)
        session.rollback()
    finally:
        session.close()

    session = get_admin_session_factory()()
    try:
        GrantService(
            SqlResourceGrantRepository(session),
            SqlTenancyRepository(session),
            SqlAuditRepository(session),
        ).create_membership_grant(
            actor=owner,
            organization_id=world.organization_id,
            membership_id=world.member_membership_id,
            scope_kind=ResourceScopeKind.PROJECT,
            project_id=world.project_id,
            role=ResourceRole.VIEWER,
        )
        session.commit()
    finally:
        session.close()

    session = get_admin_session_factory()()
    try:
        assert Permission.PROJECT_READ in SqlEffectivePermissionProvider(session).resolve(context)
        session.rollback()
    finally:
        session.close()

    session = get_admin_session_factory()()
    try:
        TenancyService(
            SqlTenancyRepository(session),
            SqlPlatformRepository(session),
            SqlAuditRepository(session),
        ).update_membership(
            actor=owner,
            organization_id=world.organization_id,
            membership_id=world.member_membership_id,
            status=MembershipStatus.REVOKED,
        )
        session.commit()
    finally:
        session.close()

    session = get_admin_session_factory()()
    try:
        permissions = SqlEffectivePermissionProvider(session).resolve(context)
        assert Permission.PROJECT_READ not in permissions
    finally:
        session.rollback()
        session.close()
