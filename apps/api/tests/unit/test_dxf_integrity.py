"""DXF writer round-trip checks for units and unsupported topology."""

from __future__ import annotations

import io
import math

import ezdxf
import pytest

from openvietgis_api.adapters.cad.dxf_codec import parse_dxf_2d, write_dxf_2d
from openvietgis_api.domains.cad.domain import CadUnit
from openvietgis_api.domains.platform_errors import PlatformValidationError


@pytest.mark.parametrize(
    ("unit", "expected_header", "factor"),
    [
        (CadUnit.METER, 6, 1),
        (CadUnit.CENTIMETER, 5, 100),
        (CadUnit.MILLIMETER, 4, 1000),
    ],
)
def test_dxf_declares_length_units(unit, expected_header, factor):
    source = [{"feature_id": "p", "geometry": {"type": "Point", "coordinates": [1.5, 2.5]}}]
    raw = write_dxf_2d(source, layer_name="Control", units=unit)
    doc = ezdxf.read(io.StringIO(raw.decode("utf-8")))
    assert doc.header["$INSUNITS"] == expected_header
    loc = list(doc.modelspace())[0].dxf.location
    assert (loc.x, loc.y) == (1.5 * factor, 2.5 * factor)


@pytest.mark.parametrize(
    "geometry",
    [
        None,
        {"type": "MultiPoint", "coordinates": [[0, 0], [1, 1]]},
        {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [3, 0], [3, 3], [0, 0]],
                [[1, 1], [2, 1], [2, 2], [1, 1]],
            ],
        },
    ],
)
def test_unsupported_topology_is_not_silently_omitted(geometry):
    with pytest.raises(PlatformValidationError):
        write_dxf_2d(
            [{"feature_id": "bad", "geometry": geometry}], layer_name="Control", units=CadUnit.METER
        )


def _encode_doc(doc):
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def test_declared_import_units_mismatch():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_point((1, 2))
    with pytest.raises(PlatformValidationError, match="units do not match"):
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER)
    family, records, _, _ = parse_dxf_2d(_encode_doc(doc), units=CadUnit.MILLIMETER)
    assert family == "Point"
    assert records[0]["geometry"]["coordinates"] == [0.001, 0.002]


def test_bulged_polyline_is_not_silently_straightened():
    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0, 1), (10, 0, 0)], format="xyb")
    with pytest.raises(PlatformValidationError, match="bulges"):
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER)


def test_nonstandard_ocs_is_not_silently_misplaced():
    doc = ezdxf.new("R2010")
    doc.modelspace().add_circle((1, 2), 1, dxfattribs={"extrusion": (0, 0, -1)})
    with pytest.raises(PlatformValidationError, match="extrusion"):
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER)


@pytest.mark.parametrize("bulge", [1.0, -1.0, 0.5, -0.5, 2.0, -2.0])
def test_bulge_signed_arc_tolerance_and_independent_roundtrip(bulge):
    doc = ezdxf.new("R2010")
    ent = doc.modelspace().add_lwpolyline([(0, 0, bulge), (10, 0, 0)], format="xyb")
    tol = 0.02
    family, records, summary, loss = parse_dxf_2d(
        _encode_doc(doc), units=CadUnit.METER, curve_tolerance_m=tol
    )
    assert family == "LineString"
    pts = records[0]["geometry"]["coordinates"]
    assert pts[0] == [0, 0] and pts[-1] == [10, 0]
    assert len(pts) > 2
    assert math.copysign(1, pts[len(pts) // 2][1]) == -math.copysign(1, bulge)
    # Independent ezdxf bulge_to_arc implementation gives the control circle.
    center, _, _, radius = ezdxf.math.bulge_to_arc((0, 0), (10, 0), bulge)
    for pt in pts:
        assert math.dist(pt, (center.x, center.y)) == pytest.approx(radius, abs=1e-10)
    measured = max(
        radius - math.dist(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), (center.x, center.y))
        for a, b in zip(pts[:-1], pts[1:], strict=True)
    )
    assert measured <= loss["curve_details"][0]["max_chord_deviation_grid_m"] <= tol
    assert summary["entity_mapping"][0]["handle"] == ent.dxf.handle
    assert summary["entity_mapping"][0]["disposition"] == "approximated"
    assert loss["requires_acknowledgement"] is True
    # Export is intentionally a straight-segment DXF, preserving the tessellated line.
    exported = write_dxf_2d(records, layer_name="Curves", units=CadUnit.MILLIMETER)
    reopened = ezdxf.read(io.StringIO(exported.decode()))
    line = list(reopened.modelspace())[0]
    assert line.dxftype() == "LWPOLYLINE"
    assert all(p[2] == 0 for p in line.get_points("xyb"))
    _, records2, _, loss2 = parse_dxf_2d(exported, units=CadUnit.MILLIMETER)
    for a, b in zip(pts, records2[0]["geometry"]["coordinates"], strict=True):
        assert a == pytest.approx(b)
    assert loss2["curve_approximations"] == []


def test_closed_two_bulges_and_last_edge_make_circle():
    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0, 1), (10, 0, 1)], format="xyb", close=True)
    family, records, _, loss = parse_dxf_2d(
        _encode_doc(doc), units=CadUnit.METER, curve_tolerance_m=0.01
    )
    pts = records[0]["geometry"]["coordinates"][0]
    assert family == "Polygon"
    assert pts[0] == pts[-1] == [0, 0]
    assert [10, 0] in pts
    assert min(p[1] for p in pts) < -4.9
    assert max(p[1] for p in pts) > 4.9
    assert loss["curve_details"][0]["max_chord_deviation_grid_m"] <= 0.01


def test_arc_crosses_zero_degrees_and_explicit_units():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_arc((1000000, 2000000), 10000, 350, 10)
    with pytest.raises(PlatformValidationError, match="curve_tolerance_m"):
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.MILLIMETER)
    family, records, summary, loss = parse_dxf_2d(
        _encode_doc(doc), units=CadUnit.MILLIMETER, curve_tolerance_m=0.001
    )
    pts = records[0]["geometry"]["coordinates"]
    assert family == "LineString"
    assert pts[0] == pytest.approx(
        [1000 + 10 * math.cos(math.radians(350)), 2000 + 10 * math.sin(math.radians(350))]
    )
    assert pts[-1] == pytest.approx(
        [1000 + 10 * math.cos(math.radians(10)), 2000 + 10 * math.sin(math.radians(10))]
    )
    assert all(p[0] >= 1009.8 for p in pts)
    assert summary["scale_to_meters"] == 0.001
    assert loss["curve_details"][0]["max_chord_deviation_grid_m"] <= 0.001


def test_circle_accuracy_and_position_limit():
    doc = ezdxf.new("R2010")
    doc.modelspace().add_circle((500000, 2300000), 20)
    family, records, _, loss = parse_dxf_2d(
        _encode_doc(doc), units=CadUnit.METER, curve_tolerance_m=0.01
    )
    pts = records[0]["geometry"]["coordinates"][0]
    assert family == "Polygon" and len(pts) > 32
    assert pts[0] == pts[-1]
    assert loss["curve_details"][0]["max_chord_deviation_grid_m"] <= 0.01
    doc.modelspace().add_circle((0, 0), 100000)
    with pytest.raises(PlatformValidationError) as exc:
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER, curve_tolerance_m=0.000001)
    assert exc.value.code == "CAD_CURVE_LIMIT"


@pytest.mark.parametrize("tolerance", [0, -1, float("nan"), float("inf"), 1001])
def test_curve_tolerance_must_be_finite_positive_and_bounded(tolerance):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_circle((0, 0), 10)
    with pytest.raises(PlatformValidationError) as exc:
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER, curve_tolerance_m=tolerance)
    assert exc.value.code == "INVALID_CAD_TOLERANCE"


@pytest.mark.parametrize("kind", ["elevation", "width", "zero_length_bulge"])
def test_no_silent_projection_or_ambiguous_bulge(kind):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    if kind == "elevation":
        msp.add_line((0, 0, 0), (1, 1, 2))
        code = "CAD_3D_UNSUPPORTED"
    elif kind == "width":
        msp.add_lwpolyline([(0, 0), (1, 1)], dxfattribs={"const_width": 1})
        code = "CAD_WIDTH_UNSUPPORTED"
    else:
        msp.add_lwpolyline([(0, 0, 1), (0, 0, 0)], format="xyb")
        code = "INVALID_DXF"
    with pytest.raises(PlatformValidationError) as exc:
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER, curve_tolerance_m=0.01)
    assert exc.value.code == code


def test_entity_inventory_accounts_for_exclusions():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (1, 0), dxfattribs={"layer": "A"})
    msp.add_line((1, 0), (2, 0), dxfattribs={"layer": "A"})
    msp.add_point((0, 0), dxfattribs={"layer": "B"})
    msp.add_text("Label", dxfattribs={"layer": "B"})
    family, _, summary, loss = parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER)
    assert family == "LineString"
    assert summary["layer_counts"] == {"A": 2, "B": 2}
    assert loss["unsupported_entities"] == {"TEXT": 1}
    assert loss["dropped_secondary_families"] == {"Point": 1}
    assert [e["disposition"] for e in summary["entity_mapping"]] == [
        "mapped",
        "mapped",
        "excluded_secondary_family",
        "unsupported",
    ]
    assert loss["requires_acknowledgement"] is True


@pytest.mark.parametrize("version", ["R2010", "R2013", "R2018"])
def test_supported_dxf_version_matrix(version):
    doc = ezdxf.new(version)
    doc.modelspace().add_point((1, 2))
    doc.modelspace().add_arc((0, 0), 10, 0, 90)
    family, _, summary, _ = parse_dxf_2d(
        _encode_doc(doc), units=CadUnit.METER, curve_tolerance_m=0.01
    )
    assert family == "LineString"
    assert summary["dxf_version"] == doc.dxfversion
    assert summary["profile"] == "dxf-2d-bounded-v1"


def test_old_dxf_profile_rejected():
    doc = ezdxf.new("R2007")
    doc.modelspace().add_point((1, 2))
    with pytest.raises(PlatformValidationError) as exc:
        parse_dxf_2d(_encode_doc(doc), units=CadUnit.METER)
    assert exc.value.code == "CAD_VERSION_UNSUPPORTED"


def test_export_rejects_non_xy_instead_of_truncating_z():
    with pytest.raises(PlatformValidationError, match="only 2D XY"):
        write_dxf_2d(
            [{"feature_id": "p", "geometry": {"type": "Point", "coordinates": [1, 2, 3]}}],
            layer_name="3D",
            units=CadUnit.METER,
        )
