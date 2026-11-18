"""PostgreSQL adapter for transaction-scoped R003 catalog operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import (
    bind_verified_project_context,
    clear_project_context,
    require_project_context,
)
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import (
    AuthorizationDeniedError,
    TenantResourceNotFoundError,
)
from openvietgis_api.domains.spatial.domain import (
    DataSource,
    Extent,
    ExtentState,
    FeatureCountState,
    GeometryDimensions,
    GeometryFamily,
    Layer,
    Lifecycle,
    SchemaState,
    SourceKind,
    ValidationReason,
    ValidationReasonCode,
    ValidationState,
)
from openvietgis_api.domains.spatial.ports import (
    SpatialProjectReadOnlyError,
    SpatialScopeError,
)
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
            if reason is not None else None
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
            if mutation else {Permission.PROJECT_READ}
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
        if mutation and status != ProjectStatus.ACTIVE.value:
            raise SpatialProjectReadOnlyError("project is read-only")
        bind_verified_project_context(self._session, context, permission=permission)

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
            context.organization_id, context.project_id
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
        row = self._session.execute(
            text(
                "SELECT * FROM spatial.data_sources "
                "WHERE organization_id=:organization AND project_id=:project AND id=:id"
                + self._target_lock(context, lock)
            ),
            params,
        ).mappings().one_or_none()
        return _source_from_row(row) if row is not None else None

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
            row = self._session.execute(
                text(query + " AND source_id=:source" + self._target_lock(context, True)),
                params | {"source": source.id},
            ).mappings().one_or_none()
            if row is None:
                return None
        return _layer_from_row(row)
