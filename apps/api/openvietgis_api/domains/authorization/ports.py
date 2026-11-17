from __future__ import annotations

from typing import Protocol

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission


class EffectivePermissionProvider(Protocol):
    def resolve(self, context: AuthorizationContext) -> frozenset[Permission]: ...
