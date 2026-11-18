"""R003 revision and audit evidence primitives (no transaction commit)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID, uuid4

from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.authorization.context import AuthorizationContext
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
    content_revision_digest,
    schema_revision_digest,
    validate_source_contents,
)
from openvietgis_api.domains.spatial.ports import SpatialRevisionConflictError, SpatialScopeError
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
