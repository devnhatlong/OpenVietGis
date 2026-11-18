"""R003 server-derived pins and actual safe mutation evidence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.spatial.domain import (
    CatalogOperation,
    DataSource,
    ExtentState,
    FeatureCountState,
    GeometryDimensions,
    GeometryFamily,
    Layer,
    Lifecycle,
    SchemaState,
    SourceKind,
    SpatialValidationError,
    ValidationReason,
    ValidationReasonCode,
    ValidationState,
)
from openvietgis_api.domains.spatial.ports import SpatialRevisionConflictError, SpatialScopeError
from openvietgis_api.domains.spatial.service import (
    build_mutation_evidence,
    derive_source_pins,
    next_revision,
    verify_source_pins,
)

NOW = datetime(2025, 1, 1, tzinfo=UTC)
LATER = NOW + timedelta(minutes=1)


def _source() -> DataSource:
    return DataSource(
        id=uuid4(), organization_id=uuid4(), project_id=uuid4(),
        name="Empty reference", kind=SourceKind.REFERENCE_FIXTURE,
        reference_key="reference_empty_4326", fixture_version="v1", manifest_digest="a"*64,
        source_asset_id=None, lifecycle=Lifecycle.ACTIVE,
        validation_state=ValidationState.READY, validation_reason=None,
        source_crs=4326, stored_crs=4326, schema_state=SchemaState.KNOWN,
        geometry_family=GeometryFamily.POINT, dimensions=GeometryDimensions.XY,
        feature_count_state=FeatureCountState.KNOWN, feature_count=0,
        extent_state=ExtentState.EMPTY, extent=None, catalog_revision=1,
        content_revision="b"*64, schema_revision="c"*64,
        created_at=NOW, updated_at=NOW, retired_at=None,
    )


def _context(source: DataSource | Layer) -> AuthorizationContext:
    return AuthorizationContext(
        Actor("human", uuid4(), "Synthetic owner"),
        source.organization_id, project_id=source.project_id,
    )


def test_manifest_pins_derived_not_trusted_and_resource_identity_independent() -> None:
    raw = _source()
    with pytest.raises(SpatialValidationError, match="canonical manifest"):
        verify_source_pins(raw, (), ())
    pinned = derive_source_pins(raw, (), ())
    verify_source_pins(pinned.source, pinned.fields, pinned.features)
    other = derive_source_pins(_source(), (), ())
    assert pinned.source.content_revision == other.source.content_revision
    assert pinned.source.schema_revision == other.source.schema_revision
    assert pinned.source.content_revision != raw.content_revision
    assert pinned.source.schema_revision != raw.schema_revision


def test_source_rename_evidence_actual_values_and_stable_read_pins() -> None:
    source = derive_source_pins(_source(), (), ()).source
    renamed = replace(source, name="Renamed", catalog_revision=next_revision(1, 1),
                      updated_at=LATER)
    evidence = build_mutation_evidence(
        context=_context(source), prior=source, current=renamed,
        operation=CatalogOperation.UPDATE_SOURCE, now=LATER,
    )
    assert evidence.change.prior_revision == source.revision
    assert evidence.change.new_revision == renamed.revision
    assert {item.field: (item.old_value,item.new_value) for item in evidence.change.changes} == {
        "name": ("Empty reference", "Renamed"), "catalog_revision": (1, 2),
    }
    assert renamed.content_revision == source.content_revision
    assert renamed.schema_revision == source.schema_revision
    assert evidence.audit.id == evidence.change.audit_event_id
    assert evidence.audit.resource_id == source.id
    assert evidence.audit.metadata == {
        "project_id": str(source.project_id), "catalog_change_id": str(evidence.change.id)
    }


def test_noop_and_cross_project_mutation_rejected() -> None:
    source = derive_source_pins(_source(), (), ()).source
    with pytest.raises(SpatialValidationError):
        build_mutation_evidence(
            context=_context(source), prior=source,
            current=replace(source, catalog_revision=2, updated_at=LATER),
            operation=CatalogOperation.UPDATE_SOURCE, now=LATER,
        )
    with pytest.raises(SpatialScopeError):
        build_mutation_evidence(
            context=_context(_source()), prior=source,
            current=replace(source, name="New", catalog_revision=2, updated_at=LATER),
            operation=CatalogOperation.UPDATE_SOURCE, now=LATER,
        )
    with pytest.raises(SpatialRevisionConflictError):
        next_revision(1, 2)
    with pytest.raises(SpatialRevisionConflictError):
        next_revision(1, True)


def test_crs_correction_changes_content_and_preserves_schema() -> None:
    invalid = replace(
        _source(), source_crs=3857, validation_state=ValidationState.INVALID,
        validation_reason=ValidationReason(ValidationReasonCode.CRS_MISMATCH, "Declared CRS mismatch"),
        extent_state=ExtentState.UNAVAILABLE,
    )
    old = derive_source_pins(invalid, (), ()).source
    corrected = derive_source_pins(replace(
        old, source_crs=4326, validation_state=ValidationState.READY,
        validation_reason=None, extent_state=ExtentState.EMPTY,
        catalog_revision=2, updated_at=LATER,
    ), (), ()).source
    evidence = build_mutation_evidence(
        context=_context(old), prior=old, current=corrected,
        operation=CatalogOperation.CORRECT_SOURCE_CRS, now=LATER,
    )
    assert old.stored_crs == corrected.stored_crs == 4326
    assert old.content_revision != corrected.content_revision
    assert old.schema_revision == corrected.schema_revision
    assert any(change.field == "source_crs" for change in evidence.change.changes)


def test_layer_rename_and_retirement_evidence() -> None:
    source = _source()
    layer = Layer(
        uuid4(), source.organization_id, source.project_id, source.id, "Layer",
        Lifecycle.ACTIVE, 1, NOW, NOW, None
    )
    context = _context(layer)
    created = build_mutation_evidence(
        context=context, prior=None, current=layer,
        operation=CatalogOperation.CREATE_LAYER, now=NOW,
    )
    assert created.change.prior_revision is None
    renamed = replace(layer, name="Renamed", layer_revision=2, updated_at=LATER)
    evidence = build_mutation_evidence(context=context, prior=layer, current=renamed,
        operation=CatalogOperation.RENAME_LAYER, now=LATER)
    assert {x.field for x in evidence.change.changes} == {"name", "layer_revision"}
    retired = replace(layer, layer_revision=2, lifecycle=Lifecycle.RETIRED,
                      updated_at=LATER, retired_at=LATER)
    stopped = build_mutation_evidence(context=context, prior=layer, current=retired,
        operation=CatalogOperation.RETIRE_LAYER, now=LATER)
    assert {x.field for x in stopped.change.changes} == {"lifecycle", "layer_revision"}
