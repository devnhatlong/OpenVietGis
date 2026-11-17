from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.tenancy.domain import Organization, OrganizationMembership


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


class InstallationStateReader(Protocol):
    def is_initialized(self) -> bool: ...