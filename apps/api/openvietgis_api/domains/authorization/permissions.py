from enum import StrEnum


class Permission(StrEnum):
    ORGANIZATION_READ = "organization.read"
    ORGANIZATION_MANAGE_MEMBERS = "organization.manage_members"
    ORGANIZATION_MANAGE_SETTINGS = "organization.manage_settings"
    ORGANIZATION_LIFECYCLE = "organization.lifecycle"
    ORGANIZATION_OWNER_TRANSFER = "organization.owner.transfer"
    ORGANIZATION_DELETE = "organization.delete"
    AUTHORIZATION_MANAGE_GRANTS = "authorization.manage_grants"
    INVITATION_MANAGE = "invitation.manage"
    SERVICE_PRINCIPAL_MANAGE = "service_principal.manage"
    AUDIT_READ = "audit.read"
    WORKSPACE_READ = "workspace.read"
    WORKSPACE_MANAGE = "workspace.manage"
    PROJECT_READ = "project.read"
    PROJECT_EDIT = "project.edit"
    PROJECT_MANAGE = "project.manage"
    PROJECT_MOVE_WORKSPACE = "project.move_workspace"
    PROJECT_ARCHIVE = "project.archive"
    PROJECT_DELETE = "project.delete"
    PROJECT_SHARE = "project.share"


ALL_PERMISSIONS = frozenset(Permission)
