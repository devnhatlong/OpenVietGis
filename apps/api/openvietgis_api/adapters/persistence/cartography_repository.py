"""R009 RLS-enforced repository for layer styles, print layouts, and immutable print exports."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.adapters.rendering.map_renderer import render_print_map
from openvietgis_api.adapters.storage.local_object_store import LocalObjectStore
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.cartography.domain import (
    LayerStyleRecord,
    Orientation,
    PaperSize,
    PrintExportRecord,
    PrintFormat,
    PrintLayoutRecord,
    StyleMode,
    validate_and_build_legend,
)
from openvietgis_api.domains.platform_errors import PlatformNotFoundError, PlatformValidationError


def _validate_print_extent(extent: dict[str, float], crs_code: int) -> None:
    if (
        set(extent) != {"min_x", "min_y", "max_x", "max_y"}
        or not all(math.isfinite(value) and abs(value) <= 1e9 for value in extent.values())
        or extent["min_x"] >= extent["max_x"]
        or extent["min_y"] >= extent["max_y"]
        or (
            crs_code in (4326, 4756)
            and not (
                -180 <= extent["min_x"] < extent["max_x"] <= 180
                and -90 <= extent["min_y"] < extent["max_y"] <= 90
            )
        )
        or (crs_code == 3857 and any(abs(value) > 20_037_509 for value in extent.values()))
    ):
        raise PlatformValidationError("invalid print extent", code="INVALID_PRINT_EXTENT")


def _style_from_row(row: RowMapping) -> LayerStyleRecord:
    return LayerStyleRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        layer_id=row["layer_id"],
        mode=StyleMode(str(row["mode"])),
        style_spec=dict(row["style_spec"]),
        label_field=str(row["label_field"]) if row["label_field"] else None,
        legend_items=list(row["legend_items"]),
        revision=int(row["revision"]),
        updated_by_actor_id=row["updated_by_actor_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _layout_from_row(row: RowMapping) -> PrintLayoutRecord:
    return PrintLayoutRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        name=str(row["name"]),
        title=str(row["title"]),
        paper_size=PaperSize(str(row["paper_size"])),
        orientation=Orientation(str(row["orientation"])),
        crs_code=int(row["crs_code"]),
        attribution=str(row["attribution"]),
        show_north_arrow=bool(row["show_north_arrow"]),
        show_scale_bar=bool(row["show_scale_bar"]),
        show_legend=bool(row["show_legend"]),
        layer_ids=[str(x) for x in row["layer_ids"]],
        extent=dict(row["extent"]) if row["extent"] is not None else None,
        created_by_actor_id=row["created_by_actor_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _export_from_row(row: RowMapping) -> PrintExportRecord:
    return PrintExportRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        layout_id=row["layout_id"],
        output_format=PrintFormat(str(row["output_format"])),
        dpi=int(row["dpi"]),
        scale_denominator=int(row["scale_denominator"]),
        scale_accuracy_note=str(row["scale_accuracy_note"]),
        revision_manifest=dict(row["revision_manifest"]),
        storage_key=str(row["storage_key"]),
        sha256=str(row["sha256"]),
        byte_size=int(row["byte_size"]),
        created_by_actor_id=row["created_by_actor_id"],
        created_at=row["created_at"],
    )


class SqlCartographyRepository:
    def __init__(self, session: Session, storage_root: Path) -> None:
        self._session = session
        self._spatial = SqlSpatialRepository(session)
        self._store = LocalObjectStore(storage_root)

    def _prepare(self, context: AuthorizationContext, *, permission: Permission) -> None:
        prepare_project_scope(self._session, context, permission=permission)

    def upsert_layer_style(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        mode: StyleMode,
        style_spec: dict[str, Any],
        label_field: str | None = None,
    ) -> LayerStyleRecord:
        self._prepare(context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        org_id, project_id = context.organization_id, context.project_id

        layer_row = (
            self._session.execute(
                text("""
                SELECT id, name, source_id FROM spatial.layers
                WHERE organization_id = :org AND project_id = :proj AND id = :lid
                  AND lifecycle = 'active'
            """),
                {"org": org_id, "proj": project_id, "lid": layer_id},
            )
            .mappings()
            .first()
        )
        if layer_row is None:
            raise PlatformNotFoundError("layer not found")

        clean_spec, legend_items = validate_and_build_legend(
            mode, style_spec, str(layer_row["name"])
        )
        if label_field:
            exists = self._session.execute(
                text("""
                    SELECT 1 FROM spatial.source_fields
                    WHERE organization_id = :org AND project_id = :proj
                      AND source_id = :src AND field_id = :fid
                """),
                {
                    "org": org_id,
                    "proj": project_id,
                    "src": layer_row["source_id"],
                    "fid": label_field,
                },
            ).first()
            if exists is None:
                raise PlatformValidationError(
                    f"label_field {label_field!r} not in layer schema", code="UNKNOWN_FIELD"
                )

        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO cartography.layer_styles (
                    id, organization_id, project_id, layer_id, mode, style_spec,
                    label_field, legend_items, revision, updated_by_actor_id,
                    created_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :lid, :mode, CAST(:spec AS jsonb),
                    :lfield, CAST(:legend AS jsonb), 1, :actor, :now, :now
                )
                ON CONFLICT (organization_id, project_id, layer_id) DO UPDATE
                SET mode = EXCLUDED.mode,
                    style_spec = EXCLUDED.style_spec,
                    label_field = EXCLUDED.label_field,
                    legend_items = EXCLUDED.legend_items,
                    revision = cartography.layer_styles.revision + 1,
                    updated_by_actor_id = EXCLUDED.updated_by_actor_id,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": org_id,
                    "proj": project_id,
                    "lid": layer_id,
                    "mode": mode.value,
                    "spec": json.dumps(clean_spec),
                    "lfield": label_field,
                    "legend": json.dumps(legend_items),
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._session.commit()
        return _style_from_row(row)

    def get_layer_style(
        self, *, context: AuthorizationContext, layer_id: UUID
    ) -> LayerStyleRecord | None:
        self._prepare(context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        row = (
            self._session.execute(
                text("""
                SELECT * FROM cartography.layer_styles
                WHERE organization_id = :org AND project_id = :proj AND layer_id = :lid
            """),
                {"org": context.organization_id, "proj": context.project_id, "lid": layer_id},
            )
            .mappings()
            .first()
        )
        return _style_from_row(row) if row is not None else None

    def create_layout(
        self,
        *,
        context: AuthorizationContext,
        name: str,
        title: str,
        paper_size: PaperSize,
        orientation: Orientation,
        crs_code: int,
        attribution: str,
        layer_ids: list[UUID],
        show_north_arrow: bool = True,
        show_scale_bar: bool = True,
        show_legend: bool = True,
        extent: dict[str, float] | None = None,
    ) -> PrintLayoutRecord:
        self._prepare(context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        if crs_code not in (4326, 3857, 4756, 5899):
            raise PlatformValidationError(
                f"unsupported layout CRS {crs_code}", code="UNSUPPORTED_CRS"
            )
        if not layer_ids:
            raise PlatformValidationError("layout requires at least one layer", code="EMPTY_LAYOUT")
        if len(layer_ids) != len(set(layer_ids)) or len(layer_ids) > 20:
            raise PlatformValidationError(
                "layout requires 1..20 unique layers", code="LAYOUT_LAYER_LIMIT"
            )
        for layer_id in layer_ids:
            row = self._session.execute(
                text("""
                    SELECT l.id FROM spatial.layers l JOIN spatial.data_sources s
                    ON l.source_id = s.id AND l.project_id = s.project_id
                    AND l.organization_id = s.organization_id
                    WHERE l.organization_id = :org AND l.project_id = :proj AND l.id = :lid
                      AND l.lifecycle = 'active' AND s.lifecycle = 'active'
                      AND s.validation_state = 'ready'
                """),
                {"org": context.organization_id, "proj": context.project_id, "lid": layer_id},
            ).first()
            if row is None:
                raise PlatformNotFoundError("layout layer unavailable")
        if extent is not None:
            _validate_print_extent(extent, crs_code)
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO cartography.print_layouts (
                    id, organization_id, project_id, name, title, paper_size, orientation,
                    crs_code, attribution, show_north_arrow, show_scale_bar, show_legend,
                    layer_ids, extent, created_by_actor_id, created_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :name, :title, :paper, :orient,
                    :crs, :attr, :na, :sb, :lg,
                    CAST(:lids AS jsonb), CAST(:ext AS jsonb), :actor, :now, :now
                )
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "name": name.strip()[:200] or "Print Layout",
                    "title": title.strip()[:200] or "OpenVietGIS Map",
                    "paper": paper_size.value,
                    "orient": orientation.value,
                    "crs": crs_code,
                    "attr": attribution.strip()[:300] or "OpenVietGIS Project Data",
                    "na": show_north_arrow,
                    "sb": show_scale_bar,
                    "lg": show_legend,
                    "lids": json.dumps([str(x) for x in layer_ids]),
                    "ext": json.dumps(extent) if extent is not None else None,
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._session.commit()
        return _layout_from_row(row)

    def list_layouts(self, *, context: AuthorizationContext) -> list[PrintLayoutRecord]:
        self._prepare(context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM cartography.print_layouts
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY created_at DESC
            """),
                {"org": context.organization_id, "proj": context.project_id},
            )
            .mappings()
            .all()
        )
        return [_layout_from_row(r) for r in rows]

    def export_layout(
        self,
        *,
        context: AuthorizationContext,
        layout_id: UUID,
        output_format: PrintFormat,
        dpi: int = 150,
    ) -> PrintExportRecord:
        self._prepare(context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        org_id, project_id = context.organization_id, context.project_id
        if dpi not in (150, 300):
            raise PlatformValidationError("dpi must be 150 or 300", code="INVALID_DPI")

        lrow = (
            self._session.execute(
                text("""
                SELECT * FROM cartography.print_layouts
                WHERE organization_id = :org AND project_id = :proj AND id = :lid
            """),
                {"org": org_id, "proj": project_id, "lid": layout_id},
            )
            .mappings()
            .first()
        )
        if lrow is None:
            raise PlatformNotFoundError("print layout not found")
        layout = _layout_from_row(lrow)

        layers_payload: list[dict[str, Any]] = []
        manifest_layers: list[dict[str, Any]] = []
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for lid_str in layout.layer_ids:
            lid = UUID(lid_str)
            meta = (
                self._session.execute(
                    text("""
                    SELECT l.id AS layer_id, l.name AS layer_name, l.layer_revision,
                           s.id AS source_id, s.stored_crs, s.content_revision, s.schema_revision,
                           s.extent
                    FROM spatial.layers l
                    JOIN spatial.data_sources s
                      ON s.organization_id = l.organization_id
                     AND s.project_id = l.project_id
                     AND s.id = l.source_id
                    WHERE l.organization_id = :org AND l.project_id = :proj AND l.id = :lid
                      AND l.lifecycle = 'active' AND s.lifecycle = 'active'
                      AND s.validation_state = 'ready'
                """),
                    {"org": org_id, "proj": project_id, "lid": lid},
                )
                .mappings()
                .first()
            )
            if meta is None:
                raise PlatformNotFoundError("one or more layout layers are unavailable")

            style_row = (
                self._session.execute(
                    text("""
                    SELECT mode, style_spec, label_field, legend_items, revision
                    FROM cartography.layer_styles
                    WHERE organization_id = :org AND project_id = :proj AND layer_id = :lid
                """),
                    {"org": org_id, "proj": project_id, "lid": lid},
                )
                .mappings()
                .first()
            )
            style_dict = dict(style_row) if style_row is not None else None

            geom_expr = (
                "rf.geometry"
                if int(meta["stored_crs"]) == layout.crs_code
                else f"ST_Transform(rf.geometry, {int(layout.crs_code)})"
            )
            frows = (
                self._session.execute(
                    text(f"""
                    SELECT rf.feature_id, rf.attributes,
                           ST_AsGeoJSON({geom_expr})::jsonb AS geom,
                           ST_XMin({geom_expr}) AS x0, ST_YMin({geom_expr}) AS y0,
                           ST_XMax({geom_expr}) AS x1, ST_YMax({geom_expr}) AS y1
                    FROM spatial.reference_features rf
                    WHERE rf.organization_id = :org AND rf.project_id = :proj
                      AND rf.source_id = :src
                    ORDER BY rf.feature_id
                    LIMIT 2501
                """),
                    {"org": org_id, "proj": project_id, "src": meta["source_id"]},
                )
                .mappings()
                .all()
            )

            if len(frows) > 2500:
                raise PlatformValidationError(
                    "print layer exceeds the supported 2500-feature limit; narrow the source",
                    code="PRINT_FEATURE_LIMIT",
                )
            features = []
            for fr in frows:
                if fr["x0"] is not None:
                    min_x = min(min_x, float(fr["x0"]))
                    min_y = min(min_y, float(fr["y0"]))
                    max_x = max(max_x, float(fr["x1"]))
                    max_y = max(max_y, float(fr["y1"]))
                features.append(
                    {
                        "feature_id": str(fr["feature_id"]),
                        "attributes": dict(fr["attributes"]),
                        "geometry": dict(fr["geom"]) if fr["geom"] is not None else None,
                    }
                )

            layers_payload.append(
                {
                    "id": str(meta["layer_id"]),
                    "name": str(meta["layer_name"]),
                    "style": style_dict,
                    "features": features,
                }
            )
            manifest_layers.append(
                {
                    "layer_id": str(meta["layer_id"]),
                    "layer_revision": int(meta["layer_revision"]),
                    "source_id": str(meta["source_id"]),
                    "content_revision": str(meta["content_revision"]),
                    "schema_revision": str(meta["schema_revision"]),
                    "style_revision": int(style_row["revision"]) if style_row else 0,
                }
            )

        if layout.extent is not None:
            _validate_print_extent(layout.extent, layout.crs_code)
            use_extent = layout.extent
        elif min_x < float("inf"):
            # Point/vertical-line extents need a finite, honest frame.
            minimum_span = 0.00001 if layout.crs_code in (4326, 4756) else 1.0
            if min_x == max_x:
                min_x, max_x = min_x - minimum_span / 2, max_x + minimum_span / 2
            if min_y == max_y:
                min_y, max_y = min_y - minimum_span / 2, max_y + minimum_span / 2
            use_extent = {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y}
        else:
            raise PlatformValidationError(
                "layout has no spatial extent; supply an explicit extent", code="EMPTY_PRINT_EXTENT"
            )

        raw_bytes, scale_denom, scale_note = render_print_map(
            title=layout.title,
            paper_size=layout.paper_size,
            orientation=layout.orientation,
            dpi=dpi,
            output_format=output_format,
            crs_code=layout.crs_code,
            attribution=layout.attribution,
            show_north_arrow=layout.show_north_arrow,
            show_scale_bar=layout.show_scale_bar,
            show_legend=layout.show_legend,
            extent=use_extent,
            layers_payload=layers_payload,
        )

        export_id = uuid4()
        storage_key = f"cartography/{org_id}/{project_id}/{export_id}.{output_format.value}"
        sha256_hex, byte_size = self._store.put_bytes(storage_key, raw_bytes)
        now = datetime.now(UTC)
        manifest = {
            "layout_id": str(layout.id),
            "crs_code": layout.crs_code,
            "paper_size": layout.paper_size.value,
            "orientation": layout.orientation.value,
            "dpi": dpi,
            "extent": use_extent,
            "layers": manifest_layers,
            "exported_at": now.isoformat(),
        }

        erow = (
            self._session.execute(
                text("""
                INSERT INTO cartography.print_exports (
                    id, organization_id, project_id, layout_id, output_format, dpi,
                    scale_denominator, scale_accuracy_note, revision_manifest,
                    storage_key, sha256, byte_size, created_by_actor_id, created_at
                ) VALUES (
                    :id, :org, :proj, :lid, :fmt, :dpi,
                    :scale, :note, CAST(:manifest AS jsonb),
                    :skey, :sha, :sz, :actor, :now
                )
                RETURNING *
            """),
                {
                    "id": export_id,
                    "org": org_id,
                    "proj": project_id,
                    "lid": layout_id,
                    "fmt": output_format.value,
                    "dpi": dpi,
                    "scale": scale_denom,
                    "note": scale_note,
                    "manifest": json.dumps(manifest),
                    "skey": storage_key,
                    "sha": sha256_hex,
                    "sz": byte_size,
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._session.commit()
        return _export_from_row(erow)

    def download_export(
        self, *, context: AuthorizationContext, export_id: UUID
    ) -> tuple[PrintExportRecord, bytes]:
        self._prepare(context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        row = (
            self._session.execute(
                text("""
                SELECT * FROM cartography.print_exports
                WHERE organization_id = :org AND project_id = :proj AND id = :eid
            """),
                {"org": context.organization_id, "proj": context.project_id, "eid": export_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise PlatformNotFoundError("print export not found")
        rec = _export_from_row(row)
        data = self._store.get_bytes(rec.storage_key, expected_sha256=rec.sha256)
        return rec, data

    def list_exports(self, *, context: AuthorizationContext) -> list[PrintExportRecord]:
        self._prepare(context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM cartography.print_exports
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY created_at DESC LIMIT 50
            """),
                {"org": context.organization_id, "proj": context.project_id},
            )
            .mappings()
            .all()
        )
        return [_export_from_row(r) for r in rows]
