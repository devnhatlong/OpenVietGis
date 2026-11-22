"""Preview and atomic import of GIS route hierarchies, without copying geometry."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import text
from openvietgis_api.domains.platform_errors import PlatformConflictError, PlatformValidationError

_PREFIX = re.compile(r"[1-9][0-9]*(?:/[1-9][0-9]*)*\Z")
_LIMIT = 5000


def _value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _prefix(parent: str, value: str) -> str:
    if not _PREFIX.fullmatch(value):
        raise ValueError("invalid_prefix")
    if not parent:
        if "/" in value:
            raise ValueError("prefix_must_be_one_level")
        return value
    if "/" not in value:
        return f"{parent}/{value}"
    if value.rsplit("/", 1)[0] != parent:
        raise ValueError("prefix_does_not_follow_parent")
    return value


def plan_routes(rows: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve dependencies; no row is ever written by the planner."""
    counts = Counter(r["code"] for r in rows)
    by_code = {r["code"]: r for r in rows if counts[r["code"]] == 1}
    by_id = {str(r["id"]): r for r in existing}
    by_saved_code: dict[str, list[dict[str, Any]]] = {}
    for r in existing:
        label = r.get("source_label", "")
        if label.startswith("route-tree-import:"):
            by_saved_code.setdefault(label.removeprefix("route-tree-import:"), []).append(r)
    by_feature: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in existing:
        by_feature.setdefault((str(r["linked_source_id"]), str(r["linked_feature_id"])), []).append(r)
    states: dict[str, int] = {}
    stack: list[dict[str, Any]] = []
    result: list[dict[str, Any]] = []

    def resolve(r: dict[str, Any]) -> None:
        key = r["key"]
        if states.get(key) == 2:
            return
        if states.get(key) == 1:
            for member in stack:
                if "cycle" not in member["errors"]:
                    member["errors"].append("cycle")
            return
        states[key] = 1
        stack.append(r)
        errors = r["errors"]
        if not r["code"] or len(r["code"]) > 160 or counts[r["code"]] > 1:
            errors.append("duplicate_or_empty_code")
        if not r["name"] or len(r["name"]) > 200:
            errors.append("invalid_name")
        found = by_feature.get((r["source_id"], r["feature_id"]), [])
        if len(found) > 1:
            errors.append("multiple_existing_routes")
        if len(found) == 1:
            r["existing_id"] = str(found[0]["id"])
        if any(str(old["id"]) != r.get("existing_id") for old in by_saved_code.get(r["code"], [])):
            errors.append("duplicate_or_empty_code")
        if r["route_type"] not in {"street", "alley"}:
            errors.append("invalid_route_type")
        ref = r["parent_code"]
        parent = None
        parent_id = None
        parent_prefix = ""
        parent_type = None
        if ref:
            if ref in by_code:
                parent = by_code[ref]
                resolve(parent)
                if parent["errors"]:
                    errors.append("parent_has_errors")
                parent_id = parent.get("existing_id")
                parent_prefix = parent.get("resolved_prefix") or ""
                parent_type = parent["route_type"]
                r["parent_key"] = parent["key"]
            elif ref in by_id or len(by_saved_code.get(ref, [])) == 1:
                p = by_id[ref] if ref in by_id else by_saved_code[ref][0]
                parent_id = str(p["id"])
                parent_prefix = p["prefix"] or ""
                parent_type = p["route_type"]
                r["parent_key"] = None
            else:
                errors.append("parent_not_found")
        if r["route_type"] == "street":
            if ref or r["prefix"]:
                errors.append("street_cannot_have_parent_or_prefix")
            r["resolved_prefix"] = None
        elif r["route_type"] == "alley":
            if not ref:
                errors.append("parent_required")
            if parent_type == "alley" and not parent_prefix:
                errors.append("parent_prefix_missing")
            try:
                r["resolved_prefix"] = _prefix(parent_prefix, r["prefix"])
                if len(r["resolved_prefix"]) > 100:
                    errors.append("prefix_too_long")
            except ValueError as e:
                errors.append(str(e))
        r["parent_id"] = parent_id
        if len(found) == 1:
            old = found[0]
            if (old["name"] != r["name"] or old["route_type"] != r["route_type"]
                or (old["prefix"] or None) != r.get("resolved_prefix")
                or (str(old["parent_route_id"]) if old["parent_route_id"] else None) != parent_id
                or old["direction_state"] != r["direction_state"]):
                errors.append("existing_route_conflict")
            r["existing_revision"] = old["revision"]
        stack.pop()
        states[key] = 2
        result.append(r)

    for row in rows:
        try:
            resolve(row)
        except RecursionError as exc:
            raise PlatformValidationError("Cây tuyến quá sâu", code="ROUTE_DEPTH_LIMIT") from exc

    occupied: dict[tuple[str, str], str] = {}
    for old in existing:
        if old["prefix"] and old["parent_route_id"]:
            occupied[(str(old["parent_route_id"]), old["prefix"])] = str(old["id"])
    for r in result:
        if r["errors"] or r.get("existing_id") or not r.get("resolved_prefix"):
            continue
        parent_ref = r.get("parent_id") or r.get("parent_key")
        key = (parent_ref, r["resolved_prefix"])
        if key in occupied:
            r["errors"].append("duplicate_sibling_prefix")
        else:
            occupied[key] = r["key"]
    by_key = {r["key"]: r for r in result}
    for r in result:
        parent_key = r.get("parent_key")
        if parent_key:
            parent = by_key.get(parent_key)
            if parent and parent["errors"] and "parent_has_errors" not in r["errors"]:
                r["errors"].append("parent_has_errors")
        r["state"] = "error" if r["errors"] else "existing" if r.get("existing_id") else "ready"
    return result


class RouteTreeImporter:
    def __init__(self, repo: Any) -> None:
        self.repo = repo
        self.session = repo.session

    def preview(self, layers: list[dict[str, Any]], overrides: dict[str, dict[str, Any]]) -> dict[str, Any]:
        self.repo.prepare("edit")
        params = {"org": self.repo.org_id, "project": self.repo.project_id}
        rows: list[dict[str, Any]] = []
        seen_sources: set[str] = set()
        for layer in layers:
            source = str(layer["source_id"])
            if source in seen_sources:
                raise PlatformValidationError("Một lớp chỉ được chọn một lần", code="DUPLICATE_SOURCE")
            seen_sources.add(source)
            entries = self.session.execute(text("""
                SELECT f.feature_id, f.attributes, f.content_revision, f.geometry_state,
                       ST_GeometryType(f.geometry) AS geometry_type, ST_SRID(f.geometry) AS srid
                FROM spatial.data_sources s JOIN spatial.reference_features f
                  ON f.organization_id=s.organization_id AND f.project_id=s.project_id AND f.source_id=s.id
                WHERE s.organization_id=:org AND s.project_id=:project AND s.id=:source
                  AND s.lifecycle='active' AND s.validation_state='ready'
                ORDER BY f.feature_id LIMIT :limit
            """), {**params, "source": source, "limit": _LIMIT + 1}).mappings().all()
            if not entries:
                raise PlatformValidationError("Lớp không có đối tượng hoặc chưa sẵn sàng", code="SOURCE_NOT_READY")
            if len(rows) + len(entries) > _LIMIT:
                raise PlatformValidationError(f"Tối đa {_LIMIT} tuyến mỗi đợt", code="ROUTE_IMPORT_LIMIT")
            mapping = layer["mapping"]
            for f in entries:
                attrs = f["attributes"]
                feature = str(f["feature_id"])
                key = f"{source}:{feature}"
                def read(field: str, default: str = "") -> str:
                    name = mapping.get(field)
                    return _value(attrs.get(name)) if name else default
                code = read("code", feature)
                parent = read("parent_code")
                prefix = read("prefix")
                kind = read("route_type", layer["default_type"]).lower()
                aliases = {"đường": "street", "duong": "street", "hẻm": "alley", "hem": "alley", "ngách": "alley", "ngach": "alley", "nhánh": "alley", "nhanh": "alley"}
                kind = aliases.get(kind, kind)
                override = overrides.get(key, {})
                parent = override.get("parent_code", parent)
                prefix = override.get("prefix", prefix)
                errors = []
                if f["geometry_state"] != "present" or f["geometry_type"] != "ST_LineString" or not f["srid"]:
                    errors.append("invalid_line_geometry")
                rows.append({"key": key, "source_id": source, "feature_id": feature,
                    "content_revision": f["content_revision"], "code": code, "name": read("name"),
                    "parent_code": parent, "prefix": prefix, "route_type": kind,
                    "direction_state": layer["direction_state"], "errors": errors})
        existing = [dict(r) for r in self.repo.list_routes()]
        planned = plan_routes(rows, existing)
        # Candidate suggestions only: geometric adjacency is not proof of address parentage.
        unresolved = [r for r in planned if r["route_type"] == "alley" and not r["parent_code"] and not r.get("existing_id") and "invalid_line_geometry" not in r["errors"]]
        if unresolved:
            candidates = {r["key"]: r["code"] for r in planned if r["route_type"] == "street" or r["prefix"]}
            for old in existing:
                if old["linked_source_id"] and old["linked_feature_id"]:
                    candidates.setdefault(f'{old["linked_source_id"]}:{old["linked_feature_id"]}', str(old["id"]))
            selected = list(candidates)
            for r in unresolved[:200]:
                matches = self.session.execute(text("""
                    WITH child AS (
                      SELECT ST_Transform(geometry,4326)::geography AS g,
                             ST_Transform(ST_StartPoint(geometry),4326)::geography AS a,
                             ST_Transform(ST_EndPoint(geometry),4326)::geography AS b
                      FROM spatial.reference_features WHERE organization_id=:org AND project_id=:project
                        AND source_id=:source AND feature_id=:feature AND geometry_state='present'
                    ), candidates AS (
                      SELECT f.source_id::text || ':' || f.feature_id AS key,
                             ST_Transform(f.geometry,4326)::geography AS g
                      FROM spatial.reference_features f
                      WHERE f.organization_id=:org AND f.project_id=:project AND f.geometry_state='present'
                        AND ST_GeometryType(f.geometry)='ST_LineString' AND ST_SRID(f.geometry)>0
                        AND f.source_id::text || ':' || f.feature_id = ANY(:keys)
                    )
                    SELECT key, LEAST(ST_Distance(child.a,c.g),ST_Distance(child.b,c.g)) AS distance
                    FROM child CROSS JOIN candidates c
                    WHERE key<>:childkey AND (ST_DWithin(child.a,c.g,8) OR ST_DWithin(child.b,c.g,8))
                    ORDER BY distance,key LIMIT 5
                """), {**params, "source": r["source_id"], "feature": r["feature_id"], "keys": selected, "childkey": r["key"]}).mappings().all()
                r["parent_suggestions"] = [{"code": candidates[m["key"]], "distance_m": round(float(m["distance"]), 2)} for m in matches]
        digest = hashlib.sha256(json.dumps(planned, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        return {"preview_token": digest, "items": planned, "ready": sum(r["state"] == "ready" for r in planned),
                "existing": sum(r["state"] == "existing" for r in planned), "errors": sum(r["state"] == "error" for r in planned)}

    def apply(self, layers: list[dict[str, Any]], overrides: dict[str, dict[str, Any]], token: str) -> dict[str, Any]:
        self.repo.prepare("edit")
        self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                             {"key": f"house-numbering-route-import:{self.repo.project_id}"})
        plan = self.preview(layers, overrides)
        if plan["preview_token"] != token:
            raise PlatformConflictError("Dữ liệu đã thay đổi, hãy xem trước lại", code="STALE_ROUTE_IMPORT")
        if plan["errors"]:
            raise PlatformValidationError("Cần xử lý toàn bộ lỗi trước khi áp dụng", code="ROUTE_IMPORT_ERRORS")
        ids: dict[str, UUID] = {}
        for r in plan["items"]:
            if r.get("existing_id"):
                ids[r["key"]] = UUID(r["existing_id"])
                continue
            parent = ids.get(r.get("parent_key")) if r.get("parent_key") else UUID(r["parent_id"]) if r.get("parent_id") else None
            created = self.repo.create_route(name=r["name"], route_type=r["route_type"], parent_route_id=parent,
                prefix=r["resolved_prefix"], source_id=UUID(r["source_id"]), feature_id=r["feature_id"],
                direction_state=r["direction_state"], source_label=f'route-tree-import:{r["code"]}', status="draft")
            ids[r["key"]] = created["id"]
        self.session.commit()
        return {"created": plan["ready"], "existing": plan["existing"]}
