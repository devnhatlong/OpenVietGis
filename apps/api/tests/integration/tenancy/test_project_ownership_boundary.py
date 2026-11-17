from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from openvietgis_api.adapters.persistence.db import get_engine


def test_database_rejects_project_workspace_cross_tenant_reference(
    migrated_database: None,
) -> None:
    user_id, org_a, org_b, workspace_b = uuid4(), uuid4(), uuid4(), uuid4()
    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                VALUES (:id, 'Boundary User', 'active', now(), now())
                """
            ),
            {"id": user_id},
        )
        for org_id in (org_a, org_b):
            connection.execute(
                text(
                    """
                    INSERT INTO org.organizations (
                        id, name, slug, status, created_by_actor_type,
                        created_by_actor_id, created_at, updated_at
                    )
                    VALUES (:id, 'Org', :slug, 'active', 'human', :user_id, now(), now())
                    """
                ),
                {"id": org_id, "slug": f"org-{org_id.hex}", "user_id": user_id},
            )
        connection.execute(
            text(
                """
                INSERT INTO workspace.workspaces (
                    id, organization_id, name, slug, status,
                    created_by_actor_type, created_by_actor_id, created_at, updated_at
                )
                VALUES (
                    :id, :org_id, 'Workspace B', :slug, 'active',
                    'human', :user_id, now(), now()
                )
                """
            ),
            {
                "id": workspace_b,
                "org_id": org_b,
                "slug": f"wb-{workspace_b.hex}",
                "user_id": user_id,
            },
        )

    with pytest.raises(IntegrityError):
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO workspace.projects (
                        id, organization_id, workspace_id, name, slug, status,
                        created_by_actor_type, created_by_actor_id, created_at, updated_at
                    )
                    VALUES (
                        :id, :org_id, :workspace_id, 'Cross Tenant', :slug, 'active',
                        'human', :user_id, now(), now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "org_id": org_a,
                    "workspace_id": workspace_b,
                    "slug": f"bad-{uuid4().hex}",
                    "user_id": user_id,
                },
            )
