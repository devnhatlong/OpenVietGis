from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from openvietgis_api.adapters.http.projects import UpdateProjectRequest
from openvietgis_api.adapters.http.workspaces import UpdateWorkspaceRequest
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlEffectivePermissionProvider,
    SqlResourceGrantRepository,
)
from openvietgis_api.adapters.persistence.rls import (
    bind_authenticated_actor,
    require_invitation_context,
    require_member_context,
    set_request_context,
)
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import (
    Actor,
    AuthorizationContext,
    InvitationAcceptanceContext,
)
from openvietgis_api.domains.authorization.roles import (
    ORGANIZATION_ROLE_PERMISSIONS,
    RESOURCE_ROLE_PERMISSIONS,
)
from openvietgis_api.domains.authorization.service import TenantResourceNotFoundError
from openvietgis_api.domains.tenancy.domain import InvitationStatus, MembershipRole, ResourceRole


@pytest.fixture
def context():
    return AuthorizationContext(Actor("human", uuid4(), "Actor"), uuid4())


@pytest.fixture
def session():
    session = Mock()
    session.info = {}
    session.get_transaction.return_value = object()
    session.get_nested_transaction.return_value = None
    session.execute.return_value.scalar_one_or_none.return_value = uuid4()
    return session


def test_required_context_and_foreign_org_rejected_before_sql(session, context):
    repo = SqlTenancyRepository(session)
    with pytest.raises(TypeError):
        repo.list_workspaces(context.organization_id)
    with pytest.raises(TenantResourceNotFoundError):
        repo.list_workspaces(uuid4(), context=context)
    session.execute.assert_not_called()


def test_raw_tenant_setting_never_proves_membership(session, context):
    set_request_context(
        session, organization_id=context.organization_id, actor_user_id=context.actor.actor_id
    )
    session.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(TenantResourceNotFoundError):
        require_member_context(session, context, context.organization_id)


def test_transaction_pin_blocks_raw_scope_switch(session, context):
    bind_authenticated_actor(session, context.actor)
    require_member_context(session, context, context.organization_id)
    with pytest.raises(PermissionError):
        set_request_context(session, organization_id=context.organization_id, actor_user_id=uuid4())
    with pytest.raises(TenantResourceNotFoundError):
        set_request_context(session, organization_id=uuid4(), actor_user_id=context.actor.actor_id)
    set_request_context(session, organization_id=None, actor_user_id=context.actor.actor_id)
    other_org = uuid4()
    with pytest.raises(TenantResourceNotFoundError):
        require_member_context(session, AuthorizationContext(context.actor, other_org), other_org)


def test_transaction_reset_requires_new_membership_check(session, context):
    bind_authenticated_actor(session, context.actor)
    require_member_context(session, context, context.organization_id)
    session.get_transaction.return_value = object()
    session.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(TenantResourceNotFoundError):
        require_member_context(session, context, context.organization_id)


def test_savepoint_transition_invalidates_membership_proof(session, context):
    bind_authenticated_actor(session, context.actor)
    require_member_context(session, context, context.organization_id)
    session.get_nested_transaction.return_value = object()
    session.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(TenantResourceNotFoundError):
        require_member_context(session, context, context.organization_id)


def test_invitation_context_is_exact_id_and_never_member_authorization(session, context):
    invite = InvitationAcceptanceContext(context.actor, context.organization_id, uuid4())
    with pytest.raises(TenantResourceNotFoundError):
        require_invitation_context(session, invite, context.organization_id, invitation_id=uuid4())
    with pytest.raises(PermissionError):
        require_invitation_context(session, invite, context.organization_id, require_verified=True)
    with pytest.raises(PermissionError):
        SqlResourceGrantRepository(session).list_for_organization(
            context.organization_id, context=invite
        )
    with pytest.raises(PermissionError):
        SqlTenancyRepository(session).list_workspaces(context.organization_id, context=invite)
    session.execute.assert_not_called()


@pytest.mark.parametrize("scope", ["project", "workspace", "mismatch", "inactive"])
def test_effective_permissions_do_not_inherit_for_missing_or_mismatched_scope(
    session, context, scope
):
    require_member_context(session, context, context.organization_id)
    session.reset_mock()
    session.execute.return_value.mappings.return_value.all.return_value = []
    scoped = AuthorizationContext(
        context.actor,
        context.organization_id,
        workspace_id=uuid4() if scope != "project" else None,
        project_id=uuid4() if scope not in ("workspace", "inactive") else None,
    )
    assert SqlEffectivePermissionProvider(session).resolve(scoped) == frozenset()

    session.execute.assert_called_once()
    statement, params = session.execute.call_args.args
    assert params["organization_id"] == context.organization_id
    assert params["user_id"] == context.actor.actor_id
    assert params["workspace_id"] == scoped.workspace_id
    assert params["project_id"] == scoped.project_id
    sql = str(statement)
    # Scope validity is part of the same query as role selection, not a
    # separate lookup that may observe an incompatible project placement.
    for predicate in (
        "m.status = 'active'",
        "o.status = 'active'",
        "p.organization_id = r.organization_id",
        "w.organization_id = r.organization_id",
        "p.id IS NOT NULL",
        "r.workspace_id = p.workspace_id",
        "w.id IS NOT NULL",
        "g.organization_id = r.organization_id",
        "g.membership_id = m.id",
        "g.revoked_at IS NULL",
        "WHEN r.project_id IS NOT NULL THEN p.workspace_id",
    ):
        assert predicate in sql


def test_effective_permissions_union_multiple_grants_without_decision_cache(session, context):
    require_member_context(session, context, context.organization_id)
    provider = SqlEffectivePermissionProvider(session)
    result = session.execute.return_value.mappings.return_value.all
    result.return_value = [
        {"membership_role": "member", "grant_role": "viewer"},
        {"membership_role": "member", "grant_role": "manager"},
    ]
    session.reset_mock()
    assert provider.resolve(context) == (
        ORGANIZATION_ROLE_PERMISSIONS[MembershipRole.MEMBER]
        | RESOURCE_ROLE_PERMISSIONS[ResourceRole.VIEWER]
        | RESOURCE_ROLE_PERMISSIONS[ResourceRole.MANAGER]
    )
    session.execute.assert_called_once()

    # A new decision in the same authorization-bound transaction must still
    # query membership, organization, placement and grants. No grant rows
    # still gives the organization-role permissions from the LEFT JOIN.
    result.return_value = [{"membership_role": "member", "grant_role": None}]
    assert provider.resolve(context) == ORGANIZATION_ROLE_PERMISSIONS[MembershipRole.MEMBER]
    assert session.execute.call_count == 2

    result.return_value = []
    assert provider.resolve(context) == frozenset()
    assert session.execute.call_count == 3


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"status": None}])
def test_noop_patch_rejected(payload):
    with pytest.raises(ValidationError):
        UpdateProjectRequest.model_validate(payload)
    with pytest.raises(ValidationError):
        UpdateWorkspaceRequest.model_validate(payload)


def test_explicit_project_ungroup_is_valid():
    assert (
        "workspace_id"
        in UpdateProjectRequest.model_validate({"workspace_id": None}).model_fields_set
    )


def test_unverified_invite_cannot_mutate_even_expired_status(session, context):
    invite = SimpleNamespace(
        id=uuid4(), organization_id=context.organization_id, status=InvitationStatus.EXPIRED
    )
    unverified = InvitationAcceptanceContext(context.actor, context.organization_id, invite.id)
    with pytest.raises(PermissionError):
        SqlTenancyRepository(session).update_invitation(invite, context=unverified)
    session.execute.assert_not_called()
