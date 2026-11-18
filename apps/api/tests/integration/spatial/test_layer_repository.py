"""US2 focused repository tests under the restricted runtime role."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.rls import bind_authenticated_actor
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.spatial.domain import Layer, Lifecycle
from openvietgis_api.domains.spatial.service import SpatialCatalogService
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world


def test_layer_repository_scoped_keyset_and_shared_source(migrated_database: None) -> None:
    world = seed_access_world()
    ctx = AuthorizationContext(
        Actor("human", world.owner_user_id, "Owner"),
        world.organization_id,
        project_id=world.project_id,
    )
    with get_session_factory()() as session:
        bind_authenticated_actor(session, ctx.actor)
        repository = SqlSpatialRepository(session)
        service = SpatialCatalogService(repository)
        source = service.register_source(
            context=ctx, reference_key="reference_points_5899", name="Shared source"
        ).source
        assert repository.has_active_layers(context=ctx, source_id=source.id) is False
        now = datetime.now(UTC)
        layers = [
            Layer(uuid4(), source.organization_id, source.project_id, source.id,
                  "Same name", Lifecycle.ACTIVE, 1, now, now, None)
            for _ in range(2)
        ]
        for layer in layers:
            repository.insert_layer(layer, context=ctx)
        assert repository.has_active_layers(context=ctx, source_id=source.id)
        with pytest.raises(PermissionError):
            repository.list_layers(context=ctx, after_id=None, limit=101)
        repository.prepare_scope(context=ctx, permission=Permission.PROJECT_READ, mutation=False)
        expected = sorted(layers, key=lambda item: item.id)
        assert repository.list_layers(context=ctx, after_id=None, limit=101) == expected
        assert repository.list_layers(context=ctx, after_id=expected[0].id, limit=1) == expected[1:]
        assert repository.list_layers(context=ctx, after_id=expected[1].id, limit=1) == []
        assert repository.get_source(context=ctx, source_id=source.id) == source
        with pytest.raises(PermissionError):
            repository.insert_layer(layers[0], context=ctx)
        session.commit()
    with get_admin_engine().begin() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM spatial.reference_features WHERE source_id=:source"),
            {"source": source.id},
        ).scalar_one() == 4
        assert connection.execute(
            text("SELECT count(*) FROM spatial.layers WHERE source_id=:source"),
            {"source": source.id},
        ).scalar_one() == 2
