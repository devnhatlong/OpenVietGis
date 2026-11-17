from uuid import uuid4

from openvietgis_api.domains.authorization.context import RequestedActorContext


def test_requested_actor_context_round_trip_has_no_permission_snapshot() -> None:
    context = RequestedActorContext(
        actor_type="human",
        actor_id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
    )

    payload = context.to_payload()
    restored = RequestedActorContext.from_payload(payload)

    assert restored == context
    assert "permissions" not in payload
