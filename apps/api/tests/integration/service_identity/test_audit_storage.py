from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.rls.test_cross_tenant_api import client_for_user


def _insert_event(
    *,
    organization_id: UUID,
    actor_id: UUID | None,
    action: str,
    created_at: datetime,
    actor_type: str = "human",
    snapshot: str = "fixture-actor",
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
                "created_at": created_at,
            },
        )
    return event_id


def test_audit_read_is_authorized_tenant_scoped_and_deterministically_ordered(
    migrated_database: None,
) -> None:
    a, b = seed_access_world(), seed_access_world()
    now = datetime.now(UTC)
    old_a = _insert_event(
        organization_id=a.organization_id,
        actor_id=a.owner_user_id,
        action="fixture.old-a",
        created_at=now - timedelta(seconds=2),
    )
    new_a = _insert_event(
        organization_id=a.organization_id,
        actor_id=a.owner_user_id,
        action="fixture.new-a",
        created_at=now - timedelta(seconds=1),
    )
    foreign_b = _insert_event(
        organization_id=b.organization_id,
        actor_id=b.owner_user_id,
        action="fixture.foreign-b",
        created_at=now,
    )

    root_a = f"/api/v1/organizations/{a.organization_id}"
    with client_for_user(a.owner_user_id) as owner:
        limited = owner.get(f"{root_a}/audit-events", params={"limit": 1})
        assert limited.status_code == 200, limited.text
        assert [row["id"] for row in limited.json()] == [str(new_a)]

        full = owner.get(f"{root_a}/audit-events", params={"limit": 200})
        assert full.status_code == 200, full.text
        ids = [row["id"] for row in full.json()]
        assert str(new_a) in ids
        assert str(old_a) in ids
        assert str(foreign_b) not in ids
        assert ids.index(str(new_a)) < ids.index(str(old_a))

        foreign = owner.get(f"/api/v1/organizations/{b.organization_id}/audit-events")
        assert foreign.status_code == 404

    with client_for_user(a.member_user_id) as member:
        denied = member.get(f"{root_a}/audit-events")
        assert denied.status_code == 403
