"""R007 Attribute & Spatial Query pure typed AST compiler (zero arbitrary SQL)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.spatial.domain import FieldType, SourceField

MAX_QUERY_LIMIT = 500
MAX_AST_DEPTH = 6


class SpatialPredicate(StrEnum):
    INTERSECTS = "intersects"
    WITHIN = "within"
    CONTAINS = "contains"


@dataclass(frozen=True, slots=True)
class SavedQueryRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    layer_id: UUID
    name: str
    description: str
    attribute_filter: dict[str, Any] | None
    spatial_filter: dict[str, Any] | None
    sort_field: str | None
    sort_direction: str
    created_by_actor_id: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CompiledFilter:
    sql: str
    params: dict[str, Any]


def compile_attribute_filter(
    node: Mapping[str, Any] | None,
    fields: Sequence[SourceField],
) -> CompiledFilter:
    """Compile a typed visual filter AST into strictly parameterized PostgreSQL SQL."""
    if not node:
        return CompiledFilter(sql="TRUE", params={})
    field_map = {f.field_id: f for f in fields}
    params: dict[str, Any] = {}
    counter = [0]

    def _next_param(val: Any) -> str:
        counter[0] += 1
        key = f"qf_{counter[0]}"
        params[key] = val
        return f":{key}"

    def _compile(expr: Mapping[str, Any], depth: int) -> str:
        if depth > MAX_AST_DEPTH:
            raise PlatformValidationError(
                f"filter nesting exceeds max depth {MAX_AST_DEPTH}",
                code="QUERY_TOO_COMPLEX",
            )
        op = expr.get("op")
        if op in ("and", "or"):
            children = expr.get("conditions")
            if not isinstance(children, list) or not children:
                raise PlatformValidationError(
                    f"logical operator {op!r} requires non-empty conditions",
                    code="INVALID_FILTER",
                )
            joiner = " AND " if op == "and" else " OR "
            compiled = [_compile(c, depth + 1) for c in children]
            return "(" + joiner.join(compiled) + ")"
        if op == "not":
            child = expr.get("condition")
            if not isinstance(child, Mapping):
                raise PlatformValidationError(
                    "'not' operator requires 'condition' object", code="INVALID_FILTER"
                )
            return f"(NOT ({_compile(child, depth + 1)}))"

        field_id = expr.get("field")
        if not isinstance(field_id, str) or field_id not in field_map:
            raise PlatformValidationError(
                f"unknown or missing query field {field_id!r}",
                code="UNKNOWN_QUERY_FIELD",
            )
        field = field_map[field_id]
        # field_id is validated against known schema regex ^[A-Za-z][A-Za-z0-9_]{0,63}$
        json_text = f"(rf.attributes ->> '{field.field_id}')"

        if op == "is_null":
            want_null = bool(expr.get("value", True))
            return f"({json_text} IS NULL)" if want_null else f"({json_text} IS NOT NULL)"

        val = expr.get("value")
        if op == "contains":
            if field.type != FieldType.TEXT:
                raise PlatformValidationError(
                    f"'contains' only valid for text field {field.field_id!r}",
                    code="INVALID_OPERATOR",
                )
            p = _next_param(f"%{str(val)}%")
            return f"({json_text} ILIKE {p})"

        if op == "in":
            if not isinstance(val, list) or len(val) == 0 or len(val) > 100:
                raise PlatformValidationError(
                    "'in' operator requires 1..100 values", code="INVALID_FILTER"
                )
            placeholders = []
            for item in val:
                placeholders.append(_next_param(_coerce_value(item, field)))
            col_expr = _typed_column_expr(json_text, field)
            return f"({col_expr} IN ({', '.join(placeholders)}))"

        cmp_map = {
            "eq": "=",
            "neq": "!=",
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
        }
        if op not in cmp_map:
            raise PlatformValidationError(
                f"unsupported filter operator {op!r}", code="INVALID_OPERATOR"
            )
        if op in ("gt", "gte", "lt", "lte") and field.type == FieldType.BOOLEAN:
            raise PlatformValidationError(
                f"operator {op!r} is not supported for boolean field {field.field_id!r}",
                code="INVALID_OPERATOR",
            )
        coerced = _coerce_value(val, field)
        p = _next_param(coerced)
        col_expr = _typed_column_expr(json_text, field)
        return f"({col_expr} {cmp_map[op]} {p})"

    sql = _compile(node, 0)
    return CompiledFilter(sql=sql, params=params)


def _typed_column_expr(json_text: str, field: SourceField) -> str:
    if field.type == FieldType.INTEGER:
        return f"({json_text})::bigint"
    if field.type == FieldType.DECIMAL:
        return f"({json_text})::double precision"
    if field.type == FieldType.BOOLEAN:
        return f"({json_text})::boolean"
    return json_text


def _coerce_value(val: Any, field: SourceField) -> Any:
    if val is None:
        raise PlatformValidationError(
            f"use 'is_null' instead of null value for {field.field_id!r}",
            code="INVALID_FILTER",
        )
    if field.type == FieldType.INTEGER:
        if isinstance(val, bool):
            raise PlatformValidationError("expected integer", code="INVALID_FILTER")
        return int(val)
    if field.type == FieldType.DECIMAL:
        if isinstance(val, bool):
            raise PlatformValidationError("expected decimal", code="INVALID_FILTER")
        return float(val)
    if field.type == FieldType.BOOLEAN:
        if isinstance(val, bool):
            return val
        if str(val).lower() in ("true", "false"):
            return str(val).lower() == "true"
        raise PlatformValidationError("expected boolean", code="INVALID_FILTER")
    return str(val)
