from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.audit.ports import AuditRepository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.domain import ResourceGrant
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.ports import (
    EffectivePermissionProvider,
    ResourceGrantRepository,
)
from openvietgis_api.domains.tenancy.domain import (
    ActorType,
    ResourceRole,
    ResourceScopeKind,
)
from openvietgis_api.domains.tenancy.ports import TenancyRepository


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


class InvalidGrantError(ValueError):
    pass


class GrantNotFoundError(LookupError):
    pass


@dataclass(slots=True)
class GrantService:
    repository: ResourceGrantRepository
    tenancy_repository: TenancyRepository
    audit_repository: AuditRepository

    def create_membership_grant(
        self,
        *,
        actor: Actor,
        organization_id: UUID,
        membership_id: UUID,
        scope_kind: ResourceScopeKind,
        role: ResourceRole,
        workspace_id: UUID | None = None,
        project_id: UUID | None = None,
        now: datetime | None = None,
    ) -> ResourceGrant:
        membership = self.tenancy_repository.get_membership(
            organization_id=organization_id,
            membership_id=membership_id,
        )
        if membership is None:
            raise InvalidGrantError("membership does not belong to organization")

        if scope_kind == ResourceScopeKind.ORGANIZATION:
            if workspace_id is not None or project_id is not None:
                raise InvalidGrantError("organization scope cannot include resource id")
        elif scope_kind == ResourceScopeKind.WORKSPACE:
            if workspace_id is None or project_id is not None:
                raise InvalidGrantError("workspace scope requires workspace_id only")
            if (
                self.tenancy_repository.get_workspace(
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                )
                is None
            ):
                raise InvalidGrantError("workspace does not belong to organization")
        elif scope_kind == ResourceScopeKind.PROJECT:
            if project_id is None or workspace_id is not None:
                raise InvalidGrantError("project scope requires project_id only")
            if (
                self.tenancy_repository.get_project(
                    organization_id=organization_id,
                    project_id=project_id,
                )
                is None
            ):
                raise InvalidGrantError("project does not belong to organization")

        now = now or datetime.now(UTC)
        grant = ResourceGrant(
            id=uuid4(),
            organization_id=organization_id,
            subject_kind="membership",
            membership_id=membership_id,
            service_principal_id=None,
            scope_kind=scope_kind,
            workspace_id=workspace_id,
            project_id=project_id,
            role=role,
            created_at=now,
            created_by_actor_type=ActorType(actor.actor_type),
            created_by_actor_id=actor.actor_id,
            revoked_at=None,
        )
        self.repository.create(grant)
        self.audit_repository.append(
            AuditEvent(
                id=uuid4(),
                organization_id=organization_id,
                actor_type=ActorType(actor.actor_type),
                actor_id=actor.actor_id,
                actor_display_snapshot=actor.display_name,
                action="authorization.grant.create",
                resource_type="resource_grant",
                resource_id=grant.id,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "scope_kind": scope_kind.value,
                    "role": role.value,
                    "membership_id": str(membership_id),
                },
                created_at=now,
            )
        )
        return grant

    def revoke(
        self,
        *,
        actor: Actor,
        organization_id: UUID,
        grant_id: UUID,
        now: datetime | None = None,
    ) -> ResourceGrant:
        grant = self.repository.get(
            organization_id=organization_id,
            grant_id=grant_id,
            for_update=True,
        )
        if grant is None:
            raise GrantNotFoundError("grant not found")
        if grant.revoked_at is not None:
            return grant

        now = now or datetime.now(UTC)
        revoked = replace(grant, revoked_at=now)
        self.repository.update(revoked)
        self.audit_repository.append(
            AuditEvent(
                id=uuid4(),
                organization_id=organization_id,
                actor_type=ActorType(actor.actor_type),
                actor_id=actor.actor_id,
                actor_display_snapshot=actor.display_name,
                action="authorization.grant.revoke",
                resource_type="resource_grant",
                resource_id=grant.id,
                outcome=AuditOutcome.SUCCESS,
                metadata={},
                created_at=now,
            )
        )
        return revoked
