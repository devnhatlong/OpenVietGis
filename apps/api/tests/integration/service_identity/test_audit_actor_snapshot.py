from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.rls.test_cross_tenant_api import client_for_user


def _insert_snapshot_event(
    *,
    organization_id: UUID,
    actor_type: str,
    actor_id: UUID | None,
    snapshot: str,
    action: str,
) -> UUID:
    event_id = uuid4()
    with get_admin_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO audit.audit_events (
                    id, organization_id, actor_type, actor_id, actor_display_snapshot,
                    action, resource_type, resource_id, outcome, metadata, created_at
                )
                VALUES (
                    :id, :organization_id, :actor_type, :actor_id, :snapshot,
                    :action, 'fixture', NULL, 'success', '{}'::jsonb, :created_at
                )
                """
            ),
            {
                "id": event_id,
                "organization_id": organization_id,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "snapshot": snapshot,
                "action": action,
                "created_at": datetime.now(UTC),
            },
        )
    return event_id


def test_actor_snapshots_survive_human_and_service_revocation(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    root = f"/api/v1/organizations/{world.organization_id}"

    with client_for_user(world.owner_user_id) as owner:
        created = owner.post(
            f"{root}/service-principals",
            json={"name": f"snapshot-{uuid4().hex}", "description": "audit snapshot fixture"},
        )
        assert created.status_code == 201, created.text
        principal_id = UUID(created.json()["id"])

        human_event = _insert_snapshot_event(
            organization_id=world.organization_id,
            actor_type="human",
            actor_id=world.member_user_id,
            snapshot="Member before revoke",
            action="fixture.snapshot.human",
        )
        service_event = _insert_snapshot_event(
            organization_id=world.organization_id,
            actor_type="service_principal",
            actor_id=principal_id,
            snapshot="Automation before revoke",
            action="fixture.snapshot.service",
        )
        system_event = _insert_snapshot_event(
            organization_id=world.organization_id,
            actor_type="system",
            actor_id=None,
            snapshot="system:bootstrap",
            action="fixture.snapshot.system",
        )

        revoked_member = owner.patch(
            f"{root}/members/{world.member_membership_id}",
            json={"status": "revoked"},
        )
        assert revoked_member.status_code == 200, revoked_member.text
        revoked_service = owner.post(
            f"{root}/service-principals/{principal_id}/revoke"
        )
        assert revoked_service.status_code == 204, revoked_service.text

        response = owner.get(f"{root}/audit-events", params={"limit": 200})
        assert response.status_code == 200, response.text
        by_id = {row["id"]: row for row in response.json()}

    assert by_id[str(human_event)]["actor_type"] == "human"
    assert by_id[str(human_event)]["actor_display_snapshot"] == "Member before revoke"
    assert by_id[str(service_event)]["actor_type"] == "service_principal"
    assert by_id[str(service_event)]["actor_display_snapshot"] == "Automation before revoke"
    assert by_id[str(system_event)]["actor_type"] == "system"
    assert by_id[str(system_event)]["actor_display_snapshot"] == "system:bootstrap"
