from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.maps.domain import (
    Configuration,
    SaveIntent,
    Viewpoint,
    ViewpointIntent,
)
from openvietgis_api.domains.maps.ports import (
    MapIntentConflictError,
    MapNoChangesError,
    MapRevisionConflictError,
)
from openvietgis_api.domains.maps.service import MapService


class MemoryRepository:
    def __init__(self):
        self.state = None
        self.operations = {}
        self.changes = []
        self.preparations = []
        self.allowed = True

    def prepare_scope(self, *, context, permission, mutation):
        self.preparations.append((permission, mutation))
        if not self.allowed:
            raise PermissionError("current authority denied")

    def get_map(self, *, context, lock=False):
        return self.state

    def get_operation(self, *, context, operation_id):
        return self.operations.get(operation_id)

    def validate_references(self, *, context, configuration):
        pass

    def commit_save(self, *, context, state, operation, revision, audit, expected_revision):
        self.state = state
        self.operations[operation.operation_id] = operation
        self.changes.append((revision, audit))

    def list_history(self, *, context, after_revision, limit):
        changes = [change[0] for change in reversed(self.changes)]
        return [
            c
            for c in changes
            if after_revision is None or c.configuration_revision < after_revision
        ][:limit]


def context():
    return AuthorizationContext(Actor("human", uuid4(), "Editor"), uuid4(), project_id=uuid4())


def intent(expected=0):
    return SaveIntent(uuid4(), expected, (), "grid", ViewpointIntent("preserve"))


def test_unsaved_get_is_virtual_and_first_empty_save_commits_once():
    repo, ctx = MemoryRepository(), context()
    service = MapService(repo)
    assert service.get_map(context=ctx).configuration_revision == 0
    assert repo.state is None
    command = intent()
    receipt = service.save(context=ctx, intent=command)
    assert receipt.configuration_revision == 1
    assert len(repo.changes) == 1
    assert service.save(context=ctx, intent=command) == receipt
    assert len(repo.changes) == 1


def test_lost_ack_replays_original_receipt_even_after_newer_save():
    repo, ctx = MemoryRepository(), context()
    service = MapService(repo)
    first = intent()
    receipt = service.save(context=ctx, intent=first)
    newer = replace(intent(1), viewpoint=ViewpointIntent("set", Viewpoint(106, 11, 8, 0, 0)))
    service.save(context=ctx, intent=newer)
    assert service.save(context=ctx, intent=first) == receipt
    assert repo.state.configuration_revision == 2 and len(repo.changes) == 2


def test_operation_reuse_changed_intent_or_foreign_actor_never_returns_receipt():
    repo, ctx = MemoryRepository(), context()
    service = MapService(repo)
    first = intent()
    service.save(context=ctx, intent=first)
    with pytest.raises(MapIntentConflictError):
        service.save(context=ctx, intent=replace(first, expected_revision=1))
    foreign = replace(ctx, actor=Actor("human", uuid4(), "Other"))
    with pytest.raises(MapIntentConflictError):
        service.save(context=foreign, intent=first)


def test_replay_and_receipt_lookup_recheck_current_edit_authority():
    repo, ctx = MemoryRepository(), context()
    service = MapService(repo)
    first = intent()
    service.save(context=ctx, intent=first)
    repo.allowed = False
    with pytest.raises(PermissionError):
        service.save(context=ctx, intent=first)
    with pytest.raises(PermissionError):
        service.operation(context=ctx, operation_id=first.operation_id)
    assert repo.preparations[-1] == (Permission.PROJECT_EDIT, True)


def test_new_stale_and_noop_operations_preserve_prior_revision():
    repo, ctx = MemoryRepository(), context()
    service = MapService(repo)
    service.save(context=ctx, intent=intent())
    with pytest.raises(MapRevisionConflictError):
        service.save(context=ctx, intent=intent(0))
    with pytest.raises(MapNoChangesError):
        service.save(context=ctx, intent=intent(1))
    assert repo.state.configuration_revision == 1 and len(repo.changes) == 1


def test_immutable_history_has_attributable_before_after_and_safe_audit_link():
    repo, ctx = MemoryRepository(), context()
    service = MapService(repo)
    service.save(context=ctx, intent=intent())
    change, audit = repo.changes[0]
    assert change.before_configuration is None
    assert change.after_configuration == Configuration()
    assert change.actor_id == ctx.actor.actor_id
    assert change.audit_event_id == audit.id
    assert audit.resource_type == "project_map"
    assert audit.resource_id == change.map_id
    assert audit.metadata == {
        "project_id": str(ctx.project_id),
        "operation_id": str(change.operation_id),
        "configuration_revision": 1,
    }
