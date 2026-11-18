"""Public tenant API representations; never expose stored secret digests."""

from openvietgis_api.domains.authorization.domain import ResourceGrant
from openvietgis_api.domains.tenancy.domain import Organization, OrganizationMembership


def serialize_organization(organization: Organization) -> dict[str, object]:
    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug,
        "status": organization.status.value,
    }


def serialize_membership(membership: OrganizationMembership) -> dict[str, object]:
    return {
        "id": membership.id,
        "organization_id": membership.organization_id,
        "user_id": membership.user_id,
        "role": membership.role.value,
        "status": membership.status.value,
    }


def serialize_grant(grant: ResourceGrant) -> dict[str, object]:
    return {
        "id": grant.id,
        "organization_id": grant.organization_id,
        "subject_kind": grant.subject_kind,
        "subject_id": grant.membership_id
        if grant.subject_kind == "membership"
        else grant.service_principal_id,
        "scope_kind": grant.scope_kind.value,
        "workspace_id": grant.workspace_id,
        "project_id": grant.project_id,
        "role": grant.role.value,
        "created_at": grant.created_at,
        "revoked_at": grant.revoked_at,
    }
