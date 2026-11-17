from __future__ import annotations

from dataclasses import dataclass

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.ports import EffectivePermissionProvider


class AuthorizationDeniedError(PermissionError):
    pass


class TenantResourceNotFoundError(LookupError):
    pass


@dataclass(slots=True)
class AuthorizationService:
    permission_provider: EffectivePermissionProvider

    def effective_permissions(self, context: AuthorizationContext) -> frozenset[Permission]:
        return self.permission_provider.resolve(context)

    def is_allowed(self, context: AuthorizationContext, permission: Permission) -> bool:
        return permission in self.effective_permissions(context)

    def require(self, context: AuthorizationContext, permission: Permission) -> None:
        if not self.is_allowed(context, permission):
            raise AuthorizationDeniedError(f"missing permission: {permission.value}")
