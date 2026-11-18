"""Trusted R003 reference definitions and scoped, pinned candidate rows.

Registry entries are immutable synthetic/control definitions, not shared tenant
records, external connections, or caller-supplied geometry. Materialization
prepares NOT_READY rows only. The native database verification in T020 must
inspect the persisted rows before the registration transaction can claim ready
or a specific independently expected validation failure.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from openvietgis_api.domains.spatial.domain import (
    AttributeValue,
    DataSource,
    ExtentState,
    FeatureCountState,
    FieldType,
    GeometryDimensions,
    GeometryFamily,
    GeometryState,
    Lifecycle,
    NativeGeometry,
    ReferenceFeature,
    SchemaState,
    SourceField,
    SourceKind,
    SpatialValidationError,
    ValidationReason,
    ValidationReasonCode,
    ValidationState,
    canonical_attribute_value,
    canonical_manifest_digest,
)
from openvietgis_api.domains.spatial.service import PinnedSource, derive_source_pins

FIXTURE_VERSION = "r003-reference-v1"
_PROVISIONAL_PIN = "0" * 64
_EPOCH = datetime(2025, 1, 1, tzinfo=UTC)

type XY = tuple[float, float]
type Bounds = tuple[float, float, float, float]
type DMS = tuple[int, int, int]  # degrees, minutes, hundredths of an arc-second


class FixtureProvenance(StrEnum):
    SYNTHETIC = "synthetic"
    ANALYTIC_WEB_MERCATOR = "analytic_web_mercator"
    QUANG_NINH_CIRCULAR = "quang_ninh_circular_50_2025"
    QUANG_NINH_HVS = "quang_ninh_mae_eia_hvs"


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    field_id: str
    name: str
    type: FieldType
    nullable: bool


REFERENCE_FIELDS: tuple[FieldDefinition, ...] = (
    FieldDefinition("fld_feature_code", "Feature code", FieldType.TEXT, False),
    FieldDefinition("fld_name", "Name", FieldType.TEXT, False),
    FieldDefinition("fld_rank", "Rank", FieldType.INTEGER, False),
    FieldDefinition("fld_measure", "Measure", FieldType.DECIMAL, True),
    FieldDefinition("fld_active", "Active", FieldType.BOOLEAN, False),
    FieldDefinition("fld_observed_at", "Observed at", FieldType.TIMESTAMP, True),
    FieldDefinition("fld_note", "Note", FieldType.TEXT, True),
)


@dataclass(frozen=True, slots=True)
class FixtureRecord:
    """Unscoped immutable manifest facts, never a persisted feature row."""

    feature_id: str
    attributes: tuple[tuple[str, AttributeValue], ...]
    geometry: NativeGeometry | None
    geometry_state: GeometryState


@dataclass(frozen=True, slots=True)
class ReferenceFixture:
    key: str
    declared_crs: int | None
    stored_crs: int | None
    declared_family: GeometryFamily
    declared_dimensions: GeometryDimensions
    expected_family: GeometryFamily
    expected_dimensions: GeometryDimensions
    expected_count: int
    expected_native_bounds: Bounds | None
    provenance: FixtureProvenance
    expected_reason: ValidationReasonCode | None
    _record_factory: Callable[[], Iterator[FixtureRecord]]
    # Independent known control XY, not an input axis heuristic.
    axis_control_xy: XY | None = None
    # Only the named correctable manifest has evidence for this correction.
    correctable_to_crs: int | None = None
    version: str = FIXTURE_VERSION
    fields: tuple[FieldDefinition, ...] = REFERENCE_FIELDS

    @property
    def trusted_quang_ninh(self) -> bool:
        return self.provenance in (
            FixtureProvenance.QUANG_NINH_CIRCULAR,
            FixtureProvenance.QUANG_NINH_HVS,
        )

    def records(self) -> tuple[FixtureRecord, ...]:
        records = tuple(sorted(self._record_factory(), key=lambda row: row.feature_id))
        if len(records) != self.expected_count:
            raise SpatialValidationError("reference fixture count differs from manifest")
        return records


def _canonical_cents(cents: int) -> str:
    whole, fraction = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    fractional = f"{fraction:02d}".rstrip("0")
    return f"{sign}{whole}" + (f".{fractional}" if fractional else "")


def _attributes(
    sequence: int, feature_id: str, label: str
) -> tuple[tuple[str, AttributeValue], ...]:
    # All values come from the one-based sequence, never a live clock/row ID.
    cents = (sequence - 1) * 37 * (-1 if sequence % 2 == 0 else 1)
    observed = (_EPOCH + timedelta(minutes=sequence - 1)).isoformat()
    note = None if sequence % 5 == 0 else "" if sequence % 5 == 1 else f"note-{sequence:06d}"
    return (
        ("fld_feature_code", feature_id),
        ("fld_name", label),
        ("fld_rank", sequence % 1000),
        ("fld_measure", None if sequence % 7 == 0 else _canonical_cents(cents)),
        ("fld_active", sequence % 2 == 0),
        ("fld_observed_at", None if sequence % 11 == 0 else observed.removesuffix("+00:00") + "Z"),
        ("fld_note", note),
    )


def _record(
    feature_id: str,
    geometry: NativeGeometry | None,
    *,
    sequence: int = 1,
    label: str | None = None,
    state: GeometryState = GeometryState.PRESENT,
) -> FixtureRecord:
    return FixtureRecord(
        feature_id,
        _attributes(sequence, feature_id, label or f"Reference {feature_id}"),
        geometry,
        state,
    )


def _microdegrees(x: int, y: int) -> XY:
    return x / 1_000_000, y / 1_000_000


def _primary_records(
    family: GeometryFamily, prefix: str, label: str, count: int
) -> Iterator[FixtureRecord]:
    # Deterministic Vietnam test grid using integer microdegrees, not repeated
    # floating point addition or projected data generated by the tested engine.
    for sequence in range(1, count + 1):
        row, column = divmod(sequence - 1, 100)
        x = 106_600_000 + 1_000 * column
        y = 10_700_000 + 1_000 * row
        if family == GeometryFamily.POINT:
            geometry = NativeGeometry(family.value, _microdegrees(x, y), 4326)
        elif family == GeometryFamily.LINE_STRING:
            geometry = NativeGeometry(
                family.value,
                (
                    _microdegrees(x, y),
                    _microdegrees(x + 300, y + 200),
                    _microdegrees(x + 600, y + 100),
                ),
                4326,
            )
        elif family == GeometryFamily.POLYGON:
            geometry = NativeGeometry(
                family.value,
                ((
                    _microdegrees(x, y),
                    _microdegrees(x + 600, y),
                    _microdegrees(x + 600, y + 400),
                    _microdegrees(x, y + 400),
                    _microdegrees(x, y),
                ),),
                4326,
            )
        else:
            raise SpatialValidationError("unexpected primary reference geometry family")
        yield _record(
            f"{prefix}-{sequence:06d}",
            geometry,
            sequence=sequence,
            label=f"{label} {sequence:06d}",
        )


def _primary(
    key: str,
    family: GeometryFamily,
    prefix: str,
    label: str,
    count: int,
    bounds: Bounds,
) -> ReferenceFixture:
    return ReferenceFixture(
        key=key,
        declared_crs=4326,
        stored_crs=4326,
        declared_family=family,
        declared_dimensions=GeometryDimensions.XY,
        expected_family=family,
        expected_dimensions=GeometryDimensions.XY,
        expected_count=count,
        expected_native_bounds=bounds,
        provenance=FixtureProvenance.SYNTHETIC,
        expected_reason=None,
        _record_factory=lambda: _primary_records(family, prefix, label, count),
    )


def _fixed(
    key: str,
    records: tuple[FixtureRecord, ...],
    *,
    declared_crs: int | None = 4326,
    stored_crs: int | None = 4326,
    declared_family: GeometryFamily = GeometryFamily.POINT,
    declared_dimensions: GeometryDimensions = GeometryDimensions.XY,
    expected_family: GeometryFamily = GeometryFamily.POINT,
    expected_dimensions: GeometryDimensions = GeometryDimensions.XY,
    expected_native_bounds: Bounds | None = None,
    provenance: FixtureProvenance = FixtureProvenance.SYNTHETIC,
    expected_reason: ValidationReasonCode | None = None,
    axis_control_xy: XY | None = None,
    correctable_to_crs: int | None = None,
) -> ReferenceFixture:
    return ReferenceFixture(
        key=key,
        declared_crs=declared_crs,
        stored_crs=stored_crs,
        declared_family=declared_family,
        declared_dimensions=declared_dimensions,
        expected_family=expected_family,
        expected_dimensions=expected_dimensions,
        expected_count=len(records),
        expected_native_bounds=expected_native_bounds,
        provenance=provenance,
        expected_reason=expected_reason,
        _record_factory=lambda: iter(records),
        axis_control_xy=axis_control_xy,
        correctable_to_crs=correctable_to_crs,
    )


def _point(xy: XY, srid: int | None = 4326) -> NativeGeometry:
    return NativeGeometry("Point", xy, srid)


def _point_fixture(
    key: str, srid: int, controls: tuple[tuple[str, XY], ...], provenance: FixtureProvenance
) -> ReferenceFixture:
    records = tuple(
        _record(feature_id, _point(xy, srid), sequence=sequence)
        for sequence, (feature_id, xy) in enumerate(controls, start=1)
    )
    return _fixed(
        key,
        records,
        declared_crs=srid,
        stored_crs=srid,
        expected_native_bounds=(
            min(xy[0] for _, xy in controls), min(xy[1] for _, xy in controls),
            max(xy[0] for _, xy in controls), max(xy[1] for _, xy in controls),
        ),
        provenance=provenance,
    )


def _dms(value: DMS) -> float:
    degrees, minutes, hundredths = value
    return (degrees * 360_000 + minutes * 6_000 + hundredths) / 360_000


def _lonlat(lon: DMS, lat: DMS) -> XY:
    return _dms(lon), _dms(lat)


# Published independent coordinates, not results of PostGIS/PROJ.
# Circular 50/2025/TT-BXD appendix: five VN-2000/WGS84 pairs.
# These source fields are longitude first in the application, even though the
# source document displays latitude first; sec values below are hundredths.
_CIRCULAR: tuple[tuple[str, DMS, DMS, DMS, DMS], ...] = (
    ("VH1", (108, 1, 1000), (21, 24, 4000), (108, 1, 1680), (21, 24, 3640)),
    ("VH2", (108, 3, 3530), (21, 24, 5210), (108, 3, 4210), (21, 24, 4850)),
    ("VH10", (107, 56, 4600), (21, 14, 1050), (107, 56, 5280), (21, 14, 690)),
    ("CT1", (107, 45, 4080), (20, 58, 1430), (107, 45, 4760), (20, 58, 1070)),
    ("QY1", (106, 52, 5920), (20, 50, 780), (106, 53, 600), (20, 50, 420)),
)
# MAE EIA (July 2025), printed p.45 Table 1.4 and QH-04 drawing:
# X=northing, Y=easting in source; stored API XY = (easting, northing).
_HVS: tuple[tuple[str, XY, DMS, DMS, DMS, DMS], ...] = (
    ("HVS-QN1", (438442.69, 2291039.83),
     (107, 9, 3244), (20, 42, 4209), (107, 9, 3919), (20, 42, 3848)),
    ("HVS-QN2", (437957.55, 2291878.33),
     (107, 9, 1556), (20, 43, 930), (107, 9, 2231), (20, 43, 569)),
    ("HVS-QN3", (438891.96, 2292185.83),
     (107, 9, 4782), (20, 43, 1941), (107, 9, 5457), (20, 43, 1580)),
    ("HVS-QN4", (439365.92, 2291378.72),
     (107, 10, 430), (20, 42, 5322), (107, 10, 1105), (20, 42, 4961)),
)
_HVS_WGS = tuple((name, _lonlat(wlon, wlat)) for name, _, _, _, wlon, wlat in _HVS)
_HVS_QN1_WGS = _HVS_WGS[0][1]
_GOOD_POINT = _point((106.6, 10.7))
_GOOD_LINE = NativeGeometry("LineString", ((106.6, 10.7), (106.601, 10.701)), 4326)

# For this fixture-only registry, negative expected reasons are evidence
# predicates used by T020, not a claim that the database has verified the rows.
_FIXTURES: tuple[ReferenceFixture, ...] = (
    _primary("reference_points_4326", GeometryFamily.POINT, "point", "Point", 4000,
             (106.6, 10.7, 106.699, 10.739)),
    _primary("reference_lines_4326", GeometryFamily.LINE_STRING, "line", "Line", 3000,
             (106.6, 10.7, 106.6996, 10.7292)),
    _primary("reference_polygons_4326", GeometryFamily.POLYGON, "polygon", "Polygon", 3000,
             (106.6, 10.7, 106.6996, 10.7294)),
    # Independent Pseudo-Mercator formula evaluated at WGS controls
    # (106.6,10.7), (106.6996,10.7294), (107.157,20.715).
    _point_fixture(
        "reference_points_3857", 3857,
        (
            ("merc-000001", (11866657.718562961, 1198103.040560261)),
            ("merc-000002", (11877745.139845973, 1201433.906852360)),
            ("merc-000003", (11928662.674934816, 2357927.646019978)),
        ),
        FixtureProvenance.ANALYTIC_WEB_MERCATOR,
    ),
    _point_fixture(
        "reference_points_4756", 4756,
        tuple((name, _lonlat(vlon, vlat)) for name, vlon, vlat, _, _ in _CIRCULAR),
        FixtureProvenance.QUANG_NINH_CIRCULAR,
    ),
    _point_fixture(
        "reference_points_4326_quang_ninh", 4326,
        tuple((name, _lonlat(wlon, wlat)) for name, _, _, wlon, wlat in _CIRCULAR),
        FixtureProvenance.QUANG_NINH_CIRCULAR,
    ),
    _point_fixture(
        "reference_points_4756_hvs", 4756,
        tuple((name, _lonlat(vlon, vlat)) for name, _, vlon, vlat, _, _ in _HVS),
        FixtureProvenance.QUANG_NINH_HVS,
    ),
    _point_fixture(
        "reference_points_4326_hvs", 4326, _HVS_WGS, FixtureProvenance.QUANG_NINH_HVS,
    ),
    _point_fixture(
        "reference_points_5899", 5899,
        tuple((name, xy) for name, xy, _, _, _, _ in _HVS),
        FixtureProvenance.QUANG_NINH_HVS,
    ),
    # Valid WGS84 native point, negative for 4326 -> 3857 (not invalid source).
    _point_fixture(
        "reference_points_4326_webmerc_out_of_area", 4326,
        (("point-000001", (0.0, 86.0)),), FixtureProvenance.SYNTHETIC,
    ),
    _fixed("reference_empty_4326", ()),
    _fixed(
        "reference_unknown_crs", (_record("point-000001", _point((106.6, 10.7), None)),),
        declared_crs=None, stored_crs=None, expected_reason=ValidationReasonCode.MISSING_CRS,
    ),
    _fixed(
        "reference_conflicting_metadata", (_record("line-000001", _GOOD_LINE),),
        expected_family=GeometryFamily.LINE_STRING,
        expected_reason=ValidationReasonCode.GEOMETRY_FAMILY_MISMATCH,
    ),
    _fixed(
        "reference_unsupported_dimensions",
        (_record("point-000001", NativeGeometry("Point", (106.6, 10.7, 5.0), 4326,
                                                GeometryDimensions.XYZ),
                 state=GeometryState.UNSUPPORTED),),
        declared_dimensions=GeometryDimensions.XYZ,
        expected_dimensions=GeometryDimensions.XYZ,
        expected_reason=ValidationReasonCode.UNSUPPORTED_DIMENSIONS,
    ),
    _fixed(
        "reference_unsupported_dimensions_m",
        (_record("point-000001", NativeGeometry("Point", (106.6, 10.7, 7.0), 4326,
                                                GeometryDimensions.XYM),
                 state=GeometryState.UNSUPPORTED),),
        declared_dimensions=GeometryDimensions.XYM,
        expected_dimensions=GeometryDimensions.XYM,
        expected_reason=ValidationReasonCode.UNSUPPORTED_DIMENSIONS,
    ),
    _fixed(
        "reference_mixed_geometry",
        (_record("line-000001", _GOOD_LINE), _record("point-000001", _GOOD_POINT, sequence=2)),
        declared_family=GeometryFamily.MIXED,
        expected_family=GeometryFamily.MIXED,
        expected_reason=ValidationReasonCode.UNSUPPORTED_GEOMETRY,
    ),
    _fixed(
        "reference_unsupported_family",
        (_record("multipoint-000001",
                 NativeGeometry("MultiPoint", ((106.6, 10.7), (106.601, 10.701)), 4326),
                 state=GeometryState.UNSUPPORTED),),
        declared_family=GeometryFamily.UNSUPPORTED,
        expected_family=GeometryFamily.UNSUPPORTED,
        expected_reason=ValidationReasonCode.UNSUPPORTED_GEOMETRY,
    ),
    _fixed(
        "reference_null_geometry",
        (_record("point-000001", None, state=GeometryState.ABSENT),),
        stored_crs=None,
        expected_family=GeometryFamily.UNKNOWN,
        expected_dimensions=GeometryDimensions.UNKNOWN,
        expected_reason=ValidationReasonCode.NULL_GEOMETRY,
    ),
    _fixed(
        "reference_empty_geometry",
        (_record("point-000001", NativeGeometry("Point", (), 4326), state=GeometryState.EMPTY),),
        expected_reason=ValidationReasonCode.EMPTY_GEOMETRY,
    ),
    _fixed(
        "reference_invalid_geometry",
        (_record("polygon-000001", NativeGeometry(
            "Polygon", (((106.6, 10.7), (106.601, 10.701), (106.6, 10.701),
                         (106.601, 10.7), (106.6, 10.7)),), 4326,
        ), state=GeometryState.INVALID),),
        declared_family=GeometryFamily.POLYGON,
        expected_family=GeometryFamily.POLYGON,
        expected_reason=ValidationReasonCode.INVALID_GEOMETRY,
    ),
    _fixed(
        "reference_axis_conflict",
        (_record("HVS-QN1", _point((_HVS_QN1_WGS[1], _HVS_QN1_WGS[0])),
                 state=GeometryState.INVALID),),
        provenance=FixtureProvenance.QUANG_NINH_HVS,
        expected_reason=ValidationReasonCode.AXIS_CONFLICT,
        axis_control_xy=_HVS_QN1_WGS,
    ),
    _fixed(
        "reference_out_of_domain",
        (_record("point-000001", _point((106.6, 91.0)), state=GeometryState.INVALID),),
        expected_reason=ValidationReasonCode.COORDINATE_OUT_OF_DOMAIN,
    ),
    _fixed(
        "reference_definition_only_crs",
        (_record("point-000001", _point((500000.0, 1200000.0), 3405)),),
        declared_crs=3405, stored_crs=3405, expected_reason=ValidationReasonCode.UNSUPPORTED_CRS,
    ),
    _fixed(
        "reference_wrapping_extent",
        (_record("line-000001", NativeGeometry("LineString", ((179.9, 10.0), (-179.9, 10.0)),
                                              4326)),),
        declared_family=GeometryFamily.LINE_STRING,
        expected_family=GeometryFamily.LINE_STRING,
        expected_reason=ValidationReasonCode.EXTENT_WRAP_UNSUPPORTED,
    ),
    _fixed(
        "reference_correctable_crs",
        (_record("HVS-QN1", _point(_HVS_QN1_WGS)),),
        declared_crs=3857,
        stored_crs=4326,
        expected_native_bounds=(*_HVS_QN1_WGS, *_HVS_QN1_WGS),
        provenance=FixtureProvenance.QUANG_NINH_HVS,
        expected_reason=ValidationReasonCode.CRS_MISMATCH,
        axis_control_xy=_HVS_QN1_WGS,
        correctable_to_crs=4326,
    ),
)

REFERENCE_FIXTURES: Mapping[str, ReferenceFixture] = MappingProxyType(
    {fixture.key: fixture for fixture in _FIXTURES}
)


def get_reference_fixture(key: str) -> ReferenceFixture | None:
    """Exact allowlisted logical alias; never interpret it as a storage locator."""
    if not isinstance(key, str):
        return None
    return REFERENCE_FIXTURES.get(key)


def materialize_reference_fixture(
    key: str,
    *,
    organization_id: UUID,
    project_id: UUID,
    source_id: UUID,
    name: str,
    now: datetime,
) -> PinnedSource:
    """Bind new candidate rows to the server-selected scope and source identity.

    The caller authorizes the project, allocates the source UUID and performs
    insertion/actual native verification/audit in one transaction. No SQL
    execution, external input or commit happens here; metadata is provisional.
    """
    fixture = get_reference_fixture(key)
    if fixture is None:
        raise SpatialValidationError("unknown reference fixture")
    fields = tuple(
        SourceField(
            organization_id, project_id, source_id, field.field_id, field.name,
            ordinal, field.type, field.nullable, _PROVISIONAL_PIN,
        )
        for ordinal, field in enumerate(fixture.fields)
    )
    field_by_id = {field.field_id: field for field in fields}
    features: list[ReferenceFeature] = []
    for record in fixture.records():
        values = dict(record.attributes)
        if len(values) != len(record.attributes) or set(values) != set(field_by_id):
            raise SpatialValidationError("reference fixture attributes differ from schema")
        attributes = {
            field_id: canonical_attribute_value(field_by_id[field_id], value)
            for field_id, value in values.items()
        }
        features.append(
            ReferenceFeature(
                organization_id, project_id, source_id, record.feature_id, attributes,
                record.geometry, record.geometry_state, _PROVISIONAL_PIN, _PROVISIONAL_PIN,
            )
        )
    source = DataSource(
        id=source_id,
        organization_id=organization_id,
        project_id=project_id,
        name=name,
        kind=SourceKind.REFERENCE_FIXTURE,
        reference_key=fixture.key,
        fixture_version=fixture.version,
        manifest_digest=_PROVISIONAL_PIN,
        source_asset_id=None,
        lifecycle=Lifecycle.ACTIVE,
        validation_state=ValidationState.NOT_READY,
        validation_reason=ValidationReason(
            ValidationReasonCode.FIXTURE_UNAVAILABLE,
            "Reference fixture awaits native verification.",
        ),
        source_crs=fixture.declared_crs,
        stored_crs=fixture.stored_crs,
        schema_state=SchemaState.KNOWN,
        geometry_family=fixture.expected_family,
        dimensions=fixture.expected_dimensions,
        feature_count_state=FeatureCountState.KNOWN,
        feature_count=len(features),
        extent_state=ExtentState.UNAVAILABLE,
        extent=None,
        catalog_revision=1,
        content_revision=_PROVISIONAL_PIN,
        schema_revision=_PROVISIONAL_PIN,
        created_at=now,
        updated_at=now,
        retired_at=None,
    )
    pinned = derive_source_pins(source, fields, features)
    # Include canonical geometry/attribute/schema pins rather than merely a
    # generator label. The immutable original manifest also pins declaration,
    # provenance, independent expected metadata and correction/axis evidence.
    manifest_digest = canonical_manifest_digest({
        "manifest_type": "r003-reference-fixture-v1",
        "key": fixture.key,
        "version": fixture.version,
        "declared_crs": fixture.declared_crs,
        "stored_crs": fixture.stored_crs,
        "declared_family": fixture.declared_family.value,
        "declared_dimensions": fixture.declared_dimensions.value,
        "expected_family": fixture.expected_family.value,
        "expected_dimensions": fixture.expected_dimensions.value,
        "expected_count": fixture.expected_count,
        "expected_native_bounds": fixture.expected_native_bounds,
        "provenance": fixture.provenance.value,
        "expected_reason": fixture.expected_reason.value if fixture.expected_reason else None,
        "axis_control_xy": fixture.axis_control_xy,
        "correctable_to_crs": fixture.correctable_to_crs,
        "schema_revision": pinned.source.schema_revision,
        "content_revision": pinned.source.content_revision,
    })
    return PinnedSource(
        replace(pinned.source, manifest_digest=manifest_digest), pinned.fields, pinned.features
    )
