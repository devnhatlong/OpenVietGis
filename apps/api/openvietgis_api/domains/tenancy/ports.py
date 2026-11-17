from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.tenancy.domain import (
    Invitation,
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

    def get_organization(
        self,
        organization_id: UUID,
        *,
        for_update: bool = False,
    ) -> Organization | None: ...

    def update_organization(self, organization: Organization) -> None: ...

    def list_memberships(self, organization_id: UUID) -> list[OrganizationMembership]: ...

    def get_membership(
        self,
        *,
        organization_id: UUID,
        membership_id: UUID,
        for_update: bool = False,
    ) -> OrganizationMembership | None: ...

    def get_membership_for_user(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        for_update: bool = False,
    ) -> OrganizationMembership | None: ...

    def count_other_active_owners(
        self,
        *,
        organization_id: UUID,
        excluding_membership_id: UUID,
    ) -> int: ...

    def create_membership(self, membership: OrganizationMembership) -> None: ...

    def update_membership(self, membership: OrganizationMembership) -> None: ...

    def create_invitation(self, invitation: Invitation) -> None: ...

    def get_invitation(
        self,
        *,
        organization_id: UUID,
        invitation_id: UUID,
        for_update: bool = False,
    ) -> Invitation | None: ...

    def update_invitation(self, invitation: Invitation) -> None: ...

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