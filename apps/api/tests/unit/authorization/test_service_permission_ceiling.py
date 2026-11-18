import pytest

from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import (
    InvalidServiceCredentialError,
    apply_permission_ceiling,
)


def test_permission_ceiling_only_restricts_granted_permissions() -> None:
    granted = frozenset(
        {
            Permission.PROJECT_READ,
            Permission.PROJECT_EDIT,
            Permission.PROJECT_SHARE,
        }
    )

    assert apply_permission_ceiling(granted, None) == granted
    assert apply_permission_ceiling(
        granted,
        frozenset({Permission.PROJECT_READ}),
    ) == frozenset({Permission.PROJECT_READ})


def test_permission_ceiling_cannot_expand_principal_grants() -> None:
    with pytest.raises(InvalidServiceCredentialError):
        apply_permission_ceiling(
            frozenset({Permission.PROJECT_READ}),
            frozenset({Permission.PROJECT_READ, Permission.PROJECT_EDIT}),
        )
