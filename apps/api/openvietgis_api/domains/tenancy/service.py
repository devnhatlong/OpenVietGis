from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

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
    Project,
    ProjectStatus,
    Workspace,
    WorkspaceStatus,
)
from openvietgis_api.domains.tenancy.ports import InstallationStateReader, TenancyRepository

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class InstallationNotInitializedError(RuntimeError):
    pass


class InvalidOrganizationInputError(ValueError):
    pass


class WorkspaceNotFoundError(LookupError):
    pass


class ProjectNotFoundError(LookupError):
    pass


class WorkspaceHasActiveProjectsError(RuntimeError):
    pass


class InvalidLifecycleTransitionError(ValueError):
    pass


class CrossOrganizationWorkspaceError(ValueError):
    pass


def _actor_type(actor: Actor) -> ActorType:
    return ActorType(actor.actor_type)


def _clean_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("name is required")
    return normalized


def _clean_slug(value: str) -> str:
    normalized = value.strip().lower()
    if not SLUG_RE.fullmatch(normalized):
        raise ValueError("invalid slug")
    return normalized


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

    def _audit(
        self,
        *,
        actor: Actor,
        organization_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        metadata: dict[str, object] | None = None,
        now: datetime,
    ) -> None:
        self._audit_repository.append(
            AuditEvent(
                id=uuid4(),
                organization_id=organization_id,
                actor_type=_actor_type(actor),
                actor_id=actor.actor_id,
                actor_display_snapshot=actor.display_name,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=AuditOutcome.SUCCESS,
                metadata=metadata or {},
                created_at=now,
            )
        )

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
        try:
            normalized_name = _clean_name(name)
            normalized_slug = _clean_slug(slug)
        except ValueError as exc:
            raise InvalidOrganizationInputError(str(exc)) from exc

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
        self._audit(
            actor=actor,
            organization_id=organization.id,
            action="organization.create",
            resource_type="organization",
            resource_id=organization.id,
            metadata={"slug": organization.slug},
            now=now,
        )
        return organization, membership

    def create_workspace(
        self,
        *,
        actor: Actor,
        organization_id: UUID,
        name: str,
        slug: str,
        now: datetime | None = None,
    ) -> Workspace:
        now = now or datetime.now(UTC)
        workspace = Workspace(
            id=uuid4(),
            organization_id=organization_id,
            name=_clean_name(name),
            slug=_clean_slug(slug),
            status=WorkspaceStatus.ACTIVE,
            created_by_actor_type=_actor_type(actor),
            created_by_actor_id=actor.actor_id,
            created_at=now,
            updated_at=now,
            archived_at=None,
            deleted_at=None,
        )
        self._repository.create_workspace(workspace)
        self._audit(
            actor=actor,
            organization_id=organization_id,
            action="workspace.create",
            resource_type="workspace",
            resource_id=workspace.id,
            metadata={"slug": workspace.slug},
            now=now,
        )
        return workspace

    def update_workspace(
        self,
        *,
        actor: Actor,
        organization_id: UUID,
        workspace_id: UUID,
        name: str | None = None,
        status: WorkspaceStatus | None = None,
        now: datetime | None = None,
    ) -> Workspace:
        workspace = self._repository.get_workspace(
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        if workspace is None:
            raise WorkspaceNotFoundError("workspace not found")
        if workspace.status == WorkspaceStatus.DELETED:
            raise InvalidLifecycleTransitionError("deleted workspace cannot be mutated")

        now = now or datetime.now(UTC)
        new_status = status or workspace.status
        if new_status == WorkspaceStatus.DELETED:
            if (
                self._repository.count_active_projects_in_workspace(
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                )
                > 0
            ):
                raise WorkspaceHasActiveProjectsError(
                    "workspace with active projects cannot be deleted"
                )

        updated = replace(
            workspace,
            name=_clean_name(name) if name is not None else workspace.name,
            status=new_status,
            updated_at=now,
            archived_at=(
                now
                if new_status == WorkspaceStatus.ARCHIVED
                else None
                if new_status == WorkspaceStatus.ACTIVE
                else workspace.archived_at
            ),
            deleted_at=now if new_status == WorkspaceStatus.DELETED else workspace.deleted_at,
        )
        self._repository.update_workspace(updated)
        self._audit(
            actor=actor,
            organization_id=organization_id,
            action="workspace.update",
            resource_type="workspace",
            resource_id=workspace_id,
            metadata={"status": updated.status.value},
            now=now,
        )
        return updated

    def create_project(
        self,
        *,
        actor: Actor,
        organization_id: UUID,
        name: str,
        slug: str,
        workspace_id: UUID | None = None,
        now: datetime | None = None,
    ) -> Project:
        if workspace_id is not None:
            workspace = self._repository.get_workspace(
                organization_id=organization_id,
                workspace_id=workspace_id,
            )
            if workspace is None:
                raise CrossOrganizationWorkspaceError(
                    "workspace does not belong to organization"
                )
            if workspace.status == WorkspaceStatus.DELETED:
                raise InvalidLifecycleTransitionError("deleted workspace cannot receive projects")

        now = now or datetime.now(UTC)
        project = Project(
            id=uuid4(),
            organization_id=organization_id,
            workspace_id=workspace_id,
            name=_clean_name(name),
            slug=_clean_slug(slug),
            status=ProjectStatus.ACTIVE,
            created_by_actor_type=_actor_type(actor),
            created_by_actor_id=actor.actor_id,
            created_at=now,
            updated_at=now,
            archived_at=None,
            deleted_at=None,
        )
        self._repository.create_project(project)
        self._audit(
            actor=actor,
            organization_id=organization_id,
            action="project.create",
            resource_type="project",
            resource_id=project.id,
            metadata={"slug": project.slug},
            now=now,
        )
        return project

    def update_project(
        self,
        *,
        actor: Actor,
        organization_id: UUID,
        project_id: UUID,
        name: str | None = None,
        workspace_id: UUID | None = None,
        workspace_supplied: bool = False,
        status: ProjectStatus | None = None,
        now: datetime | None = None,
    ) -> Project:
        project = self._repository.get_project(
            organization_id=organization_id,
            project_id=project_id,
        )
        if project is None:
            raise ProjectNotFoundError("project not found")
        if project.status == ProjectStatus.DELETED:
            raise InvalidLifecycleTransitionError("deleted project cannot be mutated")
        if project.status == ProjectStatus.ARCHIVED and (
            name is not None or workspace_supplied
        ):
            raise InvalidLifecycleTransitionError(
                "archived project must be restored before normal mutation"
            )

        target_workspace_id = project.workspace_id
        if workspace_supplied:
            target_workspace_id = workspace_id
            if workspace_id is not None:
                workspace = self._repository.get_workspace(
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                )
                if workspace is None:
                    raise CrossOrganizationWorkspaceError(
                        "workspace does not belong to organization"
                    )
                if workspace.status == WorkspaceStatus.DELETED:
                    raise InvalidLifecycleTransitionError(
                        "deleted workspace cannot receive projects"
                    )

        now = now or datetime.now(UTC)
        new_status = status or project.status
        updated = replace(
            project,
            name=_clean_name(name) if name is not None else project.name,
            workspace_id=target_workspace_id,
            status=new_status,
            updated_at=now,
            archived_at=(
                now
                if new_status == ProjectStatus.ARCHIVED
                else None
                if new_status == ProjectStatus.ACTIVE
                else project.archived_at
            ),
            deleted_at=now if new_status == ProjectStatus.DELETED else project.deleted_at,
        )
        self._repository.update_project(updated)
        self._audit(
            actor=actor,
            organization_id=organization_id,
            action="project.update",
            resource_type="project",
            resource_id=project_id,
            metadata={
                "status": updated.status.value,
                "workspace_id": (
                    str(updated.workspace_id) if updated.workspace_id is not None else None
                ),
            },
            now=now,
        )
        return updated
