from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.tenancy.domain import ProjectStatus, WorkspaceStatus
from openvietgis_api.domains.tenancy.service import (
    CrossOrganizationWorkspaceError,
    TenancyService,
    WorkspaceHasActiveProjectsError,
)
from tests.fixtures.db_admin import get_admin_engine


def _seed_orgs_and_actor() -> tuple[Actor, object, object]:
    user_id = uuid4()
    org_a, org_b = uuid4(), uuid4()
    with get_admin_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                VALUES (:id, 'Workspace Owner', 'active', now(), now())
                """
            ),
            {"id": user_id},
        )
        for org_id, slug in ((org_a, f"a-{org_a.hex}"), (org_b, f"b-{org_b.hex}")):
            connection.execute(
                text(
                    """
                    INSERT INTO org.organizations (
                        id, name, slug, status, created_by_actor_type,
                        created_by_actor_id, created_at, updated_at
                    )
                    VALUES (:id, 'Org', :slug, 'active', 'human', :user_id, now(), now())
                    """
                ),
                {"id": org_id, "slug": slug, "user_id": user_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO org.organization_memberships (
                        id, organization_id, user_id, role, status, created_at, activated_at
                    )
                    VALUES (:id, :org_id, :user_id, 'owner', 'active', now(), now())
                    """
                ),
                {"id": uuid4(), "org_id": org_id, "user_id": user_id},
            )
    return (
        Actor(actor_type="human", actor_id=user_id, display_name="Workspace Owner"),
        org_a,
        org_b,
    )


def test_workspace_project_lifecycle_and_same_org_moves(migrated_database: None) -> None:
    actor, org_a, _ = _seed_orgs_and_actor()
    session = get_session_factory()()
    try:
        service = TenancyService(
            SqlTenancyRepository(session),
            SqlPlatformRepository(session),
            SqlAuditRepository(session),
        )
        first = service.create_workspace(
            actor=actor,
            organization_id=org_a,
            name="Workspace A1",
            slug=f"a1-{uuid4().hex}",
        )
        second = service.create_workspace(
            actor=actor,
            organization_id=org_a,
            name="Workspace A2",
            slug=f"a2-{uuid4().hex}",
        )
        project = service.create_project(
            actor=actor,
            organization_id=org_a,
            workspace_id=first.id,
            name="Project P1",
            slug=f"p1-{uuid4().hex}",
        )
        moved = service.update_project(
            actor=actor,
            organization_id=org_a,
            project_id=project.id,
            workspace_id=second.id,
            workspace_supplied=True,
        )
        ungrouped = service.update_project(
            actor=actor,
            organization_id=org_a,
            project_id=project.id,
            workspace_id=None,
            workspace_supplied=True,
        )
        archived = service.update_project(
            actor=actor,
            organization_id=org_a,
            project_id=project.id,
            status=ProjectStatus.ARCHIVED,
        )

        assert moved.organization_id == org_a
        assert moved.workspace_id == second.id
        assert ungrouped.organization_id == org_a
        assert ungrouped.workspace_id is None
        assert archived.status == ProjectStatus.ARCHIVED
        assert archived.id == project.id
        session.commit()
    finally:
        session.close()


def test_cross_organization_workspace_move_is_rejected(migrated_database: None) -> None:
    actor, org_a, org_b = _seed_orgs_and_actor()
    session = get_session_factory()()
    try:
        service = TenancyService(
            SqlTenancyRepository(session),
            SqlPlatformRepository(session),
            SqlAuditRepository(session),
        )
        workspace_a = service.create_workspace(
            actor=actor,
            organization_id=org_a,
            name="Workspace A",
            slug=f"wa-{uuid4().hex}",
        )
        session.commit()
        workspace_b = service.create_workspace(
            actor=actor,
            organization_id=org_b,
            name="Workspace B",
            slug=f"wb-{uuid4().hex}",
        )
        session.commit()
        project = service.create_project(
            actor=actor,
            organization_id=org_a,
            workspace_id=workspace_a.id,
            name="Project A",
            slug=f"pa-{uuid4().hex}",
        )

        with pytest.raises(CrossOrganizationWorkspaceError):
            service.update_project(
                actor=actor,
                organization_id=org_a,
                project_id=project.id,
                workspace_id=workspace_b.id,
                workspace_supplied=True,
            )
        session.rollback()
    finally:
        session.close()


def test_workspace_delete_rejects_active_project(migrated_database: None) -> None:
    actor, org_a, _ = _seed_orgs_and_actor()
    session = get_session_factory()()
    try:
        service = TenancyService(
            SqlTenancyRepository(session),
            SqlPlatformRepository(session),
            SqlAuditRepository(session),
        )
        workspace = service.create_workspace(
            actor=actor,
            organization_id=org_a,
            name="Protected Workspace",
            slug=f"protected-{uuid4().hex}",
        )
        service.create_project(
            actor=actor,
            organization_id=org_a,
            workspace_id=workspace.id,
            name="Active Project",
            slug=f"active-{uuid4().hex}",
        )

        with pytest.raises(WorkspaceHasActiveProjectsError):
            service.update_workspace(
                actor=actor,
                organization_id=org_a,
                workspace_id=workspace.id,
                status=WorkspaceStatus.DELETED,
            )
        session.rollback()
    finally:
        session.close()
