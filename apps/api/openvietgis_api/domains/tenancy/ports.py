from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext, TenantContext
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
        *,
        actor: Actor,
    ) -> list[tuple[Organization, OrganizationMembership]]: ...

    def get_active_membership(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        user_id: UUID,
    ) -> OrganizationMembership | None: ...

    def create_organization_with_owner(
        self,
        organization: Organization,
        membership: OrganizationMembership,
        *,
        context: AuthorizationContext,
    ) -> None: ...

    def get_organization(
        self,
        organization_id: UUID,
        *,
        context: TenantContext,
        for_update: bool = False,
    ) -> Organization | None: ...

    def update_organization(
        self, organization: Organization, *, context: AuthorizationContext
    ) -> None: ...

    def list_memberships(
        self, organization_id: UUID, *, context: AuthorizationContext
    ) -> list[OrganizationMembership]: ...

    def get_membership(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        membership_id: UUID,
        for_update: bool = False,
    ) -> OrganizationMembership | None: ...

    def get_membership_for_user(
        self,
        *,
        context: TenantContext,
        organization_id: UUID,
        user_id: UUID,
        for_update: bool = False,
    ) -> OrganizationMembership | None: ...

    def count_other_active_owners(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        excluding_membership_id: UUID,
    ) -> int: ...

    def create_membership(
        self, membership: OrganizationMembership, *, context: TenantContext
    ) -> None: ...

    def update_membership(
        self, membership: OrganizationMembership, *, context: TenantContext
    ) -> None: ...

    def create_invitation(
        self, invitation: Invitation, *, context: AuthorizationContext
    ) -> None: ...

    def get_invitation(
        self,
        *,
        context: TenantContext,
        organization_id: UUID,
        invitation_id: UUID,
        for_update: bool = False,
    ) -> Invitation | None: ...

    def update_invitation(self, invitation: Invitation, *, context: TenantContext) -> None: ...

    def list_workspaces(
        self, organization_id: UUID, *, context: AuthorizationContext
    ) -> list[Workspace]: ...

    def get_workspace(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        workspace_id: UUID,
    ) -> Workspace | None: ...

    def create_workspace(self, workspace: Workspace, *, context: AuthorizationContext) -> None: ...

    def update_workspace(self, workspace: Workspace, *, context: AuthorizationContext) -> None: ...

    def count_active_projects_in_workspace(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        workspace_id: UUID,
    ) -> int: ...

    def list_projects(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        workspace_id: UUID | None = None,
    ) -> list[Project]: ...

    def get_project(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        project_id: UUID,
    ) -> Project | None: ...

    def create_project(self, project: Project, *, context: AuthorizationContext) -> None: ...

    def update_project(self, project: Project, *, context: AuthorizationContext) -> None: ...


class InstallationStateReader(Protocol):
    def is_initialized(self) -> bool: ...
