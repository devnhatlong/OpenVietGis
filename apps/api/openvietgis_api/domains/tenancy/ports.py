from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.tenancy.domain import (
    Organization,
    OrganizationMembership,
    Project,
    Workspace,
)


class TenancyRepository(Protocol):
    def list_active_organizations_for_user(
        self,
        user_id: UUID,
    ) -> list[tuple[Organization, OrganizationMembership]]: ...

    def get_active_membership(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
    ) -> OrganizationMembership | None: ...

    def create_organization_with_owner(
        self,
        organization: Organization,
        membership: OrganizationMembership,
    ) -> None: ...

    def list_workspaces(self, organization_id: UUID) -> list[Workspace]: ...

    def get_workspace(
        self,
        *,
        organization_id: UUID,
        workspace_id: UUID,
    ) -> Workspace | None: ...

    def create_workspace(self, workspace: Workspace) -> None: ...

    def update_workspace(self, workspace: Workspace) -> None: ...

    def count_active_projects_in_workspace(
        self,
        *,
        organization_id: UUID,
        workspace_id: UUID,
    ) -> int: ...

    def list_projects(
        self,
        *,
        organization_id: UUID,
        workspace_id: UUID | None = None,
    ) -> list[Project]: ...

    def get_project(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
    ) -> Project | None: ...

    def create_project(self, project: Project) -> None: ...

    def update_project(self, project: Project) -> None: ...


class InstallationStateReader(Protocol):
    def is_initialized(self) -> bool: ...