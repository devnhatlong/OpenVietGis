from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ActorType(StrEnum):
    HUMAN = "human"
    SERVICE_PRINCIPAL = "service_principal"
    SYSTEM = "system"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ResourceRole(StrEnum):
    MANAGER = "manager"
    EDITOR = "editor"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class ResourceScopeKind(StrEnum):
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"
    PROJECT = "project"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class InvitationTargetKind(StrEnum):
    EMAIL = "email"
    USER = "user"
    EXTERNAL_IDENTITY = "external_identity"


@dataclass(frozen=True, slots=True)
class Organization:
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
    created_by_actor_type: ActorType
    created_by_actor_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class OrganizationMembership:
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: MembershipRole
    status: MembershipStatus
    created_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class Workspace:
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: WorkspaceStatus
    created_by_actor_type: ActorType
    created_by_actor_id: UUID | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    organization_id: UUID
    workspace_id: UUID | None
    name: str
    slug: str
    status: ProjectStatus
    created_by_actor_type: ActorType
    created_by_actor_id: UUID | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class Invitation:
    id: UUID
    organization_id: UUID
    status: InvitationStatus
    target_kind: InvitationTargetKind
    target_email_normalized: str | None
    target_user_id: UUID | None
    target_issuer: str | None
    target_subject: str | None
    organization_role: MembershipRole
    resource_scope_kind: ResourceScopeKind | None
    resource_workspace_id: UUID | None
    resource_project_id: UUID | None
    resource_role: ResourceRole | None
    token_hash: bytes
    token_prefix: str
    expires_at: datetime
    created_at: datetime
    created_by_actor_type: ActorType
    created_by_actor_id: UUID | None
    accepted_at: datetime | None
    accepted_by_user_id: UUID | None
    revoked_at: datetime | None
