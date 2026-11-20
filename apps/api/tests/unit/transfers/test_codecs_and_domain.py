"""Unit tests for R005 format codecs, archive hostility, loss matrix, and job transitions."""

from __future__ import annotations

import io
import json
import zipfile
from uuid import uuid4

import pytest
import shapefile  # type: ignore[import-untyped]

from openvietgis_api.adapters.formats.geojson import parse_geojson, write_geojson
from openvietgis_api.adapters.formats.geopackage import (
    inspect_geopackage,
    parse_geopackage_member,
    write_geopackage,
)
from openvietgis_api.adapters.formats.registry import VectorFormatRegistry
from openvietgis_api.adapters.formats.shapefile_zip import (
    inspect_shapefile_zip,
    parse_shapefile_member,
    write_shapefile_zip,
)
from openvietgis_api.domains.spatial.domain import FieldType, NativeGeometry, SourceField
from openvietgis_api.domains.transfers.domain import (
    ExportFieldMapping,
    JobStatus,
    TransferFormat,
    can_transition,
    plan_export_mapping,
)
from openvietgis_api.domains.transfers.ports import (
    TransferFormatError,
    TransferLimitExceededError,
)


def _sample_fields() -> list[SourceField]:
    org, proj, src = uuid4(), uuid4(), uuid4()
    rev = "a" * 64
    specs = [
        ("code", "Code", FieldType.TEXT, False, 0),
        ("long_description_field", "Long Desc", FieldType.TEXT, True, 1),
        ("rank", "Rank", FieldType.INTEGER, True, 2),
        ("measure", "Measure", FieldType.DECIMAL, True, 3),
        ("active", "Active", FieldType.BOOLEAN, True, 4),
        ("observed_at", "Observed At", FieldType.TIMESTAMP, True, 5),
    ]
    return [
        SourceField(
            organization_id=org,
            project_id=proj,
            source_id=src,
            field_id=fid,
            name=name,
            ordinal=ordinal,
            type=ftype,
            nullable=nullable,
            schema_revision=rev,
        )
        for fid, name, ftype, nullable, ordinal in specs
    ]


def test_detect_format_by_content_not_extension() -> None:
    reg = VectorFormatRegistry()
    gpkg_bytes, _, _ = write_geopackage(
        layer_name="pts",
        crs_code=4326,
        geometry_family="Point",
        field_mappings=[ExportFieldMapping("name", "Name", "name", FieldType.TEXT)],
        features=[("p1", {"name": "Alpha"}, NativeGeometry("Point", (106.6, 10.7), 4326))],
    )
    assert reg.detect_format(gpkg_bytes) == TransferFormat.GEOPACKAGE
    assert (
        reg.detect_format(b'{"type":"FeatureCollection","features":[]}') == TransferFormat.GEOJSON
    )
    with pytest.raises(TransferFormatError) as exc:
        reg.detect_format(b"NOT A VALID GIS FILE")
    assert exc.value.code == "UNSUPPORTED_FORMAT"


def test_geopackage_round_trip_preserves_null_empty_zero_false() -> None:
    mappings = [
        ExportFieldMapping("note", "Note", "note", FieldType.TEXT),
        ExportFieldMapping("rank", "Rank", "rank", FieldType.INTEGER),
        ExportFieldMapping("measure", "Measure", "measure", FieldType.DECIMAL),
        ExportFieldMapping("active", "Active", "active", FieldType.BOOLEAN),
        ExportFieldMapping("observed_at", "Observed", "observed_at", FieldType.TIMESTAMP),
    ]
    features = [
        (
            "pt-1",
            {
                "note": "",
                "rank": 0,
                "measure": "0",
                "active": False,
                "observed_at": "2026-11-20T00:00:00Z",
            },
            NativeGeometry("Point", (106.6, 10.7), 4326),
        ),
        (
            "pt-2",
            {
                "note": None,
                "rank": None,
                "measure": None,
                "active": None,
                "observed_at": None,
            },
            NativeGeometry("Point", (106.7, 10.8), 4326),
        ),
    ]
    gpkg, ext, ctype = write_geopackage(
        layer_name="Ref Points",
        crs_code=4326,
        geometry_family="Point",
        field_mappings=mappings,
        features=features,
    )
    assert ext == "gpkg" and ctype == "application/geopackage+sqlite3"
    members = inspect_geopackage(gpkg)
    assert len(members) == 1 and members[0].eligible and members[0].detected_crs == 4326
    parsed = parse_geopackage_member(gpkg, member_name=members[0].name)
    assert not parsed.findings
    assert len(parsed.features) == 2
    assert parsed.features[0].feature_id == "pt-1"
    assert parsed.features[0].attributes["note"] == ""
    assert parsed.features[0].attributes["rank"] == 0
    assert parsed.features[0].attributes["active"] is False
    assert parsed.features[1].attributes == {
        "note": None,
        "rank": None,
        "measure": None,
        "active": None,
        "observed_at": None,
    }


def test_geojson_rejects_legacy_crs_and_mixed_geometries() -> None:
    legacy = json.dumps(
        {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:3857"}},
            "features": [],
        }
    ).encode("utf-8")
    with pytest.raises(TransferFormatError) as exc:
        parse_geojson(legacy)
    assert exc.value.code == "LEGACY_GEOJSON_CRS"

    mixed = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [106.6, 10.7]},
                    "properties": {},
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[106.6, 10.7], [106.7, 10.8]],
                    },
                    "properties": {},
                },
            ],
        }
    ).encode("utf-8")
    parsed = parse_geojson(mixed)
    assert any(f.code == "MIXED_GEOMETRY_FAMILY" for f in parsed.findings)

    out, ext, _ = write_geojson(
        field_mappings=[ExportFieldMapping("name", "Name", "name", FieldType.TEXT)],
        features=[("p1", {"name": "Hanoi"}, NativeGeometry("Point", (105.85, 21.02), 4326))],
    )
    assert ext == "geojson"
    reparsed = parse_geojson(out)
    assert len(reparsed.features) == 1 and reparsed.features[0].attributes["name"] == "Hanoi"


def test_shapefile_zip_rejects_path_traversal_and_detects_missing_crs_encoding() -> None:
    # 1. Hostile path traversal ZIP
    bad_zip = io.BytesIO()
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../escape.shp", b"evil")
    with pytest.raises(TransferFormatError) as exc:
        inspect_shapefile_zip(bad_zip.getvalue())
    assert exc.value.code == "ARCHIVE_PATH_TRAVERSAL"

    # 2. Entry count bomb (>64 entries)
    many_zip = io.BytesIO()
    with zipfile.ZipFile(many_zip, "w") as zf:
        for i in range(70):
            zf.writestr(f"f{i}.txt", b"x")
    with pytest.raises(TransferLimitExceededError) as exc2:
        inspect_shapefile_zip(many_zip.getvalue())
    assert exc2.value.code == "ARCHIVE_ENTRY_LIMIT_EXCEEDED"

    # 3. Missing .prj and non-ASCII without .cpg -> requires explicit CRS & encoding resolution
    shp_b, shx_b, dbf_b = io.BytesIO(), io.BytesIO(), io.BytesIO()
    w = shapefile.Writer(
        shp=shp_b, shx=shx_b, dbf=dbf_b, shapeType=shapefile.POINT, encoding="utf-8"
    )
    w.field("NAME", "C", size=50)
    w.point(106.6, 10.7)
    w.record("Hà Nội")
    w.close()
    raw_zip = io.BytesIO()
    with zipfile.ZipFile(raw_zip, "w") as zf:
        zf.writestr("cities.shp", shp_b.getvalue())
        zf.writestr("cities.shx", shx_b.getvalue())
        zf.writestr("cities.dbf", dbf_b.getvalue())
    parsed = parse_shapefile_member(raw_zip.getvalue(), member_name="cities")
    assert parsed.detected_crs is None
    assert parsed.requires_encoding_resolution is True

    resolved = parse_shapefile_member(
        raw_zip.getvalue(),
        member_name="cities",
        declared_crs=4326,
        declared_encoding="utf-8",
    )
    assert resolved.requires_encoding_resolution is False
    assert resolved.features[0].attributes["NAME"] == "Hà Nội"

    # 4. Write ZIP Shapefile with explicit .prj & .cpg
    out_zip, ext, _ = write_shapefile_zip(
        layer_name="Parcels",
        crs_code=4326,
        geometry_family="Point",
        field_mappings=[ExportFieldMapping("name", "Name", "NAME", FieldType.TEXT)],
        features=[("p1", {"name": "Quảng Ninh"}, NativeGeometry("Point", (107.16, 20.71), 4326))],
    )
    assert ext == "zip"
    members = inspect_shapefile_zip(out_zip)
    assert (
        len(members) == 1
        and members[0].detected_crs == 4326
        and members[0].detected_encoding == "utf-8"
    )


def test_export_loss_matrix_and_job_state_machine() -> None:
    fields = _sample_fields()
    _, gpkg_disc, _ = plan_export_mapping(fields, TransferFormat.GEOPACKAGE, 4326, 4326)
    assert gpkg_disc == ()

    _, gj_disc, _ = plan_export_mapping(fields, TransferFormat.GEOJSON, 4326, 4326)
    assert any(d.code == "GEOJSON_TYPED_STRING_ENCODING" and d.requires_approval for d in gj_disc)
    with pytest.raises(ValueError):
        plan_export_mapping(fields, TransferFormat.GEOJSON, 4326, 3857)

    mappings, shp_disc, _ = plan_export_mapping(fields, TransferFormat.SHAPEFILE_ZIP, 4326, 4326)
    codes = {d.code for d in shp_disc if d.requires_approval}
    assert "DBF_FIELD_NAME_TRUNCATED" in codes
    assert "DBF_TIMESTAMP_AS_TEXT" in codes
    assert "DBF_DECIMAL_FIXED_PRECISION" in codes
    assert all(len(m.output_name) <= 10 for m in mappings)

    assert can_transition(JobStatus.RECOVERABLE_FAILED, JobStatus.ACTIVE)
    assert not can_transition(JobStatus.DENIED, JobStatus.ACTIVE)
    assert not can_transition(JobStatus.SUCCEEDED, JobStatus.CANCELLED)
