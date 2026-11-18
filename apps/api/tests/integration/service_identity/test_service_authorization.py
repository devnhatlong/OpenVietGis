from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from openvietgis_api.main import create_app
from openvietgis_api.security.secrets import digest_secret
from openvietgis_api.security.sessions import issue_session_token
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world


def _client_for_user(user_id: UUID) -> TestClient:
    session_id = uuid4()
    raw_token, digest = issue_session_token(session_id)
    with get_admin_engine().begin() as connection:
        link_id = connection.execute(
            text("SELECT id FROM identity.identity_links WHERE user_id=:user"),
            {"user": user_id},
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO identity.web_sessions (
                    id, user_id, identity_link_id, secret_hash, issued_at, expires_at
                )
                VALUES (:id,:user,:link,:digest,now(),now()+interval '1 hour')
                """
            ),
            {
                "id": session_id,
                "user": user_id,
                "link": link_id,
                "digest": digest,
            },
        )
    client = TestClient(create_app())
    client.cookies.set("ovg_session", raw_token)
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    client.headers["X-OpenVietGIS-CSRF"] = csrf.json()["token"]
    return client


def _service_client(secret: str) -> TestClient:
    client = TestClient(create_app())
    client.headers["Authorization"] = "Bearer " + secret
    return client


def test_service_credential_allowed_scope_ceiling_cross_tenant_and_revocation(
    migrated_database: None,
) -> None:
    a, b = seed_access_world(), seed_access_world()
    root_a = f"/api/v1/organizations/{a.organization_id}"
    root_b = f"/api/v1/organizations/{b.organization_id}"

    with _client_for_user(a.owner_user_id) as owner:
        created = owner.post(
            f"{root_a}/service-principals",
            json={"name": "integration-check", "description": "P2 fixture"},
        )
        assert created.status_code == 201, created.text
        principal_id = created.json()["id"]

        grant = owner.post(
            f"{root_a}/grants",
            json={
                "subject_kind": "service_principal",
                "subject_id": principal_id,
                "scope_kind": "project",
                "project_id": str(a.project_id),
                "role": "viewer",
            },
        )
        assert grant.status_code == 201, grant.text
        unscoped = owner.post(
            f"{root_a}/projects",
            json={
                "name": "Unscoped project",
                "slug": f"unscoped-{uuid4().hex}",
                "workspace_id": str(a.workspace_a_id),
            },
        )
        assert unscoped.status_code == 201, unscoped.text
        unscoped_project_id = unscoped.json()["id"]

        too_wide = owner.post(
            f"{root_a}/service-principals/{principal_id}/credentials",
            json={
                "name": "too-wide",
                "permission_ceiling": ["project.read", "project.edit"],
            },
        )
        assert too_wide.status_code == 400, too_wide.text

        issued = owner.post(
            f"{root_a}/service-principals/{principal_id}/credentials",
            json={
                "name": "reader",
                "permission_ceiling": ["project.read"],
            },
        )
        assert issued.status_code == 201, issued.text
        credential_id = issued.json()["id"]
        secret = issued.json()["secret"]
        assert secret.startswith("ovgsvc")
        assert "secret_hash" not in issued.text
        with get_admin_engine().connect() as connection:
            stored = connection.execute(
                text(
                    "SELECT prefix, secret_hash, last_used_at "
                    "FROM org.service_credentials WHERE id=:id"
                ),
                {"id": credential_id},
            ).one()
        assert stored.prefix == secret[:20]
        assert bytes(stored.secret_hash) == digest_secret(secret)
        assert stored.last_used_at is None

        with _service_client(secret) as service:
            allowed = service.get(f"{root_a}/projects/{a.project_id}")
            assert allowed.status_code == 200, allowed.text
            assert allowed.json()["id"] == str(a.project_id)

            denied_edit = service.patch(
                f"{root_a}/projects/{a.project_id}",
                json={"name": "service-must-not-edit"},
            )
            assert denied_edit.status_code == 403, denied_edit.text

            out_of_scope = service.get(f"{root_a}/projects/{unscoped_project_id}")
            assert out_of_scope.status_code == 403, out_of_scope.text

            cross_tenant = service.get(f"{root_b}/projects/{b.project_id}")
            assert cross_tenant.status_code == 401
            assert cross_tenant.json()["detail"] == "invalid service credential"

        with get_admin_engine().connect() as connection:
            last_used_at = connection.execute(
                text("SELECT last_used_at FROM org.service_credentials WHERE id=:id"),
                {"id": credential_id},
            ).scalar_one()
        assert last_used_at is not None

        revoked = owner.post(
            f"{root_a}/service-principals/{principal_id}/credentials/"
            f"{credential_id}/revoke"
        )
        assert revoked.status_code == 204

        with _service_client(secret) as service:
            after_revoke = service.get(f"{root_a}/projects/{a.project_id}")
            assert after_revoke.status_code == 401

        second = owner.post(
            f"{root_a}/service-principals/{principal_id}/credentials",
            json={"name": "second", "permission_ceiling": ["project.read"]},
        )
        assert second.status_code == 201
        second_secret = second.json()["secret"]

        principal_revoke = owner.post(
            f"{root_a}/service-principals/{principal_id}/revoke"
        )
        assert principal_revoke.status_code == 204
        with _service_client(second_secret) as service:
            assert service.get(f"{root_a}/projects/{a.project_id}").status_code == 401


def test_service_principal_management_is_human_admin_only(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    root = f"/api/v1/organizations/{world.organization_id}"
    with _client_for_user(world.owner_user_id) as owner:
        created = owner.post(f"{root}/service-principals", json={"name": "admin-only"})
        assert created.status_code == 201
        principal_id = created.json()["id"]
        assert any(
            item["id"] == principal_id
            for item in owner.get(f"{root}/service-principals").json()
        )

        grant = owner.post(
            f"{root}/grants",
            json={
                "subject_kind": "service_principal",
                "subject_id": principal_id,
                "scope_kind": "project",
                "project_id": str(world.project_id),
                "role": "viewer",
            },
        )
        assert grant.status_code == 201
        issued = owner.post(
            f"{root}/service-principals/{principal_id}/credentials",
            json={"name": "reader", "permission_ceiling": ["project.read"]},
        )
        assert issued.status_code == 201

    with _service_client(issued.json()["secret"]) as service:
        denied = service.get(f"{root}/service-principals")
        assert denied.status_code == 401
        assert denied.json()["detail"] == "human session required"
