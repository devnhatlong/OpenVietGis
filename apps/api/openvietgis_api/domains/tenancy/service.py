from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.audit.ports import AuditRepository
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.tenancy.domain import (
    ActorType,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
)
from openvietgis_api.domains.tenancy.ports import InstallationStateReader, TenancyRepository

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class InstallationNotInitializedError(RuntimeError):
    pass


class InvalidOrganizationInputError(ValueError):
    pass


class TenancyService:
    def __init__(
        self,
        repository: TenancyRepository,
        installation_state: InstallationStateReader,
        audit_repository: AuditRepository,
    ) -> None:
        self._repository = repository
        self._installation_state = installation_state
        self._audit_repository = audit_repository

    def create_organization(
        self,
        *,
        actor: Actor,
        name: str,
        slug: str,
        now: datetime | None = None,
    ) -> tuple[Organization, OrganizationMembership]:
        if actor.actor_type != "human" or actor.actor_id is None:
            raise InvalidOrganizationInputError("human actor required")
        if not self._installation_state.is_initialized():
            raise InstallationNotInitializedError("installation is not initialized")
        normalized_name = name.strip()
        normalized_slug = slug.strip().lower()
        if not normalized_name or not SLUG_RE.fullmatch(normalized_slug):
            raise InvalidOrganizationInputError("invalid organization name or slug")

        now = now or datetime.now(UTC)
        organization = Organization(
            id=uuid4(),
            name=normalized_name,
            slug=normalized_slug,
            status=OrganizationStatus.ACTIVE,
            created_by_actor_type=ActorType.HUMAN,
            created_by_actor_id=actor.actor_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        membership = OrganizationMembership(
            id=uuid4(),
            organization_id=organization.id,
            user_id=actor.actor_id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            activated_at=now,
            suspended_at=None,
            revoked_at=None,
        )
        self._repository.create_organization_with_owner(organization, membership)
        self._audit_repository.append(
            AuditEvent(
                id=uuid4(),
                organization_id=organization.id,
                actor_type=ActorType.HUMAN,
                actor_id=actor.actor_id,
                actor_display_snapshot=actor.display_name,
                action="organization.create",
                resource_type="organization",
                resource_id=organization.id,
                outcome=AuditOutcome.SUCCESS,
                metadata={"slug": organization.slug},
                created_at=now,
            )
        )
        return organization, membership
