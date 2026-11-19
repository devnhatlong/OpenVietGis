from __future__ import annotations

from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.audit.domain import AuditEvent
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.maps.domain import Configuration, MapOperation, MapRevision, MapState


class MapRevisionConflictError(ValueError):
    """Current configuration revision differs from the explicit save base."""


class MapIntentConflictError(ValueError):
    """Operation identity cannot be used for this actor or intent."""


class MapNoChangesError(ValueError):
    """The request does not change an existing committed configuration."""


class MapReferenceUnavailableError(ValueError):
    """A requested map Layer is not currently supported in this Project."""


class MapRepository(Protocol):
    """Request transaction owns commit/rollback; every operation requires scope proof."""

    def prepare_scope(
        self,
        *,
        context: AuthorizationContext,
        permission: Permission,
        mutation: bool,
    ) -> None: ...

    def get_map(
        self,
        *,
        context: AuthorizationContext,
        lock: bool = False,
    ) -> MapState | None: ...

    def get_operation(
        self,
        *,
        context: AuthorizationContext,
        operation_id: UUID,
    ) -> MapOperation | None: ...

    def validate_references(
        self,
        *,
        context: AuthorizationContext,
        configuration: Configuration,
    ) -> None: ...

    def commit_save(
        self,
        *,
        context: AuthorizationContext,
        state: MapState,
        operation: MapOperation,
        revision: MapRevision,
        audit: AuditEvent,
        expected_revision: int,
    ) -> None: ...

    def list_history(
        self,
        *,
        context: AuthorizationContext,
        after_revision: int | None,
        limit: int,
    ) -> list[MapRevision]: ...
