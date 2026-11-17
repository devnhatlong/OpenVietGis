from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import (
    ORGANIZATION_ROLE_PERMISSIONS,
    RESOURCE_ROLE_PERMISSIONS,
)
from openvietgis_api.domains.tenancy.domain import MembershipRole, ResourceRole


def test_owner_and_admin_bundles_keep_owner_only_permissions_distinct() -> None:
    owner = ORGANIZATION_ROLE_PERMISSIONS[MembershipRole.OWNER]
    admin = ORGANIZATION_ROLE_PERMISSIONS[MembershipRole.ADMIN]

    assert Permission.ORGANIZATION_LIFECYCLE in owner
    assert Permission.ORGANIZATION_OWNER_TRANSFER in owner
    assert Permission.ORGANIZATION_DELETE in owner
    assert Permission.ORGANIZATION_LIFECYCLE not in admin
    assert Permission.ORGANIZATION_OWNER_TRANSFER not in admin
    assert Permission.ORGANIZATION_DELETE not in admin


def test_member_guest_and_resource_roles_are_additive_capability_bundles() -> None:
    member = ORGANIZATION_ROLE_PERMISSIONS[MembershipRole.MEMBER]
    guest = ORGANIZATION_ROLE_PERMISSIONS[MembershipRole.GUEST]
    viewer = RESOURCE_ROLE_PERMISSIONS[ResourceRole.VIEWER]
    editor = RESOURCE_ROLE_PERMISSIONS[ResourceRole.EDITOR]

    assert member == frozenset({Permission.ORGANIZATION_READ})
    assert guest == frozenset()
    assert Permission.PROJECT_READ in viewer
    assert Permission.PROJECT_EDIT not in viewer
    assert viewer <= editor
