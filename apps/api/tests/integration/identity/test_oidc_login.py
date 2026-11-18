from __future__ import annotations

from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from tools.test_database import assert_safe_test_target

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


def test_oidc_authorization_redirect_contains_state_nonce_and_pkce() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/auth/login/keycloak",
            params={"return_to": "/organizations"},
            follow_redirects=False,
        )

    assert response.status_code in {302, 307}
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "127.0.0.1:18080"
    assert parsed.path.endswith("/protocol/openid-connect/auth")
    assert query["client_id"] == ["openvietgis-web"]
    assert query["redirect_uri"] == ["http://127.0.0.1:8000/api/v1/auth/callback/keycloak"]
    assert query["state"][0]
    assert query["nonce"][0]
    assert query["code_challenge"][0]
    assert query["code_challenge_method"] == ["S256"]
    assert "ovg_oidc_state" in response.cookies


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
