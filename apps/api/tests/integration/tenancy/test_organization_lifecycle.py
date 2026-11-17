from __future__ import annotations

from dataclasses import replace

import pytest

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlEffectivePermissionProvider,
)
from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.tenancy.domain import MembershipRole, OrganizationStatus
from openvietgis_api.domains.tenancy.service import OwnerRequiredError, TenancyService
from tests.fixtures.identity_tenancy import seed_access_world


def test_organization_lifecycle_is_owner_only_and_suspension_blocks_normal_access(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    session = get_session_factory()()
    try:
        repository = SqlTenancyRepository(session)
        member = repository.get_membership(
            organization_id=world.organization_id,
            membership_id=world.member_membership_id,
            for_update=True,
        )
        assert member is not None
        repository.update_membership(replace(member, role=MembershipRole.ADMIN))
        session.commit()
    finally:
        session.close()

    owner = Actor(actor_type="human", actor_id=world.owner_user_id, display_name="Owner")
    admin = Actor(actor_type="human", actor_id=world.member_user_id, display_name="Admin")

    session = get_session_factory()()
    try:
        service = TenancyService(
            SqlTenancyRepository(session),
            SqlPlatformRepository(session),
            SqlAuditRepository(session),
        )
        with pytest.raises(OwnerRequiredError):
            service.update_organization(
                actor=admin,
                organization_id=world.organization_id,
                status=OrganizationStatus.SUSPENDED,
            )
        session.rollback()
    finally:
        session.close()

    session = get_session_factory()()
    try:
        TenancyService(
            SqlTenancyRepository(session),
            SqlPlatformRepository(session),
            SqlAuditRepository(session),
        ).update_organization(
            actor=owner,
            organization_id=world.organization_id,
            status=OrganizationStatus.SUSPENDED,
        )
        session.commit()
    finally:
        session.close()

    session = get_session_factory()()
    try:
        context = AuthorizationContext(
            actor=admin,
            organization_id=world.organization_id,
            project_id=world.project_id,
        )
        permissions = SqlEffectivePermissionProvider(session).resolve(context)
        assert Permission.PROJECT_READ not in permissions
        assert permissions == frozenset()
        session.rollback()
    finally:
        session.close()

    session = get_session_factory()()
    try:
        restored = TenancyService(
            SqlTenancyRepository(session),
            SqlPlatformRepository(session),
            SqlAuditRepository(session),
        ).update_organization(
            actor=owner,
            organization_id=world.organization_id,
            status=OrganizationStatus.ACTIVE,
        )
        assert restored.status == OrganizationStatus.ACTIVE
        session.commit()
    finally:
        session.close()
