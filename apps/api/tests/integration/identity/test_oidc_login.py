from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from authlib.integrations.starlette_client import StarletteOAuth2App
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from tools.test_database import assert_safe_test_target

from openvietgis_api.adapters.http.security import get_db_session
from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.identity_repository import SqlIdentityRepository
from openvietgis_api.adapters.persistence.rls import set_request_context
from openvietgis_api.config import get_settings
from openvietgis_api.domains.identity.domain import User, UserStatus
from openvietgis_api.domains.identity.service import (
    ExternalIdentityClaims,
    IdentityConflictError,
    IdentityService,
)
from openvietgis_api.main import create_app


def _assert_configured_login_redirect(client: TestClient) -> None:
    settings = get_settings()
    provider = settings.oidc_providers["keycloak"]
    expected = urlparse(provider.issuer.rstrip("/") + "/protocol/openid-connect/auth")
    response = client.get(
        "/api/v1/auth/login/keycloak",
        params={"return_to": "/organizations"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert (parsed.scheme, parsed.netloc, parsed.path) == (
        expected.scheme,
        expected.netloc,
        expected.path,
    )
    assert query["client_id"] == [provider.client_id]
    assert query["redirect_uri"] == [
        settings.api_public_base_url.rstrip("/") + "/api/v1/auth/callback/keycloak"
    ]
    assert query["state"][0]
    assert query["nonce"][0]
    assert query["code_challenge"][0]
    assert query["code_challenge_method"] == ["S256"]
    assert "ovg_oidc_state" in response.cookies


def test_oidc_authorization_redirect_contains_state_nonce_and_pkce() -> None:
    # Exercise actual configured provider discovery; no fixed shared port.
    with TestClient(create_app()) as client:
        _assert_configured_login_redirect(client)


@pytest.mark.parametrize("oidc_port,api_port", [(18080, 8000), (18086, 18085)])
def test_redirect_fixture_supports_isolated_loopback_profiles(
    monkeypatch: pytest.MonkeyPatch, oidc_port: int, api_port: int
) -> None:
    # Pure variant: only external provider discovery is replaced. Authlib's real
    # redirect, state, nonce, PKCE and cookie code still runs; no service/DB needed.
    issuer = f"http://127.0.0.1:{oidc_port}/realms/openvietgis"
    monkeypatch.setenv("OPENVIETGIS_API_PUBLIC_BASE_URL", f"http://127.0.0.1:{api_port}")
    monkeypatch.setenv(
        "OPENVIETGIS_OIDC_PROVIDERS",
        json.dumps(
            {
                "keycloak": {
                    "issuer": issuer,
                    "client_id": "isolated-test",
                    "display_name": "Fixture",
                }
            }
        ),
    )
    get_settings.cache_clear()

    async def discovery(client):
        assert client._server_metadata_url == issuer + "/.well-known/openid-configuration"
        return {
            "issuer": issuer,
            "authorization_endpoint": issuer + "/protocol/openid-connect/auth",
        }

    monkeypatch.setattr(StarletteOAuth2App, "load_server_metadata", discovery)
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: None
    try:
        with TestClient(app) as client:
            _assert_configured_login_redirect(client)
    finally:
        get_settings.cache_clear()


def test_identity_link_conflict_and_link_unlink_are_audited(
    migrated_database: None,
) -> None:
    migration_url = get_settings().migration_db_url
    assert_safe_test_target(migration_url)
    engine = create_engine(migration_url)
    session = Session(engine)
    try:
        repository = SqlIdentityRepository(session)
        audit = SqlAuditRepository(session)
        service = IdentityService(repository, audit)
        primary = ExternalIdentityClaims(
            issuer="https://issuer.example",
            subject=f"primary-{uuid4()}",
            display_name="Primary User",
            email="primary@example.test",
            email_verified=True,
        )
        login = service.login(primary, session_ttl_seconds=3600)
        set_request_context(session, organization_id=None, actor_user_id=login.user.id)
        second = ExternalIdentityClaims(
            issuer="https://issuer.example",
            subject=f"second-{uuid4()}",
            display_name="Primary User",
            email="primary@example.test",
            email_verified=True,
        )
        linked = service.link_identity(user_id=login.user.id, claims=second)

        other_user = User(
            id=uuid4(),
            display_name="Other User",
            email_snapshot="other@example.test",
            status=UserStatus.ACTIVE,
            created_at=login.user.created_at,
            updated_at=login.user.updated_at,
        )
        session.execute(
            text(
                """
                INSERT INTO identity.users (
                    id, display_name, email_snapshot, status, created_at, updated_at
                )
                VALUES (
                    :id, :display_name, :email_snapshot, :status, :created_at, :updated_at
                )
                """
            ),
            {
                "id": other_user.id,
                "display_name": other_user.display_name,
                "email_snapshot": other_user.email_snapshot,
                "status": other_user.status.value,
                "created_at": other_user.created_at,
                "updated_at": other_user.updated_at,
            },
        )

        with pytest.raises(IdentityConflictError):
            service.link_identity(user_id=other_user.id, claims=primary)

        service.unlink_identity(
            user_id=login.user.id,
            identity_link_id=linked.id,
        )
        actions = set(
            session.execute(
                text(
                    """
                    SELECT action
                    FROM audit.audit_events
                    WHERE actor_id = :user_id
                    """
                ),
                {"user_id": login.user.id},
            ).scalars()
        )
        assert {"identity.link", "identity.unlink"} <= actions
        session.commit()
    finally:
        session.close()
        engine.dispose()
