"""HTTP adapter tests for T067; never use a database or external OIDC provider."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from openvietgis_api.adapters.http import invitations, organizations, tenant_access
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
)
from openvietgis_api.config import get_settings
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.authorization.service import TenantResourceNotFoundError
from openvietgis_api.domains.tenancy.domain import MembershipRole, OrganizationStatus
from openvietgis_api.domains.tenancy.service import InvalidInvitationError
from openvietgis_api.main import create_app
from openvietgis_api.security.csrf import make_csrf_token


@pytest.fixture
def actor():
    return Actor(actor_type="human", actor_id=uuid4(), display_name="Test actor")


@pytest.fixture
def client(actor):
    app = create_app()
    token = "synthetic-session-token"
    auth = AuthenticatedRequest(actor=actor, session_id=uuid4(), raw_session_token=token)
    session = Mock()
    app.dependency_overrides[authenticate_request] = lambda: auth
    app.dependency_overrides[get_db_session] = lambda: session
    with TestClient(app) as test_client:
        test_client.headers["X-OpenVietGIS-CSRF"] = make_csrf_token(
            token, get_settings().csrf_secret.get_secret_value()
        )
        yield test_client


def test_tenant_admin_routes_registered(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path, methods in {
        "/organizations/{organization_id}": {"get", "patch"},
        "/organizations/{organization_id}/members": {"get"},
        "/organizations/{organization_id}/members/{membership_id}": {"patch"},
        "/organizations/{organization_id}/ownership-transfer": {"post"},
        "/organizations/{organization_id}/grants": {"get", "post"},
        "/organizations/{organization_id}/grants/{grant_id}/revoke": {"post"},
        "/organizations/{organization_id}/invitations": {"post"},
        "/organizations/{organization_id}/invitations/{invitation_id}/revoke": {"post"},
        "/invitations/accept": {"post"},
        "/organizations/{organization_id}/effective-permissions": {"get"},
    }.items():
        assert methods <= paths[f"/api/v1{path}"].keys()


def test_nonmember_hides_organization_before_tenant_lookup(monkeypatch, actor):
    repo = Mock()
    repo.get_active_membership.return_value = None
    monkeypatch.setattr(tenant_access, "SqlTenancyRepository", lambda _: repo)
    with pytest.raises(TenantResourceNotFoundError):
        tenant_access.human_tenant(
            Mock(),
            AuthenticatedRequest(actor, uuid4(), "synthetic-session-token"),
            uuid4(),
        )
    repo.get_organization.assert_not_called()


def test_admin_cannot_promote_self_to_owner(client, monkeypatch):
    monkeypatch.setattr(
        organizations,
        "require_human_permission",
        lambda *args, **kwargs: SimpleNamespace(role=MembershipRole.ADMIN),
    )
    monkeypatch.setattr(
        organizations,
        "human_tenant",
        lambda *args, **kwargs: (SimpleNamespace(), SimpleNamespace(role=MembershipRole.ADMIN)),
    )
    repo = Mock()
    repo.get_membership.return_value = SimpleNamespace(role=MembershipRole.ADMIN)
    monkeypatch.setattr(organizations, "SqlTenancyRepository", lambda _: repo)
    service = Mock()
    monkeypatch.setattr(organizations, "_service", lambda _: service)
    response = client.patch(
        f"/api/v1/organizations/{uuid4()}/members/{uuid4()}",
        json={"role": "owner"},
    )
    assert response.status_code == 403
    service.update_membership.assert_not_called()


def test_admin_cannot_downgrade_existing_owner(client, monkeypatch):
    monkeypatch.setattr(
        organizations,
        "require_human_permission",
        lambda *args, **kwargs: SimpleNamespace(role=MembershipRole.ADMIN),
    )
    monkeypatch.setattr(
        organizations,
        "human_tenant",
        lambda *args, **kwargs: (SimpleNamespace(), SimpleNamespace(role=MembershipRole.ADMIN)),
    )
    repo = Mock()
    repo.get_membership.return_value = SimpleNamespace(role=MembershipRole.OWNER)
    monkeypatch.setattr(organizations, "SqlTenancyRepository", lambda _: repo)
    service = Mock()
    monkeypatch.setattr(organizations, "_service", lambda _: service)
    response = client.patch(
        f"/api/v1/organizations/{uuid4()}/members/{uuid4()}",
        json={"status": "revoked"},
    )
    assert response.status_code == 403
    service.update_membership.assert_not_called()


def test_owner_can_restore_suspended_organization(client, monkeypatch, actor):
    org_id = uuid4()
    organization = SimpleNamespace(
        id=org_id, name="Demo", slug="demo", status=OrganizationStatus.SUSPENDED
    )
    membership = SimpleNamespace(role=MembershipRole.OWNER)
    monkeypatch.setattr(
        organizations,
        "human_tenant",
        lambda *args, **kwargs: (organization, membership),
    )
    service = Mock()
    service.update_organization.return_value = SimpleNamespace(
        id=org_id, name="Demo", slug="demo", status=OrganizationStatus.ACTIVE
    )
    monkeypatch.setattr(organizations, "_service", lambda _: service)
    response = client.patch(f"/api/v1/organizations/{org_id}", json={"status": "active"})
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    service.update_organization.assert_called_once_with(
        actor=actor, organization_id=org_id, name=None, status=OrganizationStatus.ACTIVE
    )


def test_invitation_error_body_does_not_echo_secret(client):
    secret = "sensitive"
    response = client.post(
        "/api/v1/invitations/accept",
        json={
            "organization_id": str(uuid4()),
            "invitation_id": str(uuid4()),
            "secret": secret,
        },
    )
    assert response.status_code == 422
    assert secret not in response.text


def test_invitation_accept_requires_csrf(client, monkeypatch):
    client.headers.pop("X-OpenVietGIS-CSRF")
    service = Mock()
    monkeypatch.setattr(invitations, "_service", lambda _: service)
    response = client.post(
        "/api/v1/invitations/accept",
        json={
            "organization_id": str(uuid4()),
            "invitation_id": str(uuid4()),
            "secret": "synthetic-test-only-invitation-secret",
        },
    )
    assert response.status_code == 403
    service.accept.assert_not_called()


def test_wrong_invitation_returns_generic_error(client, monkeypatch):
    repo = Mock()
    repo.get_organization.return_value = SimpleNamespace(status=OrganizationStatus.ACTIVE)
    repo.get_membership_for_user.return_value = None
    monkeypatch.setattr(invitations, "SqlTenancyRepository", lambda _: repo)
    service = Mock()
    secret = "synthetic-test-only-invitation-secret"
    service.accept.side_effect = InvalidInvitationError(f"invalid {secret}")
    monkeypatch.setattr(invitations, "_service", lambda _: service)
    response = client.post(
        "/api/v1/invitations/accept",
        json={
            "organization_id": str(uuid4()),
            "invitation_id": str(uuid4()),
            "secret": secret,
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid invitation"}
    assert secret not in response.text
