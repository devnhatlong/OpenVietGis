from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from testcontainers.community.postgres import PostgresContainer

from openvietgis_api.adapters.persistence.db import get_engine


@dataclass(frozen=True, slots=True)
class SyntheticIds:
    user_a: UUID
    user_b: UUID
    organization_a: UUID
    organization_b: UUID


@pytest.fixture
def synthetic_ids() -> SyntheticIds:
    return SyntheticIds(
        user_a=uuid4(),
        user_b=uuid4(),
        organization_a=uuid4(),
        organization_b=uuid4(),
    )


@pytest.fixture
def postgis_container_factory() -> Callable[[], PostgresContainer]:
    def factory() -> PostgresContainer:
        return PostgresContainer(
            image="postgis/postgis:18-3.7",
            username="openvietgis",
            password="openvietgis",
            dbname="openvietgis_test",
            driver="psycopg",
        )

    return factory


@dataclass(frozen=True, slots=True)
class AccessWorld:
    owner_user_id: UUID
    owner_membership_id: UUID
    member_user_id: UUID
    member_membership_id: UUID
    wrong_user_id: UUID
    organization_id: UUID
    workspace_a_id: UUID
    workspace_b_id: UUID
    project_id: UUID


def seed_access_world() -> AccessWorld:
    owner_user_id = uuid4()
    member_user_id = uuid4()
    wrong_user_id = uuid4()
    organization_id = uuid4()
    owner_membership_id = uuid4()
    member_membership_id = uuid4()
    workspace_a_id = uuid4()
    workspace_b_id = uuid4()
    project_id = uuid4()

    with get_engine().begin() as connection:
        for user_id, name, email in (
            (owner_user_id, "Owner", "owner@example.test"),
            (member_user_id, "Member", "member-a@example.test"),
            (wrong_user_id, "Wrong", "wrong@example.test"),
        ):
            connection.execute(
                text(
                    """
                    INSERT INTO identity.users (
                        id, display_name, email_snapshot, status, created_at, updated_at
                    )
                    VALUES (:id, :name, :email, 'active', now(), now())
                    """
                ),
                {"id": user_id, "name": name, "email": email},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO identity.identity_links (
                        id, user_id, issuer, subject, email_snapshot,
                        email_verified, display_name_snapshot, created_at
                    )
                    VALUES (
                        :id, :user_id, 'https://issuer.example', :subject,
                        :email, true, :name, now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "user_id": user_id,
                    "subject": f"subject-{user_id}",
                    "email": email,
                    "name": name,
                },
            )

        connection.execute(
            text(
                """
                INSERT INTO org.organizations (
                    id, name, slug, status, created_by_actor_type,
                    created_by_actor_id, created_at, updated_at
                )
                VALUES (
                    :id, 'Access Org', :slug, 'active', 'human',
                    :owner_id, now(), now()
                )
                """
            ),
            {
                "id": organization_id,
                "slug": f"access-{organization_id.hex}",
                "owner_id": owner_user_id,
            },
        )
        for membership_id, user_id, role in (
            (owner_membership_id, owner_user_id, "owner"),
            (member_membership_id, member_user_id, "member"),
        ):
            connection.execute(
                text(
                    """
                    INSERT INTO org.organization_memberships (
                        id, organization_id, user_id, role, status,
                        created_at, activated_at
                    )
                    VALUES (
                        :id, :organization_id, :user_id, :role, 'active',
                        now(), now()
                    )
                    """
                ),
                {
                    "id": membership_id,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "role": role,
                },
            )

        for workspace_id, name in (
            (workspace_a_id, "Workspace A"),
            (workspace_b_id, "Workspace B"),
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
                        :id, :organization_id, :name, :slug, 'active',
                        'human', :owner_id, now(), now()
                    )
                    """
                ),
                {
                    "id": workspace_id,
                    "organization_id": organization_id,
                    "name": name,
                    "slug": f"workspace-{workspace_id.hex}",
                    "owner_id": owner_user_id,
                },
            )

        connection.execute(
            text(
                """
                INSERT INTO workspace.projects (
                    id, organization_id, workspace_id, name, slug, status,
                    created_by_actor_type, created_by_actor_id,
                    created_at, updated_at
                )
                VALUES (
                    :id, :organization_id, :workspace_id, 'Access Project',
                    :slug, 'active', 'human', :owner_id, now(), now()
                )
                """
            ),
            {
                "id": project_id,
                "organization_id": organization_id,
                "workspace_id": workspace_a_id,
                "slug": f"project-{project_id.hex}",
                "owner_id": owner_user_id,
            },
        )

    return AccessWorld(
        owner_user_id=owner_user_id,
        owner_membership_id=owner_membership_id,
        member_user_id=member_user_id,
        member_membership_id=member_membership_id,
        wrong_user_id=wrong_user_id,
        organization_id=organization_id,
        workspace_a_id=workspace_a_id,
        workspace_b_id=workspace_b_id,
        project_id=project_id,
    )
