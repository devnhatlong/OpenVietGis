"""US1 repository-only transaction and scope tests (real restricted role)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.rls import bind_authenticated_actor
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import TenantResourceNotFoundError
from openvietgis_api.domains.spatial.domain import (
    CatalogOperation,
    Lifecycle,
    ValidationReasonCode,
    ValidationState,
)
from openvietgis_api.domains.spatial.ports import (
    SpatialCrsCorrectionUnverifiedError,
    SpatialNoChangesError,
    SpatialRevisionConflictError,
    SpatialSourceAlreadyRegisteredError,
)
from openvietgis_api.domains.spatial.service import SpatialCatalogService, build_mutation_evidence
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world


def test_scoped_source_storage_reads_and_duplicate_binding(migrated_database: None) -> None:
    world = seed_access_world()
    ctx = AuthorizationContext(
        Actor("human", world.owner_user_id, "Owner"),
        world.organization_id,
        project_id=world.project_id,
    )
    with get_session_factory()() as session:
        bind_authenticated_actor(session, ctx.actor)
        repository = SqlSpatialRepository(session)
        repository.prepare_scope(context=ctx, permission=Permission.PROJECT_EDIT, mutation=True)
        with pytest.raises(PermissionError):
            repository.list_sources(context=ctx, after_id=None, limit=2)
        # Failed scope proof is invalidated; rebind before continuing.
        repository.prepare_scope(context=ctx, permission=Permission.PROJECT_EDIT, mutation=True)
        now = datetime.now(UTC)
        source, fields, features = repository.prepare_reference_source(
            context=ctx,
            reference_key="reference_points_5899",
            source_id=uuid4(),
            name="Projected",
            now=now,
        )
        assert source.validation_state == ValidationState.READY
        repository.insert_source(source, fields, features, context=ctx)
        assert (
            repository.find_source_by_reference_key(context=ctx, reference_key=source.reference_key)
            == source
        )
        with pytest.raises(SpatialSourceAlreadyRegisteredError):
            other, fields2, features2 = repository.prepare_reference_source(
                context=ctx,
                reference_key=source.reference_key,
                source_id=uuid4(),
                name="Duplicate",
                now=now,
            )
            repository.insert_source(other, fields2, features2, context=ctx)
        assert repository.get_source(context=ctx, source_id=source.id) == source
        evidence = build_mutation_evidence(
            context=ctx,
            prior=None,
            current=source,
            operation=CatalogOperation.REGISTER_SOURCE,
            now=now,
        )
        repository.append_change(evidence.change, evidence.audit, context=ctx)
        session.commit()
    with get_session_factory()() as session:
        bind_authenticated_actor(session, ctx.actor)
        repository = SqlSpatialRepository(session)
        repository.prepare_scope(context=ctx, permission=Permission.PROJECT_READ, mutation=False)
        assert repository.list_sources(context=ctx, after_id=None, limit=2) == [source]
        assert repository.list_sources(context=ctx, after_id=source.id, limit=2) == []
        assert repository.get_fields(context=ctx, source_id=source.id) == list(fields)
        assert repository.get_source(context=ctx, source_id=source.id).lifecycle == Lifecycle.ACTIVE
        with pytest.raises(PermissionError):
            repository.find_source_by_reference_key(context=ctx, reference_key=source.reference_key)
    with get_admin_engine().begin() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM spatial.reference_features WHERE source_id=:id"),
                {"id": source.id},
            ).scalar_one()
            == 4
        )


def test_source_service_mutation_and_revision_lifecycle(migrated_database: None) -> None:
    world = seed_access_world()
    ctx = AuthorizationContext(
        Actor("human", world.owner_user_id, "Owner"),
        world.organization_id,
        project_id=world.project_id,
    )
    with get_session_factory()() as session:
        bind_authenticated_actor(session, ctx.actor)
        service = SpatialCatalogService(SqlSpatialRepository(session))
        created = service.register_source(
            context=ctx,
            reference_key="reference_correctable_crs",
            name="  Control  ",
        )
        assert created.source.validation_reason.code == ValidationReasonCode.CRS_MISMATCH
        assert created.source.name == "Control"
        prior = created.source
        with pytest.raises(SpatialCrsCorrectionUnverifiedError):
            service.update_source(
                context=ctx,
                source_id=prior.id,
                expected_revision=1,
                declared_crs=4756,
            )
        corrected = service.update_source(
            context=ctx,
            source_id=prior.id,
            expected_revision=1,
            name="Corrected",
            declared_crs=4326,
        )
        assert corrected.source.validation_state == ValidationState.READY
        assert corrected.source.revision.schema_revision == prior.revision.schema_revision
        assert corrected.source.revision.content_revision != prior.revision.content_revision
        assert corrected.source.catalog_revision == 2
        with pytest.raises(SpatialRevisionConflictError):
            service.update_source(
                context=ctx,
                source_id=prior.id,
                expected_revision=1,
                name="Stale",
            )
        with pytest.raises(SpatialNoChangesError):
            service.update_source(
                context=ctx,
                source_id=prior.id,
                expected_revision=2,
                name="Corrected",
            )
        renamed = service.update_source(
            context=ctx,
            source_id=prior.id,
            expected_revision=2,
            name="New name",
        )
        assert renamed.source.catalog_revision == 3
        assert renamed.source.content_revision == corrected.source.content_revision
        assert renamed.source.schema_revision == corrected.source.schema_revision
        retired = service.retire_source(context=ctx, source_id=prior.id, expected_revision=3)
        assert retired.source.lifecycle == Lifecycle.RETIRED
        assert retired.source.catalog_revision == 4
        with pytest.raises(TenantResourceNotFoundError):
            service.get_source(context=ctx, source_id=prior.id)
        with pytest.raises(TenantResourceNotFoundError):
            service.update_source(
                context=ctx,
                source_id=prior.id,
                expected_revision=4,
                name="Not allowed",
            )
        with pytest.raises(SpatialSourceAlreadyRegisteredError):
            service.register_source(
                context=ctx,
                reference_key=prior.reference_key,
                name="No rebind",
            )
        assert service.list_sources(context=ctx, after_id=None, limit=100).items == ()
        session.commit()
    with get_admin_engine().begin() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM spatial.catalog_changes WHERE resource_id=:id"),
                {"id": prior.id},
            ).scalar_one()
            == 4
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM audit.audit_events WHERE resource_id=:id"),
                {"id": prior.id},
            ).scalar_one()
            == 4
        )
