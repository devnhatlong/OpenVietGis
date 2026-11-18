from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.rls.test_cross_tenant_api import client_for_user


@contextmanager
def _private_runtime_logs() -> Iterator[io.StringIO]:
    """Keep synthetic credential regressions out of pytest's report/log handlers."""
    root = logging.getLogger()
    previous_handlers, previous_level = root.handlers, root.level
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    try:
        yield stream
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)
        handler.close()
        stream.close()


def test_private_runtime_logs_are_not_forwarded(caplog: pytest.LogCaptureFixture) -> None:
    with _private_runtime_logs() as captured:
        logging.getLogger("openvietgis.synthetic").warning("synthetic-fixture-marker")
        assert "synthetic-fixture-marker" in captured.getvalue()
    assert "synthetic-fixture-marker" not in caplog.text


def test_p1_sensitive_mutations_append_durable_actor_attributed_audit(
    migrated_database: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with _private_runtime_logs() as captured:
        try:
            _exercise_sensitive_mutations(captured, capsys)
        finally:
            # Drain private captured stdout/stderr even if a preceding assertion failed.
            capsys.readouterr()


def _exercise_sensitive_mutations(
    captured: io.StringIO,
    capsys: pytest.CaptureFixture[str],
) -> None:
    world = seed_access_world()
    with get_admin_engine().begin() as connection:
        original_state = dict(
            connection.execute(
                text("""
                SELECT initialized_at, initial_organization_id, initialized_by_user_id,
                       updated_at
                FROM platform.installation_state WHERE singleton_key = 'installation'
            """)
            )
            .mappings()
            .one()
        )
        connection.execute(
            text("""
                UPDATE platform.installation_state
                SET initialized_at = now(), initial_organization_id = :org,
                    initialized_by_user_id = :actor, updated_at = now()
                WHERE singleton_key = 'installation'
            """),
            {"org": world.organization_id, "actor": world.owner_user_id},
        )
    try:
        with (
            client_for_user(world.owner_user_id) as owner,
            client_for_user(world.member_user_id) as member,
            client_for_user(world.wrong_user_id) as recipient,
        ):
            canaries = tuple(
                value
                for client in (owner, member, recipient)
                for value in (
                    client.cookies.get("ovg_session"),
                    client.headers.get("X-OpenVietGIS-CSRF"),
                )
                if value
            )
            assert len(canaries) == 6
            # Check both complete cookies and their raw secret fragments.
            canaries += tuple(
                value.split(".", 1)[1]
                for value in canaries
                if value.startswith("ovgs_") and "." in value
            )
            created = owner.post(
                "/api/v1/organizations",
                json={
                    "name": "Audit fixture",
                    "slug": f"audit-{uuid4().hex}",
                },
            )
            assert created.status_code == 201
            org_id = created.json()["organization"]["id"]
            owner_membership = created.json()["owner_membership"]["id"]
            root = f"/api/v1/organizations/{org_id}"
            project = owner.post(
                f"{root}/projects",
                json={
                    "name": "Audit fixture project",
                    "slug": f"audit-project-{uuid4().hex}",
                },
            )
            assert project.status_code == 201
            project_id = project.json()["id"]

            issued = owner.post(
                f"{root}/invitations",
                json={
                    "target": {"kind": "user", "user_id": str(world.member_user_id)},
                    "organization_role": "admin",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    "resource_grant": {
                        "scope_kind": "project",
                        "project_id": project_id,
                        "role": "viewer",
                    },
                },
            )
            assert issued.status_code == 201
            invite_id = issued.json()["id"]
            accepted_secret = issued.json()["secret"]
            accepted = member.post(
                "/api/v1/invitations/accept",
                json={
                    "organization_id": org_id,
                    "invitation_id": invite_id,
                    "secret": accepted_secret,
                },
            )
            assert accepted.status_code == 200
            membership_id = accepted.json()["membership"]["id"]
            bundled_grant_id = accepted.json()["grant"]["id"]

            grant = owner.post(
                f"{root}/grants",
                json={
                    "subject_kind": "membership",
                    "subject_id": membership_id,
                    "scope_kind": "organization",
                    "role": "viewer",
                },
            )
            assert grant.status_code == 201
            grant_id = grant.json()["id"]
            assert owner.post(f"{root}/grants/{grant_id}/revoke").status_code == 204
            assert owner.post(f"{root}/grants/{bundled_grant_id}/revoke").status_code == 204

            pending = owner.post(
                f"{root}/invitations",
                json={
                    "target": {"kind": "user", "user_id": str(world.wrong_user_id)},
                    "organization_role": "guest",
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            )
            assert pending.status_code == 201
            pending_id = pending.json()["id"]
            pending_secret = pending.json()["secret"]
            assert owner.post(f"{root}/invitations/{pending_id}/revoke").status_code == 204
            assert (
                recipient.post(
                    "/api/v1/invitations/accept",
                    json={
                        "organization_id": org_id,
                        "invitation_id": pending_id,
                        "secret": pending_secret,
                    },
                ).status_code
                == 400
            )

            # Same-tenant Admin has member-management authority, not owner-transfer authority.
            rejected = member.post(
                f"{root}/ownership-transfer",
                json={
                    "target_membership_id": membership_id,
                },
            )
            assert rejected.status_code == 403
            assert owner.get(f"{root}/members").status_code == 200
            assert any(
                row["id"] == owner_membership and row["role"] == "owner"
                for row in owner.get(f"{root}/members").json()
            )

            for status in ("suspended", "active"):
                response = owner.patch(
                    f"{root}/members/{membership_id}",
                    json={
                        "status": status,
                    },
                )
                assert response.status_code == 200
            for status in ("suspended", "active", "deleted", "active"):
                assert owner.patch(root, json={"status": status}).status_code == 200

            transferred = owner.post(
                f"{root}/ownership-transfer",
                json={
                    "target_membership_id": membership_id,
                },
            )
            assert transferred.status_code == 200
            assert transferred.json()["new_owner"]["id"] == membership_id
            assert (
                member.patch(
                    f"{root}/members/{owner_membership}",
                    json={
                        "status": "revoked",
                    },
                ).status_code
                == 200
            )
            assert owner.get(root).status_code == 404

        # Check committed events after the original actor loses its membership.
        with get_admin_engine().connect() as connection:
            events = (
                connection.execute(
                    text("""
                    SELECT actor_type, actor_id, actor_display_snapshot, action, outcome,
                           resource_id, metadata
                    FROM audit.audit_events WHERE organization_id = :org
                """),
                    {"org": org_id},
                )
                .mappings()
                .all()
            )
        canaries += (accepted_secret, pending_secret)
        raw_audit = json.dumps([dict(event) for event in events], default=str)
        if any(secret in raw_audit for secret in canaries):
            pytest.fail("P1 audit contains a synthetic credential", pytrace=False)
        output = capsys.readouterr()
        if any(
            secret in surface
            for secret in canaries
            for surface in (captured.getvalue(), output.out, output.err)
        ):
            pytest.fail("P1 runtime log contains a synthetic credential", pytrace=False)
        assert events
        for event in events:
            assert event["actor_type"] == "human"
            assert event["actor_id"] in {
                world.owner_user_id,
                world.member_user_id,
                world.wrong_user_id,
            }
            assert event["actor_display_snapshot"]

        def matching(action: str, resource_id: str, actor: UUID) -> list:
            return [
                event
                for event in events
                if event["action"] == action
                and event["outcome"] == "success"
                and event["resource_id"] == UUID(resource_id)
                and event["actor_id"] == actor
            ]

        assert matching("organization.create", org_id, world.owner_user_id)
        statuses = {
            event["metadata"]["status"]
            for event in matching("organization.update", org_id, world.owner_user_id)
        }
        assert statuses == {"suspended", "active", "deleted"}
        member_updates = matching(
            "organization.membership.update", membership_id, world.owner_user_id
        )
        assert {event["metadata"]["status"] for event in member_updates} == {
            "suspended",
            "active",
        }
        assert matching("organization.membership.update", owner_membership, world.member_user_id)
        assert matching("organization.owner.transfer", membership_id, world.owner_user_id)
        assert matching("invitation.create", invite_id, world.owner_user_id)
        assert matching("invitation.create", pending_id, world.owner_user_id)
        assert matching("invitation.revoke", pending_id, world.owner_user_id)
        accepts = matching("invitation.accept", invite_id, world.member_user_id)
        assert len(accepts) == 1
        assert accepts[0]["metadata"]["membership_id"] == membership_id
        assert accepts[0]["metadata"]["grant_id"] == bundled_grant_id
        bundled = matching("authorization.grant.create", bundled_grant_id, world.member_user_id)
        assert len(bundled) == 1
        assert bundled[0]["metadata"]["invitation_id"] == invite_id
        assert matching("authorization.grant.create", grant_id, world.owner_user_id)
        assert matching("authorization.grant.revoke", grant_id, world.owner_user_id)
        assert matching("authorization.grant.revoke", bundled_grant_id, world.owner_user_id)
        denied = [
            event
            for event in events
            if event["action"] == "organization.owner.transfer"
            and event["outcome"] == "denied"
            and event["actor_id"] == world.member_user_id
        ]
        assert len(denied) == 1
        assert denied[0]["resource_id"] is None
    finally:
        # The test-only installation singleton is restored for unrelated scenarios.
        with get_admin_engine().begin() as connection:
            connection.execute(
                text("""
                    UPDATE platform.installation_state
                    SET initialized_at = :initialized_at,
                        initial_organization_id = :initial_organization_id,
                        initialized_by_user_id = :initialized_by_user_id,
                        updated_at = :updated_at
                    WHERE singleton_key = 'installation'
                """),
                original_state,
            )
