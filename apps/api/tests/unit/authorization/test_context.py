from uuid import uuid4

import pytest

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


def test_service_requested_context_preserves_exact_credential_identity() -> None:
    context = RequestedActorContext(
        actor_type="service_principal",
        actor_id=uuid4(),
        organization_id=uuid4(),
        credential_id=uuid4(),
        project_id=uuid4(),
    )
    payload = context.to_payload()
    assert RequestedActorContext.from_payload(payload) == context
    assert set(payload) == {
        "actor_type", "actor_id", "organization_id", "workspace_id",
        "project_id", "credential_id",
    }
    with pytest.raises(ValueError, match="credential_id"):
        RequestedActorContext.from_payload({**payload, "credential_id": None})
    with pytest.raises(ValueError, match="credential_id"):
        RequestedActorContext.from_payload({**payload, "actor_type": "human"})
