"""R003 repository scope and ordered lock boundary, real restricted role."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.rls import bind_authenticated_actor
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import (
    AuthorizationDeniedError,
    TenantResourceNotFoundError,
)
from openvietgis_api.domains.spatial.ports import SpatialProjectReadOnlyError
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import AccessWorld, seed_access_world


def _context(world: AccessWorld, *, project: UUID | None = None) -> AuthorizationContext:
    return AuthorizationContext(
        Actor("human", world.owner_user_id, "Owner"),
        world.organization_id,
        project_id=project or world.project_id,
    )


def _seed(world: AccessWorld) -> tuple[UUID, UUID]:
    source, layer = uuid4(), uuid4()
    with get_admin_engine().begin() as connection:
        connection.execute(text("""
            INSERT INTO spatial.data_sources (
                id, organization_id, project_id, name, kind, reference_key, fixture_version,
                manifest_digest, lifecycle, validation_state, source_crs, stored_crs, schema_state,
                geometry_family, dimensions, feature_count_state, feature_count, extent_state,
                catalog_revision, content_revision, schema_revision, created_at, updated_at
            ) VALUES (
                :source, :org, :project, 'Empty reference','reference_fixture',
                'reference_empty_4326','v1',:manifest,'active','ready',4326,4326,'known',
                'Point','XY','known',0,'empty',1,:content,:schema,now(),now()
            )
        """), {
            "source": source, "org": world.organization_id, "project": world.project_id,
            "manifest": "a"*64, "content": "b"*64, "schema": "c"*64,
        })
        connection.execute(text("""
            INSERT INTO spatial.layers (
                id,organization_id,project_id,source_id,name,lifecycle,layer_revision,
                created_at,updated_at
            ) VALUES (:layer,:org,:project,:source,'Layer','active',1,now(),now())
        """), {
            "layer": layer, "source": source, "org": world.organization_id,
            "project": world.project_id,
        })
    return source, layer


def test_repository_fails_closed_before_verified_scope_and_on_wrong_project(
    migrated_database: None,
) -> None:
    a, b = seed_access_world(), seed_access_world()
    source_a, layer_a = _seed(a)
    source_b, layer_b = _seed(b)
    with get_session_factory()() as session:
        repository = SqlSpatialRepository(session)
        ctx = _context(a)
        bind_authenticated_actor(session, ctx.actor)
        with pytest.raises(PermissionError):
            repository.get_source(context=ctx, source_id=source_a)
        repository.prepare_scope(context=ctx, permission=Permission.PROJECT_READ, mutation=False)
        source = repository.get_source(context=ctx, source_id=source_a, lock=True)
        layer = repository.get_layer(context=ctx, layer_id=layer_a, lock=True)
        assert source is not None and source.project_id == a.project_id
        assert layer is not None and layer.source_id == source_a
        assert repository.get_source(context=ctx, source_id=source_b) is None
        assert repository.get_layer(context=ctx, layer_id=layer_b) is None
        wrong = _context(a, project=b.project_id)
        with pytest.raises(PermissionError):
            repository.get_source(context=wrong, source_id=source_a)
        with pytest.raises(TenantResourceNotFoundError):
            repository.prepare_scope(
                context=wrong, permission=Permission.PROJECT_READ, mutation=False
            )
        with pytest.raises(PermissionError):
            repository.get_source(context=ctx, source_id=source_a)


def test_repository_archived_read_allowed_mutation_denied_and_scope_cleared(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    source, _ = _seed(world)
    with get_admin_engine().begin() as connection:
        connection.execute(text("""
            UPDATE workspace.projects SET status='archived',archived_at=now(),updated_at=now()
            WHERE organization_id=:org AND id=:project
        """), {"org": world.organization_id, "project": world.project_id})
    with get_session_factory()() as session:
        ctx = _context(world)
        bind_authenticated_actor(session, ctx.actor)
        repository = SqlSpatialRepository(session)
        repository.prepare_scope(context=ctx, permission=Permission.PROJECT_READ, mutation=False)
        assert repository.get_source(context=ctx, source_id=source) is not None
        with pytest.raises((SpatialProjectReadOnlyError, AuthorizationDeniedError)):
            repository.prepare_scope(context=ctx, permission=Permission.PROJECT_EDIT, mutation=True)
        with pytest.raises(PermissionError):
            repository.get_source(context=ctx, source_id=source)


def test_repository_denies_ungranted_member_and_action_mismatch(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    source, _ = _seed(world)
    ctx = AuthorizationContext(
        Actor("human", world.member_user_id, "Member"),
        world.organization_id,
        project_id=world.project_id,
    )
    with get_session_factory()() as session:
        bind_authenticated_actor(session, ctx.actor)
        repository = SqlSpatialRepository(session)
        with pytest.raises(AuthorizationDeniedError):
            repository.prepare_scope(
                context=ctx, permission=Permission.PROJECT_READ, mutation=False
            )
        with pytest.raises(PermissionError):
            repository.get_source(context=ctx, source_id=source)
        with pytest.raises(PermissionError):
            repository.prepare_scope(
                context=ctx, permission=Permission.PROJECT_EDIT, mutation=False
            )
