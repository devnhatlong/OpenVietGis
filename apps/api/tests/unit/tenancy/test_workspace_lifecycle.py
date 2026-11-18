from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.tenancy.domain import (
    ActorType,
    Organization,
    OrganizationStatus,
    Workspace,
    WorkspaceStatus,
)
from openvietgis_api.domains.tenancy.service import (
    TenancyService,
    WorkspaceHasActiveProjectsError,
)


class WorkspaceRepo:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def get_organization(self, organization_id, *, context, for_update=False):
        assert organization_id == self.workspace.organization_id
        assert for_update
        return Organization(
            id=organization_id,
            name="Organization",
            slug="organization",
            status=OrganizationStatus.ACTIVE,
            created_by_actor_type=ActorType.HUMAN,
            created_by_actor_id=self.workspace.created_by_actor_id,
            created_at=self.workspace.created_at,
            updated_at=self.workspace.updated_at,
            deleted_at=None,
        )

    def get_workspace(self, *, context, organization_id, workspace_id):
        assert organization_id == self.workspace.organization_id
        assert workspace_id == self.workspace.id
        return self.workspace

    def count_active_projects_in_workspace(self, *, context, organization_id, workspace_id):
        del organization_id, workspace_id
        return 1

    def update_workspace(self, workspace: Workspace, *, context) -> None:
        self.workspace = workspace


class Installation:
    def is_initialized(self) -> bool:
        return True


class Audit:
    def append(self, event) -> None:
        del event


def test_workspace_with_active_projects_cannot_be_deleted() -> None:
    now = datetime.now(UTC)
    workspace = Workspace(
        id=uuid4(),
        organization_id=uuid4(),
        name="Workspace",
        slug="workspace",
        status=WorkspaceStatus.ACTIVE,
        created_by_actor_type=ActorType.HUMAN,
        created_by_actor_id=uuid4(),
        created_at=now,
        updated_at=now,
        archived_at=None,
        deleted_at=None,
    )
    service = TenancyService(WorkspaceRepo(workspace), Installation(), Audit())

    with pytest.raises(WorkspaceHasActiveProjectsError):
        service.update_workspace(
            actor=Actor(actor_type="human", actor_id=uuid4(), display_name="Owner"),
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            status=WorkspaceStatus.DELETED,
        )
