from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from openvietgis_api.adapters.persistence.identity_repository import SqlIdentityRepository
from openvietgis_api.domains.audit.ports import AuditRepository
from openvietgis_api.domains.identity.service import ExternalIdentityClaims, IdentityService
from openvietgis_api.main import create_app
from tests.fixtures.db_admin import get_admin_engine, get_admin_session_factory


class NullAuditRepository(AuditRepository):
    def append(self, event: object) -> None:
        del event


def _authenticated_client() -> tuple[TestClient, str]:
    session = get_admin_session_factory()()
    try:
        service = IdentityService(
            SqlIdentityRepository(session),
            NullAuditRepository(),
        )
        result = service.login(
            ExternalIdentityClaims(
                issuer="https://issuer.example",
                subject=f"multi-org-{uuid4()}",
                display_name="Multi Org User",
                email="multi-org@example.test",
                email_verified=True,
            ),
            session_ttl_seconds=3600,
        )
        session.commit()
    finally:
        session.close()

    client = TestClient(create_app())
    client.cookies.set("ovg_session", result.session_token)
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    return client, csrf.json()["token"]


def _set_initialized_for_user(user_id: str) -> None:
    initial_org = uuid4()
    initial_membership = uuid4()
    with get_admin_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO org.organizations (
                    id, name, slug, status, created_by_actor_type,
                    created_by_actor_id, created_at, updated_at
                )
                VALUES (
                    :org_id, 'Initial Org', :slug, 'active', 'human',
                    :user_id, now(), now()
                )
                """
            ),
            {
                "org_id": initial_org,
                "slug": f"initial-{initial_org.hex}",
                "user_id": user_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO org.organization_memberships (
                    id, organization_id, user_id, role, status,
                    created_at, activated_at
                )
                VALUES (
                    :membership_id, :org_id, :user_id, 'owner', 'active',
                    now(), now()
                )
                """
            ),
            {
                "membership_id": initial_membership,
                "org_id": initial_org,
                "user_id": user_id,
            },
        )
        connection.execute(
            text(
                """
                UPDATE platform.installation_state
                SET initialized_at = :now,
                    initial_organization_id = :org_id,
                    initialized_by_user_id = :user_id,
                    updated_at = :now
                WHERE singleton_key = 'installation'
                """
            ),
            {
                "now": datetime.now(UTC),
                "org_id": initial_org,
                "user_id": user_id,
            },
        )


def test_normal_organization_create_requires_initialized_installation_and_creates_owner(
    migrated_database: None,
) -> None:
    with get_admin_engine().begin() as connection:
        connection.execute(
            text(
                """
                UPDATE platform.installation_state
                SET initialized_at = NULL,
                    initial_organization_id = NULL,
                    initialized_by_user_id = NULL,
                    updated_at = now()
                WHERE singleton_key = 'installation'
                """
            )
        )

    client, csrf = _authenticated_client()
    try:
        me = client.get("/api/v1/me")
        assert me.status_code == 200
        user_id = me.json()["id"]

        blocked = client.post(
            "/api/v1/organizations",
            headers={"X-OpenVietGIS-CSRF": csrf},
            json={"name": "Blocked Org", "slug": f"blocked-{uuid4().hex}"},
        )
        assert blocked.status_code == 409

        _set_initialized_for_user(user_id)

        created_ids: list[str] = []
        for index in range(2):
            response = client.post(
                "/api/v1/organizations",
                headers={"X-OpenVietGIS-CSRF": csrf},
                json={
                    "name": f"Organization {index}",
                    "slug": f"organization-{index}-{uuid4().hex}",
                },
            )
            assert response.status_code == 201, response.text
            payload = response.json()
            assert payload["owner_membership"]["role"] == "owner"
            assert payload["owner_membership"]["status"] == "active"
            assert payload["owner_membership"]["user_id"] == user_id
            created_ids.append(payload["organization"]["id"])

        organizations = client.get("/api/v1/me/organizations")
        assert organizations.status_code == 200
        orgs = organizations.json()
        assert len(orgs) >= 3
        assert set(created_ids) <= {item["id"] for item in orgs}
        assert all(item["role"] == "owner" for item in orgs)

        with get_admin_engine().connect() as connection:
            audited = set(
                connection.execute(
                    text(
                        """
                        SELECT resource_id
                        FROM audit.audit_events
                        WHERE actor_id = :user_id
                          AND action = 'organization.create'
                        """
                    ),
                    {"user_id": user_id},
                ).scalars()
            )
        assert {__import__("uuid").UUID(value) for value in created_ids} <= audited
    finally:
        client.close()
