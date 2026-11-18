from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.domain import ResourceGrant
from openvietgis_api.domains.authorization.permissions import Permission


class EffectivePermissionProvider(Protocol):
    def resolve(self, context: AuthorizationContext) -> frozenset[Permission]: ...


class ResourceGrantRepository(Protocol):
    def list_for_organization(
        self, organization_id: UUID, *, context: AuthorizationContext
    ) -> list[ResourceGrant]: ...

    def create(self, grant: ResourceGrant, *, context: AuthorizationContext) -> None: ...

    def get(
        self,
        *,
        context: AuthorizationContext,
        organization_id: UUID,
        grant_id: UUID,
        for_update: bool = False,
    ) -> ResourceGrant | None: ...

    def update(self, grant: ResourceGrant, *, context: AuthorizationContext) -> None: ...
