from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text

from openvietgis_api.adapters.persistence.db import get_engine


def test_runtime_role_is_not_superuser_or_bypassrls(migrated_database: None) -> None:
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT rolsuper, rolbypassrls, rolcanlogin
                FROM pg_roles
                WHERE rolname = 'openvietgis_runtime'
                """
            )
        ).mappings().one()

    assert row["rolsuper"] is False
    assert row["rolbypassrls"] is False
    assert row["rolcanlogin"] is True


def test_runtime_role_rls_hides_other_organization_and_audit_rows(
    migrated_database: None,
) -> None:
    user_id = uuid4()
    org_a, org_b = uuid4(), uuid4()
    workspace_a, workspace_b = uuid4(), uuid4()
    engine = get_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                VALUES (:id, 'RLS User', 'active', now(), now())
                """
            ),
            {"id": user_id},
        )
        for org_id, workspace_id, slug in (
            (org_a, workspace_a, f"wa-{workspace_a.hex}"),
            (org_b, workspace_b, f"wb-{workspace_b.hex}"),
        ):
            connection.execute(
                text(
                    """
                    INSERT INTO org.organizations (
                        id, name, slug, status, created_by_actor_type,
                        created_by_actor_id, created_at, updated_at
                    )
                    VALUES (:id, 'Org', :org_slug, 'active', 'human', :user_id, now(), now())
                    """
                ),
                {"id": org_id, "org_slug": f"org-{org_id.hex}", "user_id": user_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workspace.workspaces (
                        id, organization_id, name, slug, status, created_by_actor_type,
                        created_by_actor_id, created_at, updated_at
                    )
                    VALUES (
                        :id, :org_id, 'Workspace', :slug, 'active', 'human',
                        :user_id, now(), now()
                    )
                    """
                ),
                {
                    "id": workspace_id,
                    "org_id": org_id,
                    "slug": slug,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO audit.audit_events (
                        id, organization_id, actor_type, actor_id, actor_display_snapshot,
                        action, outcome, metadata, created_at
                    )
                    VALUES (
                        :id, :org_id, 'human', :user_id, 'RLS User',
                        'test.rls', 'success', '{}'::jsonb, now()
                    )
                    """
                ),
                {"id": uuid4(), "org_id": org_id, "user_id": user_id},
            )

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET LOCAL ROLE openvietgis_runtime"))
            connection.execute(
                text("SELECT set_config('openvietgis.organization_id', :org, true)"),
                {"org": str(org_a)},
            )
            workspace_ids = set(
                connection.execute(text("SELECT id FROM workspace.workspaces")).scalars()
            )
            audit_orgs = set(
                connection.execute(
                    text("SELECT organization_id FROM audit.audit_events")
                ).scalars()
            )
            assert workspace_a in workspace_ids
            assert workspace_b not in workspace_ids
            assert audit_orgs == {org_a}
        finally:
            transaction.rollback()