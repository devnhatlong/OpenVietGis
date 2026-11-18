from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from openvietgis_api.domains.audit.domain import AuditEvent
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.spatial.domain import (
    CatalogChange,
    DataSource,
    Layer,
    ReferenceFeature,
    SourceField,
)


class SpatialScopeError(PermissionError):
    """The transaction does not hold the required current project authorization."""


class SpatialRevisionConflictError(ValueError):
    """A write did not match the expected catalog or layer revision."""


class SpatialProjectReadOnlyError(ValueError):
    """An archived project may be inspected but not changed."""


class SpatialUnknownReferenceKeyError(ValueError):
    """Reference key is not in the trusted fixture allowlist."""


class SpatialCrsCorrectionUnverifiedError(ValueError):
    """Independent native evidence does not establish the requested declaration."""


class SpatialSourceAlreadyRegisteredError(ValueError):
    """A project already bound the immutable reference key, including retired."""


class SpatialNoChangesError(ValueError):
    """A mutation requested no material changes."""


class SpatialActiveLayerDependenciesError(ValueError):
    """An active layer still depends on this source."""


class SpatialSourceRepository(Protocol):
    """Transaction-bound port; implementation never commits or bypasses RLS.

    A context is an actor request, not authority on its own. prepare_scope must
    verify current R002 membership/credential, project ownership/lifecycle and
    the requested permission in the same transaction. Every method rechecks
    that the bound scope matches the supplied context. Writes require an
    authorized mutation scope; reads from that scope are internal to validation,
    not permission to return spatial metadata to an edit-only actor. Callers
    acquire locks organization -> project -> source -> layer, then persist
    audit evidence in that transaction. No method accepts an unscoped ID.
    """

    def prepare_scope(
        self, *, context: AuthorizationContext, permission: Permission, mutation: bool
    ) -> None: ...

    def get_source(
        self, *, context: AuthorizationContext, source_id: UUID, lock: bool = False
    ) -> DataSource | None:
        """Lock source before its dependents if requested; absent/retired stays scoped."""
        ...

    def list_sources(
        self, *, context: AuthorizationContext, after_id: UUID | None, limit: int
    ) -> list[DataSource]: ...

    def find_source_by_reference_key(
        self, *, context: AuthorizationContext, reference_key: str
    ) -> DataSource | None:
        """Include retired bindings for uniqueness; this is a mutation-only lookup."""
        ...

    def get_fields(
        self, *, context: AuthorizationContext, source_id: UUID
    ) -> list[SourceField]: ...

    def insert_source(
        self,
        source: DataSource,
        fields: Sequence[SourceField],
        features: Sequence[ReferenceFeature],
        *,
        context: AuthorizationContext,
    ) -> None: ...

    def update_source(
        self, source: DataSource, *, context: AuthorizationContext, expected_revision: int
    ) -> None:
        """CAS catalog revision; synchronize changed pins on current rows atomically."""
        ...

    def prepare_reference_source(
        self,
        *,
        context: AuthorizationContext,
        reference_key: str,
        source_id: UUID,
        name: str,
        now: datetime,
    ) -> tuple[DataSource, tuple[SourceField, ...], tuple[ReferenceFeature, ...]]: ...

    def correct_reference_source(
        self,
        *,
        context: AuthorizationContext,
        source: DataSource,
        declared_crs: int,
        now: datetime,
    ) -> DataSource: ...

    def has_active_layers(self, *, context: AuthorizationContext, source_id: UUID) -> bool: ...

    def append_change(
        self, change: CatalogChange, audit: AuditEvent, *, context: AuthorizationContext
    ) -> None:
        """Persist linked change and R002 event atomically; neither may commit alone."""
        ...


class SpatialRepository(SpatialSourceRepository, Protocol):
    """Full R003 port, including layer and pinned feature reads."""

    def get_layer(
        self, *, context: AuthorizationContext, layer_id: UUID, lock: bool = False
    ) -> Layer | None: ...

    def list_layers(
        self, *, context: AuthorizationContext, after_id: UUID | None, limit: int
    ) -> list[Layer]: ...

    def insert_layer(self, layer: Layer, *, context: AuthorizationContext) -> None: ...

    def update_layer(
        self, layer: Layer, *, context: AuthorizationContext, expected_revision: int
    ) -> None: ...

    def read_features(
        self,
        *,
        context: AuthorizationContext,
        source_id: UUID,
        content_revision: str,
        schema_revision: str,
        after_feature_id: str | None,
        limit: int,
    ) -> list[ReferenceFeature]:
        """Return bounded keyset records plus at most one lookahead, with pins verified."""
        ...

    def get_feature(
        self,
        *,
        context: AuthorizationContext,
        source_id: UUID,
        feature_id: str,
        content_revision: str,
        schema_revision: str,
    ) -> ReferenceFeature | None: ...

    def list_changes(
        self, *, context: AuthorizationContext, after_id: UUID | None, limit: int
    ) -> list[CatalogChange]: ...
