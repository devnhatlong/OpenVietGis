"""DXF writer round-trip checks for units and unsupported topology."""

from __future__ import annotations

import io

import ezdxf
import pytest

from openvietgis_api.adapters.cad.dxf_codec import write_dxf_2d
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
