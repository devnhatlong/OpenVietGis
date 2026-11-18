"""R003 revision and audit evidence primitives (no transaction commit)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import TenantResourceNotFoundError
from openvietgis_api.domains.spatial.domain import (
    MAX_REVISION,
    CatalogChange,
    CatalogOperation,
    ChangedValue,
    ChangeValue,
    DataSource,
    Layer,
    Lifecycle,
    ReferenceFeature,
    ResourceType,
    SourceField,
    SpatialValidationError,
    ValidationState,
    content_revision_digest,
    schema_revision_digest,
    validate_source_contents,
)
from openvietgis_api.domains.spatial.ports import (
    SpatialActiveLayerDependenciesError,
    SpatialNoChangesError,
    SpatialRevisionConflictError,
    SpatialScopeError,
    SpatialSourceAlreadyRegisteredError,
    SpatialSourceRepository,
)
from openvietgis_api.domains.tenancy.domain import ActorType


@dataclass(frozen=True, slots=True)
class PinnedSource:
    source: DataSource
    fields: tuple[SourceField, ...]
    features: tuple[ReferenceFeature, ...]


def derive_source_pins(
    source: DataSource,
    fields: Sequence[SourceField],
    features: Sequence[ReferenceFeature],
) -> PinnedSource:
    """Compute both manifest hashes server-side and replace provisional pins.

    The digest inputs include geometry interpretation and explicit schema state;
    scope/attribute/availability invariants are checked on the resulting records.
    Never accept user-supplied revision tokens on registration or correction.
    """
    schema = schema_revision_digest(
        fields, source.geometry_family, source.dimensions, schema_state=source.schema_state
    )
    content = content_revision_digest(
        features,
        fields,
        source.stored_crs,
        source.source_crs,
        geometry_family=source.geometry_family,
        dimensions=source.dimensions,
    )
    result = PinnedSource(
        replace(source, schema_revision=schema, content_revision=content),
        tuple(replace(field, schema_revision=schema) for field in fields),
        tuple(
            replace(feature, schema_revision=schema, content_revision=content)
            for feature in features
        ),
    )
    validate_source_contents(result.source, result.fields, result.features)
    return result


def verify_source_pins(
    source: DataSource,
    fields: Sequence[SourceField],
    features: Sequence[ReferenceFeature],
) -> None:
    """Check both actual content and assigned tokens before materialization."""
    validate_source_contents(source, fields, features)
    expected = derive_source_pins(source, fields, features)
    if expected.source.revision != source.revision:
        raise SpatialValidationError("source revision is not its canonical manifest")


def next_revision(current: int, expected: int) -> int:
    if type(expected) is not int or expected != current:
        raise SpatialRevisionConflictError("stale catalog revision")
    if not 1 <= current < MAX_REVISION:
        raise SpatialValidationError("catalog revision exhausted")
    return current + 1


@dataclass(frozen=True, slots=True)
class MutationEvidence:
    change: CatalogChange
    audit: AuditEvent


def _source_snapshot(source: DataSource) -> dict[str, ChangeValue]:
    reason = source.validation_reason
    return {
        "name": source.name,
        "kind": source.kind.value,
        "reference_key": source.reference_key,
        "fixture_version": source.fixture_version,
        "manifest_digest": source.manifest_digest,
        "source_asset_id": None,
        "lifecycle": source.lifecycle.value,
        "validation_state": source.validation_state.value,
        "validation_reason.code": reason.code.value if reason else None,
        "validation_reason.message": reason.message if reason else None,
        "source_crs": source.source_crs,
        "stored_crs": source.stored_crs,
        "schema_state": source.schema_state.value,
        "geometry_family": source.geometry_family.value,
        "dimensions": source.dimensions.value,
        "feature_count_state": source.feature_count_state.value,
        "feature_count": source.feature_count,
        "extent_state": source.extent_state.value,
        "catalog_revision": source.catalog_revision,
        "content_revision": source.content_revision,
        "schema_revision": source.schema_revision,
    }


def _layer_snapshot(layer: Layer) -> dict[str, ChangeValue]:
    return {
        "name": layer.name,
        "source_id": str(layer.source_id),
        "lifecycle": layer.lifecycle.value,
        "layer_revision": layer.layer_revision,
    }


def _diff(
    prior: dict[str, ChangeValue], current: dict[str, ChangeValue]
) -> tuple[ChangedValue, ...]:
    return tuple(
        ChangedValue(field, prior.get(field), value)
        for field, value in sorted(current.items())
        if type(prior.get(field)) is not type(value) or prior.get(field) != value
    )


def build_mutation_evidence(
    *,
    context: AuthorizationContext,
    prior: DataSource | Layer | None,
    current: DataSource | Layer,
    operation: CatalogOperation,
    now: datetime,
) -> MutationEvidence:
    """Derive actual safe scalar changes from immutable domain objects."""
    actor = context.actor
    if (
        actor.actor_id is None
        or actor.actor_type not in ("human", "service_principal")
        or (context.organization_id, context.project_id)
        != (current.organization_id, current.project_id)
    ):
        raise SpatialScopeError("catalog mutation scope mismatch")
    if prior is not None and (
        type(prior) is not type(current)
        or (prior.id, prior.organization_id, prior.project_id)
        != (current.id, current.organization_id, current.project_id)
        or prior.lifecycle != Lifecycle.ACTIVE
        or prior.created_at != current.created_at
    ):
        raise SpatialValidationError(
            "catalog mutation changes immutable identity or retired resource"
        )
    if current.updated_at != now:
        raise SpatialValidationError("catalog mutation timestamp mismatch")
    source_id: UUID | None
    layer_id: UUID | None
    if isinstance(current, DataSource):
        if prior is not None and not isinstance(prior, DataSource):
            raise SpatialValidationError("source mutation type mismatch")
        current_values = _source_snapshot(current)
        prior_values = _source_snapshot(prior) if prior is not None else {}
        resource_type = ResourceType.DATA_SOURCE
        source_id, layer_id = current.id, None
        expected_operation = CatalogOperation.REGISTER_SOURCE
        mutable_fields = {
            CatalogOperation.UPDATE_SOURCE: {"name", "catalog_revision"},
            CatalogOperation.CORRECT_SOURCE_CRS: {
                "name",
                "source_crs",
                "validation_state",
                "validation_reason.code",
                "validation_reason.message",
                "extent_state",
                "content_revision",
                "catalog_revision",
            },
            CatalogOperation.RETIRE_SOURCE: {"lifecycle", "catalog_revision"},
            CatalogOperation.REFRESH_REFERENCE_FIXTURE: {
                "validation_state",
                "validation_reason.code",
                "validation_reason.message",
                "schema_state",
                "geometry_family",
                "dimensions",
                "feature_count_state",
                "feature_count",
                "extent_state",
                "content_revision",
                "schema_revision",
                "catalog_revision",
            },
        }
        revision_field = "catalog_revision"
        if (
            prior is not None
            and operation in (CatalogOperation.UPDATE_SOURCE, CatalogOperation.RETIRE_SOURCE)
            and prior.extent != current.extent
        ):
            raise SpatialValidationError("metadata-only mutation cannot change native extent")
        if prior is not None and (prior.stored_crs, prior.manifest_digest) != (
            current.stored_crs,
            current.manifest_digest,
        ):
            raise SpatialValidationError("native CRS or manifest identity cannot be rewritten")
    else:
        if prior is not None and not isinstance(prior, Layer):
            raise SpatialValidationError("layer mutation type mismatch")
        current_values = _layer_snapshot(current)
        prior_values = _layer_snapshot(prior) if prior is not None else {}
        resource_type = ResourceType.LAYER
        source_id, layer_id = None, current.id
        expected_operation = CatalogOperation.CREATE_LAYER
        mutable_fields = {
            CatalogOperation.RENAME_LAYER: {"name", "layer_revision"},
            CatalogOperation.RETIRE_LAYER: {"lifecycle", "layer_revision"},
        }
        revision_field = "layer_revision"

    changes = _diff(prior_values, current_values)
    changed = {change.field for change in changes}
    if prior is None:
        if operation != expected_operation or current.lifecycle != Lifecycle.ACTIVE:
            raise SpatialValidationError("invalid initial catalog operation")
    else:
        allowed = mutable_fields.get(operation)
        if allowed is None or not changed <= allowed or not (changed - {revision_field}):
            raise SpatialValidationError("invalid catalog transition or no material change")
        if revision_field not in changed:
            raise SpatialValidationError("catalog transition did not advance revision")
        retiring = operation in (CatalogOperation.RETIRE_SOURCE, CatalogOperation.RETIRE_LAYER)
        if retiring != (current.lifecycle == Lifecycle.RETIRED):
            raise SpatialValidationError("catalog retirement operation mismatch")
        if operation == CatalogOperation.CORRECT_SOURCE_CRS and (
            "source_crs" not in changed or "content_revision" not in changed
        ):
            raise SpatialValidationError("coordinate correction must change interpretation and pin")
        if operation == CatalogOperation.REFRESH_REFERENCE_FIXTURE and not (
            changed & {"content_revision", "schema_revision"}
        ):
            raise SpatialValidationError("controlled refresh must change a readable revision")
    change = CatalogChange(
        id=uuid4(),
        organization_id=current.organization_id,
        project_id=current.project_id,
        resource_type=resource_type,
        resource_id=current.id,
        source_id=source_id,
        layer_id=layer_id,
        actor_type=ActorType(actor.actor_type),
        actor_id=actor.actor_id,
        actor_display_snapshot=actor.display_name,
        operation=operation,
        created_at=now,
        audit_event_id=uuid4(),
        prior_revision=prior.revision if prior is not None else None,
        new_revision=current.revision,
        changes=changes,
    )
    audit = AuditEvent(
        id=change.audit_event_id,
        organization_id=change.organization_id,
        actor_type=change.actor_type,
        actor_id=change.actor_id,
        actor_display_snapshot=change.actor_display_snapshot,
        action=f"spatial.catalog.{change.operation.value}",
        resource_type=change.resource_type.value,
        resource_id=change.resource_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={"project_id": str(change.project_id), "catalog_change_id": str(change.id)},
        created_at=change.created_at,
    )
    return MutationEvidence(change, audit)


@dataclass(frozen=True, slots=True)
class SourceDetail:
    source: DataSource
    fields: tuple[SourceField, ...]


@dataclass(frozen=True, slots=True)
class SourceCatalogPage:
    items: tuple[SourceDetail, ...]
    next_after_id: UUID | None


@dataclass(frozen=True, slots=True)
class SourceMutationResult:
    source: DataSource
    change: CatalogChange


def _source_name(name: str) -> str:
    if not isinstance(name, str):
        raise SpatialValidationError("source name must be text")
    cleaned = name.strip()
    if not 1 <= len(cleaned) <= 200 or "\x00" in cleaned:
        raise SpatialValidationError("source name outside bounds")
    try:
        cleaned.encode("utf-8")
    except UnicodeError:
        raise SpatialValidationError("source name has invalid encoding") from None
    return cleaned


@dataclass(slots=True)
class SpatialCatalogService:
    """One authorized request transaction; no independent commit or storage locator."""

    repository: SpatialSourceRepository

    def _active(self, *, context: AuthorizationContext, source_id: UUID) -> DataSource:
        source = self.repository.get_source(context=context, source_id=source_id, lock=True)
        if source is None or source.lifecycle != Lifecycle.ACTIVE:
            raise TenantResourceNotFoundError("resource not found")
        return source

    def _detail(self, *, context: AuthorizationContext, source: DataSource) -> SourceDetail:
        fields = tuple(self.repository.get_fields(context=context, source_id=source.id))
        if any(
            (f.organization_id, f.project_id, f.source_id, f.schema_revision)
            != (source.organization_id, source.project_id, source.id, source.schema_revision)
            for f in fields
        ):
            raise SpatialValidationError("catalog schema scope or pin disagrees")
        if (
            schema_revision_digest(
                fields,
                source.geometry_family,
                source.dimensions,
                schema_state=source.schema_state,
            )
            != source.schema_revision
        ):
            raise SpatialValidationError("catalog schema revision disagrees")
        return SourceDetail(source, fields)

    def list_sources(
        self,
        *,
        context: AuthorizationContext,
        after_id: UUID | None,
        limit: int,
    ) -> SourceCatalogPage:
        self.repository.prepare_scope(
            context=context,
            permission=Permission.PROJECT_READ,
            mutation=False,
        )
        if type(limit) is not int or not 1 <= limit <= 100:
            raise SpatialValidationError("catalog limit out of bounds")
        sources = self.repository.list_sources(context=context, after_id=after_id, limit=limit + 1)
        visible = sources[:limit]
        items = tuple(self._detail(context=context, source=source) for source in visible)
        return SourceCatalogPage(items, visible[-1].id if len(sources) > limit else None)

    def get_source(self, *, context: AuthorizationContext, source_id: UUID) -> SourceDetail:
        self.repository.prepare_scope(
            context=context,
            permission=Permission.PROJECT_READ,
            mutation=False,
        )
        return self._detail(
            context=context, source=self._active(context=context, source_id=source_id)
        )

    def register_source(
        self,
        *,
        context: AuthorizationContext,
        reference_key: str,
        name: str,
    ) -> SourceMutationResult:
        self.repository.prepare_scope(
            context=context,
            permission=Permission.PROJECT_EDIT,
            mutation=True,
        )
        clean_name = _source_name(name)
        if (
            self.repository.find_source_by_reference_key(
                context=context, reference_key=reference_key
            )
            is not None
        ):
            raise SpatialSourceAlreadyRegisteredError("reference fixture already registered")
        now = datetime.now(UTC)
        source, fields, features = self.repository.prepare_reference_source(
            context=context,
            reference_key=reference_key,
            source_id=uuid4(),
            name=clean_name,
            now=now,
        )
        evidence = build_mutation_evidence(
            context=context,
            prior=None,
            current=source,
            operation=CatalogOperation.REGISTER_SOURCE,
            now=now,
        )
        self.repository.insert_source(source, fields, features, context=context)
        self.repository.append_change(evidence.change, evidence.audit, context=context)
        return SourceMutationResult(source, evidence.change)

    def update_source(
        self,
        *,
        context: AuthorizationContext,
        source_id: UUID,
        expected_revision: int,
        name: str | None = None,
        declared_crs: int | None = None,
    ) -> SourceMutationResult:
        self.repository.prepare_scope(
            context=context,
            permission=Permission.PROJECT_EDIT,
            mutation=True,
        )
        prior = self._active(context=context, source_id=source_id)
        revision = next_revision(prior.catalog_revision, expected_revision)
        clean_name = _source_name(name) if name is not None else prior.name
        now = datetime.now(UTC)
        if declared_crs is not None and (
            declared_crs != prior.source_crs or prior.validation_state != ValidationState.READY
        ):
            current = self.repository.correct_reference_source(
                context=context,
                source=prior,
                declared_crs=declared_crs,
                now=now,
            )
            current = replace(current, name=clean_name)
            operation = CatalogOperation.CORRECT_SOURCE_CRS
        else:
            if clean_name == prior.name:
                raise SpatialNoChangesError("source metadata did not change")
            current = replace(prior, name=clean_name, catalog_revision=revision, updated_at=now)
            operation = CatalogOperation.UPDATE_SOURCE
        if current.catalog_revision != revision:
            raise SpatialValidationError("source validation returned unexpected revision")
        evidence = build_mutation_evidence(
            context=context,
            prior=prior,
            current=current,
            operation=operation,
            now=now,
        )
        self.repository.update_source(current, context=context, expected_revision=expected_revision)
        self.repository.append_change(evidence.change, evidence.audit, context=context)
        return SourceMutationResult(current, evidence.change)

    def retire_source(
        self,
        *,
        context: AuthorizationContext,
        source_id: UUID,
        expected_revision: int,
    ) -> SourceMutationResult:
        self.repository.prepare_scope(
            context=context,
            permission=Permission.PROJECT_MANAGE,
            mutation=True,
        )
        prior = self._active(context=context, source_id=source_id)
        revision = next_revision(prior.catalog_revision, expected_revision)
        if self.repository.has_active_layers(context=context, source_id=source_id):
            raise SpatialActiveLayerDependenciesError(
                "Retire active Layers before retiring the source"
            )
        now = datetime.now(UTC)
        current = replace(
            prior,
            lifecycle=Lifecycle.RETIRED,
            retired_at=now,
            updated_at=now,
            catalog_revision=revision,
        )
        evidence = build_mutation_evidence(
            context=context,
            prior=prior,
            current=current,
            operation=CatalogOperation.RETIRE_SOURCE,
            now=now,
        )
        self.repository.update_source(current, context=context, expected_revision=expected_revision)
        self.repository.append_change(evidence.change, evidence.audit, context=context)
        return SourceMutationResult(current, evidence.change)
