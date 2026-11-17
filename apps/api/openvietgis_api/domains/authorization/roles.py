from openvietgis_api.domains.authorization.permissions import ALL_PERMISSIONS, Permission
from openvietgis_api.domains.tenancy.domain import MembershipRole, ResourceRole

OWNER_ONLY = frozenset(
    {
        Permission.ORGANIZATION_LIFECYCLE,
        Permission.ORGANIZATION_OWNER_TRANSFER,
        Permission.ORGANIZATION_DELETE,
    }
)

ORGANIZATION_ROLE_PERMISSIONS: dict[MembershipRole, frozenset[Permission]] = {
    MembershipRole.OWNER: ALL_PERMISSIONS,
    MembershipRole.ADMIN: ALL_PERMISSIONS - OWNER_ONLY,
    MembershipRole.MEMBER: frozenset({Permission.ORGANIZATION_READ}),
    MembershipRole.GUEST: frozenset(),
}

RESOURCE_ROLE_PERMISSIONS: dict[ResourceRole, frozenset[Permission]] = {
    ResourceRole.MANAGER: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.WORKSPACE_MANAGE,
            Permission.PROJECT_READ,
            Permission.PROJECT_EDIT,
            Permission.PROJECT_MANAGE,
            Permission.PROJECT_MOVE_WORKSPACE,
            Permission.PROJECT_ARCHIVE,
            Permission.PROJECT_DELETE,
            Permission.PROJECT_SHARE,
        }
    ),
    ResourceRole.EDITOR: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.PROJECT_READ,
            Permission.PROJECT_EDIT,
            Permission.PROJECT_SHARE,
        }
    ),
    ResourceRole.CONTRIBUTOR: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.PROJECT_READ,
            Permission.PROJECT_EDIT,
        }
    ),
    ResourceRole.VIEWER: frozenset(
        {
            Permission.WORKSPACE_READ,
            Permission.PROJECT_READ,
        }
    ),
}
