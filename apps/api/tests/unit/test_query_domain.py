"""Exact R007 typed AST and bounded spatial input regressions."""

from decimal import Decimal
from uuid import uuid4

import pytest

from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.queries.domain import (
    compile_attribute_filter,
    compile_sort,
    parse_drawn_area,
)
from openvietgis_api.domains.spatial.domain import FieldType, SourceField


def fields():
    org, project, source = uuid4(), uuid4(), uuid4()
    return [
        SourceField(
            organization_id=org,
            project_id=project,
            source_id=source,
            field_id=name,
            name=name,
            ordinal=idx,
            type=field_type,
            nullable=True,
            schema_revision="a" * 64,
        )
        for idx, (name, field_type) in enumerate(
            [
                ("integer", FieldType.INTEGER),
                ("decimal", FieldType.DECIMAL),
                ("text", FieldType.TEXT),
                ("boolean", FieldType.BOOLEAN),
                ("timestamp", FieldType.TIMESTAMP),
            ]
        )
    ]


@pytest.mark.parametrize(
    "name,value",
    [
        ("integer", "1"),
        ("integer", True),
        ("integer", 1.5),
        ("integer", 2**31),
        ("decimal", 1.5),
        ("decimal", "NaN"),
        ("decimal", "1.00000000000000000001"),
        ("boolean", "true"),
        ("boolean", 1),
        ("text", 1),
        ("text", None),
        ("timestamp", "2026-11-21"),
        ("timestamp", "2026-11-21T01:02:03"),
    ],
)
def test_reject_invalid_typed_values(name, value):
    with pytest.raises(PlatformValidationError):
        compile_attribute_filter({"field": name, "op": "eq", "value": value}, fields())


@pytest.mark.parametrize(
    "node",
    [
        {},
        {"op": []},
        {"op": "and", "conditions": []},
        {"op": "or", "conditions": [1]},
        {"field": "text", "op": "is_null", "value": "false"},
        {"field": "integer", "op": "eq", "value": 1, "extra": "x"},
        {"field": "integer", "op": "between", "value": [2, 1]},
        {"field": "boolean", "op": "gt", "value": False},
        {"field": "boolean", "op": "between", "value": [False, True]},
        {"field": "text", "op": "in", "value": []},
        {"op": "and", "conditions": [{"field": "text", "op": "eq", "value": "x"}] * 101},
    ],
)
def test_reject_bad_ast(node):
    with pytest.raises(PlatformValidationError):
        compile_attribute_filter(node, fields())


def test_exact_sql_values_and_literal_wildcards():
    f = fields()
    compiled = compile_attribute_filter(
        {
            "op": "and",
            "conditions": [
                {"field": "decimal", "op": "eq", "value": "1.000000000000000001"},
                {"op": "not", "condition": {"field": "text", "op": "contains", "value": "%_Đ\\x"}},
                {"field": "boolean", "op": "eq", "value": False},
                {"field": "text", "op": "prefix", "value": ""},
            ],
        },
        f,
    )
    assert "::double" not in compiled.sql and "numeric" in compiled.sql
    assert (
        "strpos" in compiled.sql and "starts_with" in compiled.sql and "ILIKE" not in compiled.sql
    )
    assert compiled.params == {
        "qf_1": Decimal("1.000000000000000001"),
        "qf_2": "%_Đ\\x",
        "qf_3": False,
        "qf_4": "",
    }
    assert "numeric DESC NULLS LAST" in compile_sort(f, "decimal", "desc").replace(")", "")
    with pytest.raises(PlatformValidationError):
        compile_sort(f, "text", "descending")


def test_drawn_polygon_shape_bounds():
    polygon = {
        "type": "Polygon",
        "coordinates": [[[105.0, 21.0], [105.1, 21.0], [105.1, 21.1], [105.0, 21.0]]],
    }
    assert parse_drawn_area(polygon, 4326).srid == 4326
    for crs in (None, "4326", True, 9999):
        with pytest.raises(PlatformValidationError):
            parse_drawn_area(polygon, crs)
    for wrong in (
        {"type": "Point", "coordinates": [105, 21]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [2, 2]]]},
        {"type": "Polygon", "coordinates": [[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0]]]},
        {"type": "Polygon", "coordinates": [[[179, 0], [-179, 0], [-179, 1], [179, 0]]]},
    ):
        with pytest.raises(PlatformValidationError):
            parse_drawn_area(wrong, 4326)
