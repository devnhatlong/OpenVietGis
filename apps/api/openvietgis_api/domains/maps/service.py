from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import TenantResourceNotFoundError
from openvietgis_api.domains.maps.domain import (
    MAX_REVISION,
    Configuration,
    MapOperation,
    MapReceipt,
    MapRevision,
    MapState,
    MapValidationError,
    SaveIntent,
    map_identity,
)
from openvietgis_api.domains.maps.ports import (
    MapIntentConflictError,
    MapNoChangesError,
    MapRepository,
    MapRevisionConflictError,
)
from openvietgis_api.domains.tenancy.domain import ActorType


@dataclass(frozen=True, slots=True)
class MapService:
    repository: MapRepository

    def get_map(self, *, context: AuthorizationContext) -> MapState:
        self.repository.prepare_scope(
            context=context, permission=Permission.PROJECT_READ, mutation=False
        )
        state = self.repository.get_map(context=context)
        if state is not None:
            return state
        assert context.project_id is not None
        return MapState(
            map_identity(context.project_id),
            context.organization_id,
            context.project_id,
            0,
            Configuration(),
        )

    def save(self, *, context: AuthorizationContext, intent: SaveIntent) -> MapReceipt:
        self.repository.prepare_scope(
            context=context, permission=Permission.PROJECT_EDIT, mutation=True
        )
        actor = context.actor
        if actor.actor_type not in ("human", "service_principal") or actor.actor_id is None:
            raise MapValidationError("authenticated map actor required")
        existing = self.repository.get_operation(context=context, operation_id=intent.operation_id)
        if existing is not None:
            if (existing.actor_type, existing.actor_id, existing.request_hash) != (
                actor.actor_type,
                actor.actor_id,
                intent.fingerprint,
            ):
                raise MapIntentConflictError("operation cannot be reused")
            return existing.receipt
        previous = self.repository.get_map(context=context, lock=True)
        revision = previous.configuration_revision if previous else 0
        if intent.expected_revision != revision or revision == MAX_REVISION:
            raise MapRevisionConflictError("configuration revision changed")
        configuration = intent.apply(previous.configuration if previous else Configuration())
        if previous is not None and previous.configuration == configuration:
            raise MapNoChangesError("configuration has no material change")
        self.repository.validate_references(context=context, configuration=configuration)
        assert context.project_id is not None
        now = datetime.now(UTC)
        state = MapState(
            map_identity(context.project_id),
            context.organization_id,
            context.project_id,
            revision + 1,
            configuration,
            now,
        )
        operation = MapOperation(
            intent.operation_id,
            state.map_id,
            actor.actor_type,
            actor.actor_id,
            intent.fingerprint,
            state.configuration_revision,
            now,
        )
        change = MapRevision(
            state.map_id,
            operation.operation_id,
            state.configuration_revision,
            revision,
            actor.actor_type,
            actor.actor_id,
            actor.display_name,
            now,
            previous.configuration if previous else None,
            configuration,
            uuid4(),
        )
        audit = AuditEvent(
            id=change.audit_event_id,
            organization_id=context.organization_id,
            actor_type=ActorType(actor.actor_type),
            actor_id=actor.actor_id,
            actor_display_snapshot=actor.display_name,
            action="map.configuration.saved",
            resource_type="project_map",
            resource_id=state.map_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "project_id": str(context.project_id),
                "operation_id": str(operation.operation_id),
                "configuration_revision": state.configuration_revision,
            },
            created_at=now,
        )
        self.repository.commit_save(
            context=context,
            state=state,
            operation=operation,
            revision=change,
            audit=audit,
            expected_revision=revision,
        )
        return operation.receipt

    def operation(self, *, context: AuthorizationContext, operation_id: UUID) -> MapReceipt:
        # Edit-only credentials may reconcile only their own minimal receipt.
        # Archived/revoked edit authority remains denied by existing lifecycle.
        self.repository.prepare_scope(
            context=context, permission=Permission.PROJECT_EDIT, mutation=True
        )
        operation = self.repository.get_operation(context=context, operation_id=operation_id)
        if operation is None or (operation.actor_type, operation.actor_id) != (
            context.actor.actor_type,
            context.actor.actor_id,
        ):
            raise TenantResourceNotFoundError("resource not found")
        return operation.receipt

    def history(
        self,
        *,
        context: AuthorizationContext,
        after_revision: int | None = None,
        limit: int = 50,
    ) -> tuple[list[MapRevision], int | None]:
        self.repository.prepare_scope(
            context=context, permission=Permission.PROJECT_READ, mutation=False
        )
        if type(limit) is not int or not 1 <= limit <= 100:
            raise MapValidationError("invalid history limit")
        if after_revision is not None and (
            type(after_revision) is not int or not 1 <= after_revision <= MAX_REVISION
        ):
            raise MapValidationError("invalid history continuation")
        items = self.repository.list_history(
            context=context, after_revision=after_revision, limit=limit + 1
        )
        page = items[:limit]
        return page, page[-1].configuration_revision if len(items) > limit else None
