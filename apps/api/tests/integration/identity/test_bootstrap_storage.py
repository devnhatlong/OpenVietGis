from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.platform_repository import SqlPlatformRepository
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.identity.test_bootstrap import uninitialized as uninitialized


def test_installation_state_lock_and_immutable_transition(uninitialized: None) -> None:
    world = seed_access_world()
    now = datetime.now(UTC)
    with get_session_factory()() as session:
        repository = SqlPlatformRepository(session)
        original = repository.get_installation_state(for_update=True)
        assert original.initialized_at is None
        assert not repository.is_initialized()
        initialized = repository.mark_initialized(
            organization_id=world.organization_id, user_id=world.owner_user_id, now=now
        )
        assert initialized.initialized_at == now
        assert initialized.initial_organization_id == world.organization_id
        assert initialized.initialized_by_user_id == world.owner_user_id
        session.commit()

    with get_session_factory()() as session:
        repository = SqlPlatformRepository(session)
        assert repository.is_initialized()
        with pytest.raises(RuntimeError, match="installation already initialized"):
            repository.mark_initialized(
                organization_id=world.organization_id,
                user_id=world.member_user_id,
                now=datetime.now(UTC),
            )
        session.rollback()
        assert repository.get_installation_state() == initialized
