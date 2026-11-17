from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text

from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlEffectivePermissionProvider,
)
from openvietgis_api.adapters.persistence.db import get_engine, get_session_factory
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission


def test_workspace_grant_inheritance_is_dynamic_and_project_grant_is_additive(
    migrated_database: None,
) -> None:
    owner_id, member_id, org_id = uuid4(), uuid4(), uuid4()
    membership_id, workspace_a, workspace_b, project_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    workspace_grant_id, project_grant_id = uuid4(), uuid4()

    with get_engine().begin() as connection:
        for user_id, name in ((owner_id, "Owner"), (member_id, "Member")):
            connection.execute(
                text(
                    """
                    INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                    VALUES (:id, :name, 'active', now(), now())
                    """
                ),
                {"id": user_id, "name": name},
            )
        connection.execute(
            text(
                """
                INSERT INTO org.organizations (
                    id, name, slug, status, created_by_actor_type,
                    created_by_actor_id, created_at, updated_at
                )
                VALUES (
                    :id, 'Grant Org', :slug, 'active', 'human',
                    :owner_id, now(), now()
                )
                """
            ),
            {"id": org_id, "slug": f"grant-{org_id.hex}", "owner_id": owner_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO org.organization_memberships (
                    id, organization_id, user_id, role, status,
                    created_at, activated_at
                )
                VALUES (
                    :id, :org_id, :member_id, 'member', 'active',
                    now(), now()
                )
                """
            ),
            {"id": membership_id, "org_id": org_id, "member_id": member_id},
        )
        for workspace_id, slug in (
            (workspace_a, f"a-{workspace_a.hex}"),
            (workspace_b, f"b-{workspace_b.hex}"),
        ):
            connection.execute(
                text(
                    """
                    INSERT INTO workspace.workspaces (
                        id, organization_id, name, slug, status,
                        created_by_actor_type, created_by_actor_id,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :org_id, 'Workspace', :slug, 'active',
                        'human', :owner_id, now(), now()
                    )
                    """
                ),
                {
                    "id": workspace_id,
                    "org_id": org_id,
                    "slug": slug,
                    "owner_id": owner_id,
                },
            )
        connection.execute(
            text(
                """
                INSERT INTO workspace.projects (
                    id, organization_id, workspace_id, name, slug, status,
                    created_by_actor_type, created_by_actor_id, created_at, updated_at
                )
                VALUES (
                    :id, :org_id, :workspace_id, 'Project', :slug, 'active',
                    'human', :owner_id, now(), now()
                )
                """
            ),
            {
                "id": project_id,
                "org_id": org_id,
                "workspace_id": workspace_a,
                "slug": f"p-{project_id.hex}",
                "owner_id": owner_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO org.resource_grants (
                    id, organization_id, subject_kind, membership_id, scope_kind,
                    workspace_id, role, created_at, created_by_actor_type,
                    created_by_actor_id
                )
                VALUES (
                    :id, :org_id, 'membership', :membership_id, 'workspace',
                    :workspace_id, 'viewer', now(), 'human', :owner_id
                )
                """
            ),
            {
                "id": workspace_grant_id,
                "org_id": org_id,
                "membership_id": membership_id,
                "workspace_id": workspace_a,
                "owner_id": owner_id,
            },
        )

    actor = Actor(actor_type="human", actor_id=member_id, display_name="Member")
    context = AuthorizationContext(actor=actor, organization_id=org_id, project_id=project_id)

    session = get_session_factory()()
    try:
        provider = SqlEffectivePermissionProvider(session)
        assert Permission.PROJECT_READ in provider.resolve(context)
        session.rollback()
    finally:
        session.close()

    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                UPDATE workspace.projects
                SET workspace_id = :workspace_b
                WHERE organization_id = :org_id AND id = :project_id
                """
            ),
            {"workspace_b": workspace_b, "org_id": org_id, "project_id": project_id},
        )

    session = get_session_factory()()
    try:
        provider = SqlEffectivePermissionProvider(session)
        assert Permission.PROJECT_READ not in provider.resolve(context)
        session.rollback()
    finally:
        session.close()

    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO org.resource_grants (
                    id, organization_id, subject_kind, membership_id, scope_kind,
                    project_id, role, created_at, created_by_actor_type,
                    created_by_actor_id
                )
                VALUES (
                    :id, :org_id, 'membership', :membership_id, 'project',
                    :project_id, 'viewer', now(), 'human', :owner_id
                )
                """
            ),
            {
                "id": project_grant_id,
                "org_id": org_id,
                "membership_id": membership_id,
                "project_id": project_id,
                "owner_id": owner_id,
            },
        )

    session = get_session_factory()()
    try:
        provider = SqlEffectivePermissionProvider(session)
        assert Permission.PROJECT_READ in provider.resolve(context)
    finally:
        session.rollback()
        session.close()
