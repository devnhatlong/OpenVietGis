"""PostgreSQL adapter for transaction-scoped R003 catalog operations."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, replace
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.rls import (
    ProjectMutationNotWritableError,
    bind_verified_project_context,
    clear_project_context,
    require_project_context,
)
from openvietgis_api.adapters.persistence.spatial_fixtures import (
    ReferenceCorrectionUnverifiedError,
    ReferenceFixtureIntegrityError,
    get_reference_fixture,
    materialize_reference_fixture,
    native_geometry_parameters,
    validate_persisted_reference_source,
    validate_reference_candidate,
    validate_reference_correction,
)
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import (
    AuthorizationDeniedError,
    TenantResourceNotFoundError,
)
from openvietgis_api.domains.spatial.domain import (
    CatalogChange,
    CatalogOperation,
    DataSource,
    Extent,
    ExtentState,
    FeatureCountState,
    FieldType,
    GeometryDimensions,
    GeometryFamily,
    Layer,
    Lifecycle,
    ReferenceFeature,
    ResourceType,
    SchemaState,
    SourceField,
    SourceKind,
    SpatialValidationError,
    ValidationReason,
    ValidationReasonCode,
    ValidationState,
)
from openvietgis_api.domains.spatial.ports import (
    SpatialCrsCorrectionUnverifiedError,
    SpatialProjectReadOnlyError,
    SpatialRevisionConflictError,
    SpatialScopeError,
    SpatialSourceAlreadyRegisteredError,
    SpatialUnknownReferenceKeyError,
)
from openvietgis_api.domains.spatial.service import PinnedSource, verify_source_pins
from openvietgis_api.domains.tenancy.domain import OrganizationStatus, ProjectStatus


def _source_from_row(row: RowMapping) -> DataSource:
    reason = row["validation_reason"]
    extent = row["extent"]
    return DataSource(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        name=row["name"],
        kind=SourceKind(row["kind"]),
        reference_key=row["reference_key"],
        fixture_version=row["fixture_version"],
        manifest_digest=row["manifest_digest"],
        source_asset_id=row["source_asset_id"],
        lifecycle=Lifecycle(row["lifecycle"]),
        validation_state=ValidationState(row["validation_state"]),
        validation_reason=(
            ValidationReason(ValidationReasonCode(reason["code"]), reason["message"])
            if reason is not None
            else None
        ),
        source_crs=row["source_crs"],
        stored_crs=row["stored_crs"],
        schema_state=SchemaState(row["schema_state"]),
        geometry_family=GeometryFamily(row["geometry_family"]),
        dimensions=GeometryDimensions(row["dimensions"]),
        feature_count_state=FeatureCountState(row["feature_count_state"]),
        feature_count=row["feature_count"],
        extent_state=ExtentState(row["extent_state"]),
        extent=Extent(**extent) if extent is not None else None,
        catalog_revision=row["catalog_revision"],
        content_revision=row["content_revision"],
        schema_revision=row["schema_revision"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        retired_at=row["retired_at"],
    )


def _layer_from_row(row: RowMapping) -> Layer:
    return Layer(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        source_id=row["source_id"],
        name=row["name"],
        lifecycle=Lifecycle(row["lifecycle"]),
        layer_revision=row["layer_revision"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        retired_at=row["retired_at"],
    )


class SqlSpatialRepository:
    """Production runtime role only; caller owns the outer transaction.

    Acquire organization then project locks before writes and revalidate current
    permission on that boundary. Target locks are source before layer.
    No method sets raw GUCs or commits the session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def prepare_scope(
        self, *, context: AuthorizationContext, permission: Permission, mutation: bool
    ) -> None:
        clear_project_context(self._session)
        if context.project_id is None:
            raise SpatialScopeError("explicit project scope required")
        allowed = (
            {Permission.PROJECT_EDIT, Permission.PROJECT_MANAGE}
            if mutation
            else {Permission.PROJECT_READ}
        )
        if permission not in allowed:
            raise SpatialScopeError("spatial action does not match requested scope")
        organization = SqlTenancyRepository(self._session).get_organization(
            context.organization_id, context=context, for_update=mutation
        )
        if organization is None:
            raise TenantResourceNotFoundError("organization not found")
        if organization.status != OrganizationStatus.ACTIVE:
            raise AuthorizationDeniedError("organization is not active")
        # Existing project repository does not expose a row-lock argument.
        # Organization lock precedes this exact owner-scoped project lock.
        lock = " FOR UPDATE" if mutation else ""
        status = self._session.execute(
            text(
                "SELECT status FROM workspace.projects "
                "WHERE organization_id = :organization AND id = :project" + lock
            ),
            {"organization": context.organization_id, "project": context.project_id},
        ).scalar_one_or_none()
        if status is None or status == ProjectStatus.DELETED.value:
            raise TenantResourceNotFoundError("project not found")
        try:
            bind_verified_project_context(self._session, context, permission=permission)
        except ProjectMutationNotWritableError as exc:
            raise SpatialProjectReadOnlyError("project is read-only") from exc

    def _scope(
        self, context: AuthorizationContext, *, permission: Permission | None = None
    ) -> dict[str, UUID]:
        require_project_context(self._session, context, permission=permission)
        project_id = context.project_id
        if project_id is None:
            raise SpatialScopeError("explicit project scope required")
        return {"organization": context.organization_id, "project": project_id}

    @staticmethod
    def _assert_owner(context: AuthorizationContext, resource: DataSource | Layer) -> None:
        if (resource.organization_id, resource.project_id) != (
            context.organization_id,
            context.project_id,
        ):
            raise TenantResourceNotFoundError("resource not found")

    def _target_lock(self, context: AuthorizationContext, lock: bool) -> str:
        permission = require_project_context(self._session, context)
        if not lock:
            return ""
        return " FOR SHARE" if permission == Permission.PROJECT_READ else " FOR UPDATE"

    def get_source(
        self, *, context: AuthorizationContext, source_id: UUID, lock: bool = False
    ) -> DataSource | None:
        params = self._scope(context) | {"id": source_id}
        row = (
            self._session.execute(
                text(
                    "SELECT * FROM spatial.data_sources "
                    "WHERE organization_id=:organization AND project_id=:project AND id=:id"
                    + self._target_lock(context, lock)
                ),
                params,
            )
            .mappings()
            .one_or_none()
        )
        return _source_from_row(row) if row is not None else None

    def list_sources(
        self, *, context: AuthorizationContext, after_id: UUID | None, limit: int
    ) -> list[DataSource]:
        if type(limit) is not int or not 1 <= limit <= 101:
            raise SpatialValidationError("catalog query limit out of bounds")
        params = self._scope(context, permission=Permission.PROJECT_READ)
        rows = (
            self._session.execute(
                text(
                    """
                SELECT * FROM spatial.data_sources
                WHERE organization_id=:organization AND project_id=:project
                    AND lifecycle='active'
                    AND (CAST(:after_id AS uuid) IS NULL OR id > CAST(:after_id AS uuid))
                ORDER BY id LIMIT :limit FOR SHARE
                """
                ),
                params | {"after_id": after_id, "limit": limit},
            )
            .mappings()
            .all()
        )
        return [_source_from_row(row) for row in rows]

    def find_source_by_reference_key(
        self, *, context: AuthorizationContext, reference_key: str
    ) -> DataSource | None:
        params = self._scope(context, permission=Permission.PROJECT_EDIT)
        row = (
            self._session.execute(
                text(
                    """
                SELECT * FROM spatial.data_sources
                WHERE organization_id=:organization AND project_id=:project
                    AND reference_key=:reference_key FOR UPDATE
                """
                ),
                params | {"reference_key": reference_key},
            )
            .mappings()
            .one_or_none()
        )
        return _source_from_row(row) if row is not None else None

    def get_fields(self, *, context: AuthorizationContext, source_id: UUID) -> list[SourceField]:
        params = self._scope(context) | {"source": source_id}
        rows = (
            self._session.execute(
                text(
                    """
                SELECT * FROM spatial.source_fields
                WHERE organization_id=:organization AND project_id=:project AND source_id=:source
                ORDER BY ordinal
                """
                ),
                params,
            )
            .mappings()
            .all()
        )
        return [
            SourceField(
                row["organization_id"],
                row["project_id"],
                row["source_id"],
                row["field_id"],
                row["name"],
                row["ordinal"],
                FieldType(row["type"]),
                row["nullable"],
                row["schema_revision"],
            )
            for row in rows
        ]

    def prepare_reference_source(
        self,
        *,
        context: AuthorizationContext,
        reference_key: str,
        source_id: UUID,
        name: str,
        now: datetime,
    ) -> tuple[DataSource, tuple[SourceField, ...], tuple[ReferenceFeature, ...]]:
        params = self._scope(context, permission=Permission.PROJECT_EDIT)
        fixture = get_reference_fixture(reference_key)
        if fixture is None:
            raise SpatialUnknownReferenceKeyError("unknown reference fixture")
        candidate = materialize_reference_fixture(
            reference_key,
            organization_id=params["organization"],
            project_id=params["project"],
            source_id=source_id,
            name=name,
            now=now,
        )
        verified = validate_reference_candidate(self._session, fixture, candidate)
        return verified.source, verified.fields, verified.features

    def correct_reference_source(
        self,
        *,
        context: AuthorizationContext,
        source: DataSource,
        declared_crs: int,
        now: datetime,
    ) -> DataSource:
        self._scope(context, permission=Permission.PROJECT_EDIT)
        self._assert_owner(context, source)
        try:
            return validate_reference_correction(
                self._session,
                source,
                context=context,
                declared_crs=declared_crs,
                now=now,
            )
        except ReferenceCorrectionUnverifiedError as exc:
            raise SpatialCrsCorrectionUnverifiedError(
                "CRS correction could not be verified"
            ) from exc

    def insert_source(
        self,
        source: DataSource,
        fields: Sequence[SourceField],
        features: Sequence[ReferenceFeature],
        *,
        context: AuthorizationContext,
    ) -> None:
        params = self._scope(context, permission=Permission.PROJECT_EDIT)
        self._assert_owner(context, source)
        if source.lifecycle != Lifecycle.ACTIVE or source.catalog_revision != 1:
            raise SpatialValidationError("invalid initial source lifecycle or revision")
        fixture = get_reference_fixture(source.reference_key)
        if fixture is None:
            raise SpatialUnknownReferenceKeyError("unknown reference fixture")
        verify_source_pins(source, fields, features)
        inserted = self._session.execute(
            text("""
                INSERT INTO spatial.data_sources (
                    id, organization_id, project_id, name, kind, reference_key,
                    fixture_version, manifest_digest, source_asset_id, lifecycle,
                    validation_state, validation_reason, source_crs, stored_crs, schema_state,
                    geometry_family, dimensions, feature_count_state, feature_count,
                    extent_state, extent, catalog_revision, content_revision, schema_revision,
                    created_at, updated_at, retired_at
                ) VALUES (
                    :id, :organization, :project, :name, :kind, :reference_key, :fixture_version,
                    :manifest_digest, NULL, :lifecycle, :validation_state, CAST(:reason AS jsonb),
                    :source_crs, :stored_crs, :schema_state, :family, :dimensions, :count_state,
                    :count, :extent_state, CAST(:extent AS jsonb), :revision, :content, :schema,
                    :created_at, :updated_at, :retired_at
                ) ON CONFLICT (organization_id, project_id, reference_key) DO NOTHING
                RETURNING id
            """),
            params
            | {
                "id": source.id,
                "name": source.name,
                "kind": source.kind.value,
                "reference_key": source.reference_key,
                "fixture_version": source.fixture_version,
                "manifest_digest": source.manifest_digest,
                "lifecycle": source.lifecycle.value,
                "validation_state": source.validation_state.value,
                "reason": json.dumps(source.validation_reason.to_wire())
                if source.validation_reason is not None
                else None,
                "source_crs": source.source_crs,
                "stored_crs": source.stored_crs,
                "schema_state": source.schema_state.value,
                "family": source.geometry_family.value,
                "dimensions": source.dimensions.value,
                "count_state": source.feature_count_state.value,
                "count": source.feature_count,
                "extent_state": source.extent_state.value,
                "extent": json.dumps(asdict(source.extent)) if source.extent is not None else None,
                "revision": source.catalog_revision,
                "content": source.content_revision,
                "schema": source.schema_revision,
                "created_at": source.created_at,
                "updated_at": source.updated_at,
                "retired_at": source.retired_at,
            },
        ).scalar_one_or_none()
        if inserted is None:
            raise SpatialSourceAlreadyRegisteredError("reference fixture already registered")
        # Bounded batch inserts use typed recordsets and preserve native SRID and geometry.
        self._session.execute(
            text("""
                INSERT INTO spatial.source_fields (organization_id, project_id, source_id,
                    field_id, name, ordinal, type, nullable, schema_revision)
                SELECT :organization, :project, :source, r.field_id, r.name, r.ordinal,
                    r.type, r.nullable, :schema
                FROM jsonb_to_recordset(CAST(:records AS jsonb))
                    AS r(field_id text, name text, ordinal integer, type text, nullable boolean)
            """),
            params
            | {
                "source": source.id,
                "schema": source.schema_revision,
                "records": json.dumps(
                    [
                        {
                            "field_id": f.field_id,
                            "name": f.name,
                            "ordinal": f.ordinal,
                            "type": f.type.value,
                            "nullable": f.nullable,
                        }
                        for f in fields
                    ]
                ),
            },
        )
        self._session.execute(
            text("""
                INSERT INTO spatial.reference_features (organization_id, project_id, source_id,
                    feature_id, attributes, geometry, geometry_state, content_revision,
                    schema_revision)
                SELECT :organization, :project, :source, r.feature_id, r.attributes,
                    CASE WHEN r.wkt IS NULL THEN NULL
                         ELSE ST_GeomFromText(r.wkt, COALESCE(r.srid,0)) END,
                    r.geometry_state, :content, :schema
                FROM jsonb_to_recordset(CAST(:records AS jsonb))
                    AS r(feature_id text, attributes jsonb, wkt text, srid integer,
                         geometry_state text)
            """),
            params
            | {
                "source": source.id,
                "content": source.content_revision,
                "schema": source.schema_revision,
                "records": json.dumps(
                    [
                        {
                            "feature_id": f.feature_id,
                            "attributes": dict(f.attributes),
                            "wkt": wkt,
                            "srid": srid,
                            "geometry_state": f.geometry_state.value,
                        }
                        for f in features
                        for wkt, srid in (native_geometry_parameters(f.geometry),)
                    ],
                    allow_nan=False,
                ),
            },
        )
        # Verify actual persisted facts under the same scoped runtime transaction.
        checked = validate_persisted_reference_source(
            self._session,
            fixture,
            PinnedSource(source, tuple(fields), tuple(features)),
            context=context,
        )
        if checked.source != source:
            raise ReferenceFixtureIntegrityError("persisted source metadata disagrees")

    def get_layer(
        self, *, context: AuthorizationContext, layer_id: UUID, lock: bool = False
    ) -> Layer | None:
        params = self._scope(context) | {"id": layer_id}
        query = (
            "SELECT * FROM spatial.layers "
            "WHERE organization_id=:organization AND project_id=:project AND id=:id"
        )
        # The source ID is immutable. Discover it without a row lock; acquire
        # source lock first, then re-read/lock the layer under that source.
        row = self._session.execute(text(query), params).mappings().one_or_none()
        if row is None:
            return None
        if lock:
            source = self.get_source(context=context, source_id=row["source_id"], lock=True)
            if source is None:
                raise TenantResourceNotFoundError("resource not found")
            row = (
                self._session.execute(
                    text(query + " AND source_id=:source" + self._target_lock(context, True)),
                    params | {"source": source.id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
        return _layer_from_row(row)

    def update_source(
        self, source: DataSource, *, context: AuthorizationContext, expected_revision: int
    ) -> None:
        permission = (
            Permission.PROJECT_MANAGE
            if source.lifecycle == Lifecycle.RETIRED
            else Permission.PROJECT_EDIT
        )
        params = self._scope(context, permission=permission)
        self._assert_owner(context, source)
        if type(expected_revision) is not int or source.catalog_revision != expected_revision + 1:
            raise SpatialRevisionConflictError("stale source catalog revision")
        prior = self.get_source(context=context, source_id=source.id, lock=True)
        if (
            prior is None
            or prior.lifecycle != Lifecycle.ACTIVE
            or prior.catalog_revision != expected_revision
        ):
            raise SpatialRevisionConflictError("stale source catalog revision")
        if (
            source.reference_key,
            source.fixture_version,
            source.manifest_digest,
            source.stored_crs,
            source.created_at,
        ) != (
            prior.reference_key,
            prior.fixture_version,
            prior.manifest_digest,
            prior.stored_crs,
            prior.created_at,
        ):
            raise SpatialScopeError("source identity/native storage is immutable")
        if (
            source.lifecycle == Lifecycle.ACTIVE
            and replace(
                source, catalog_revision=prior.catalog_revision, updated_at=prior.updated_at
            )
            == prior
        ):
            raise SpatialValidationError("no material source change")
        if source.lifecycle == Lifecycle.RETIRED:
            if (
                replace(
                    source,
                    lifecycle=prior.lifecycle,
                    catalog_revision=prior.catalog_revision,
                    updated_at=prior.updated_at,
                    retired_at=prior.retired_at,
                )
                != prior
            ):
                raise SpatialScopeError("retirement cannot rewrite source data")
            if self.has_active_layers(context=context, source_id=source.id):
                raise SpatialValidationError("active layer dependencies")
        changed = self._session.execute(
            text(
                """
                UPDATE spatial.data_sources SET
                    name=:name, lifecycle=:lifecycle, validation_state=:validation_state,
                    validation_reason=CAST(:reason AS jsonb), source_crs=:source_crs,
                    schema_state=:schema_state, geometry_family=:family, dimensions=:dimensions,
                    feature_count_state=:count_state, feature_count=:feature_count,
                    extent_state=:extent_state, extent=CAST(:extent AS jsonb),
                    catalog_revision=:revision, content_revision=:content, schema_revision=:schema,
                    updated_at=:updated_at, retired_at=:retired_at
                WHERE organization_id=:organization AND project_id=:project AND id=:id
                    AND catalog_revision=:expected AND lifecycle='active'
                RETURNING id
                """
            ),
            params
            | {
                "id": source.id,
                "name": source.name,
                "lifecycle": source.lifecycle.value,
                "validation_state": source.validation_state.value,
                "reason": json.dumps(source.validation_reason.to_wire())
                if source.validation_reason is not None
                else None,
                "source_crs": source.source_crs,
                "schema_state": source.schema_state.value,
                "family": source.geometry_family.value,
                "dimensions": source.dimensions.value,
                "count_state": source.feature_count_state.value,
                "feature_count": source.feature_count,
                "extent_state": source.extent_state.value,
                "extent": json.dumps(asdict(source.extent)) if source.extent is not None else None,
                "revision": source.catalog_revision,
                "content": source.content_revision,
                "schema": source.schema_revision,
                "updated_at": source.updated_at,
                "retired_at": source.retired_at,
                "expected": expected_revision,
            },
        ).scalar_one_or_none()
        if changed is None:
            raise SpatialRevisionConflictError("stale source catalog revision")
        # Current-only pins; deferrable scoped FKs ensure all are consistent at commit.
        pins = params | {
            "source": source.id,
            "schema": source.schema_revision,
            "content": source.content_revision,
        }
        if prior.schema_revision != source.schema_revision:
            self._session.execute(
                text(
                    "UPDATE spatial.source_fields SET schema_revision=:schema "
                    "WHERE organization_id=:organization AND project_id=:project "
                    "AND source_id=:source"
                ),
                pins,
            )
        if (prior.schema_revision, prior.content_revision) != (
            source.schema_revision,
            source.content_revision,
        ):
            self._session.execute(
                text(
                    "UPDATE spatial.reference_features SET schema_revision=:schema, "
                    "content_revision=:content WHERE organization_id=:organization "
                    "AND project_id=:project AND source_id=:source"
                ),
                pins,
            )

    def update_layer(
        self, layer: Layer, *, context: AuthorizationContext, expected_revision: int
    ) -> None:
        params = self._scope(context, permission=Permission.PROJECT_EDIT)
        self._assert_owner(context, layer)
        if type(expected_revision) is not int or layer.layer_revision != expected_revision + 1:
            raise SpatialRevisionConflictError("stale layer revision")
        prior = self.get_layer(context=context, layer_id=layer.id, lock=True)
        if (
            prior is None
            or prior.lifecycle != Lifecycle.ACTIVE
            or prior.layer_revision != expected_revision
        ):
            raise SpatialRevisionConflictError("stale layer revision")
        if (prior.source_id, prior.created_at) != (layer.source_id, layer.created_at):
            raise SpatialScopeError("layer source and identity are immutable")
        if (
            layer.lifecycle == Lifecycle.ACTIVE
            and replace(layer, layer_revision=prior.layer_revision, updated_at=prior.updated_at)
            == prior
        ):
            raise SpatialValidationError("no material layer change")
        if layer.lifecycle == Lifecycle.RETIRED and layer.name != prior.name:
            raise SpatialValidationError("retirement cannot rename layer")
        changed = self._session.execute(
            text(
                """
                UPDATE spatial.layers SET name=:name, lifecycle=:lifecycle,
                    layer_revision=:revision, updated_at=:updated_at, retired_at=:retired_at
                WHERE organization_id=:organization AND project_id=:project AND id=:id
                    AND source_id=:source AND layer_revision=:expected AND lifecycle='active'
                RETURNING id
                """
            ),
            params
            | {
                "id": layer.id,
                "source": layer.source_id,
                "name": layer.name,
                "lifecycle": layer.lifecycle.value,
                "revision": layer.layer_revision,
                "updated_at": layer.updated_at,
                "retired_at": layer.retired_at,
                "expected": expected_revision,
            },
        ).scalar_one_or_none()
        if changed is None:
            raise SpatialRevisionConflictError("stale layer revision")

    def has_active_layers(self, *, context: AuthorizationContext, source_id: UUID) -> bool:
        params = self._scope(context) | {"source": source_id}
        return bool(
            self._session.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM spatial.layers "
                    "WHERE organization_id=:organization "
                    "AND project_id=:project AND source_id=:source AND lifecycle='active')"
                ),
                params,
            ).scalar_one()
        )

    def append_change(
        self, change: CatalogChange, audit: AuditEvent, *, context: AuthorizationContext
    ) -> None:
        permission = (
            Permission.PROJECT_MANAGE
            if change.operation == CatalogOperation.RETIRE_SOURCE
            else Permission.PROJECT_EDIT
        )
        params = self._scope(context, permission=permission)
        if (
            (change.organization_id, change.project_id)
            != (context.organization_id, context.project_id)
            or change.actor_id != context.actor.actor_id
            or change.actor_type.value != context.actor.actor_type
            or change.actor_display_snapshot != context.actor.display_name
            or (
                audit.id,
                audit.organization_id,
                audit.actor_type,
                audit.actor_id,
                audit.actor_display_snapshot,
                audit.resource_type,
                audit.resource_id,
                audit.outcome,
                audit.created_at,
                audit.action,
            )
            != (
                change.audit_event_id,
                change.organization_id,
                change.actor_type,
                change.actor_id,
                change.actor_display_snapshot,
                change.resource_type.value,
                change.resource_id,
                AuditOutcome.SUCCESS,
                change.created_at,
                f"spatial.catalog.{change.operation.value}",
            )
            or audit.metadata
            != {"project_id": str(change.project_id), "catalog_change_id": str(change.id)}
        ):
            raise SpatialScopeError("catalog and audit evidence mismatch")
        resource = (
            self.get_source(context=context, source_id=change.resource_id)
            if change.resource_type == ResourceType.DATA_SOURCE
            else self.get_layer(context=context, layer_id=change.resource_id)
        )
        if resource is None or resource.revision != change.new_revision:
            raise SpatialRevisionConflictError("catalog evidence revision mismatch")
        # Same session and outer transaction; append only, never independent commit.
        SqlAuditRepository(self._session).append(audit)
        self._scope(context, permission=permission)
        self._session.execute(
            text(
                """
                INSERT INTO spatial.catalog_changes (
                    id, organization_id, project_id, resource_type, resource_id, source_id,
                    layer_id, actor_type, actor_id, actor_display_snapshot, operation, created_at,
                    audit_event_id, prior_revision, new_revision, changes
                ) VALUES (
                    :id, :organization, :project, :resource_type, :resource_id, :source_id,
                    :layer_id, :actor_type, :actor_id, :actor_display_snapshot, :operation,
                    :created_at, :audit_event_id, CAST(:prior AS jsonb),
                    CAST(:new AS jsonb), CAST(:changes AS jsonb)
                )
                """
            ),
            params
            | {
                "id": change.id,
                "resource_type": change.resource_type.value,
                "resource_id": change.resource_id,
                "source_id": change.source_id,
                "layer_id": change.layer_id,
                "actor_type": change.actor_type.value,
                "actor_id": change.actor_id,
                "actor_display_snapshot": change.actor_display_snapshot,
                "operation": change.operation.value,
                "created_at": change.created_at,
                "audit_event_id": change.audit_event_id,
                "prior": json.dumps(change.prior_revision.to_wire())
                if change.prior_revision is not None
                else None,
                "new": json.dumps(change.new_revision.to_wire()),
                "changes": json.dumps([item.to_wire() for item in change.changes]),
            },
        )
