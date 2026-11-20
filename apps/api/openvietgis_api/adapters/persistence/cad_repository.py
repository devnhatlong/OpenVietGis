"""R012 RLS-enforced PostGIS repository for 2D DXF import/export & loss-disclosed conversion."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.cad.dxf_codec import parse_dxf_2d, write_dxf_2d
from openvietgis_api.adapters.persistence.scope_helper import (
    append_project_audit,
    prepare_project_scope,
)
from openvietgis_api.adapters.storage.local_object_store import LocalObjectStore
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.cad.domain import CadConversionRecord, CadUnit
from openvietgis_api.domains.editing.domain import geometry_to_wkt
from openvietgis_api.domains.platform_errors import (
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.domains.spatial.domain import (
    FieldType,
    GeometryDimensions,
    GeometryFamily,
    SourceField,
    schema_revision_digest,
)


def _conv_from_row(row: RowMapping) -> CadConversionRecord:
    return CadConversionRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        direction=str(row["direction"]),
        cad_format=str(row["cad_format"]),
        filename=str(row["filename"]),
        units=CadUnit(str(row["units"])),
        crs_code=int(row["crs_code"]),
        status=str(row["status"]),
        entity_summary=dict(row["entity_summary"]),
        loss_report=dict(row["loss_report"]),
        storage_key=str(row["storage_key"]),
        sha256=str(row["sha256"]),
        byte_size=int(row["byte_size"]),
        source_id=row["source_id"],
        layer_id=row["layer_id"],
        content_revision=str(row["content_revision"]) if row["content_revision"] else None,
        actor_id=row["actor_id"],
        created_at=row["created_at"],
    )


class SqlCadRepository:
    def __init__(self, session: Session, storage_root: Path) -> None:
        self._session = session
        self._store = LocalObjectStore(storage_root)

    def import_cad(
        self,
        *,
        context: AuthorizationContext,
        filename: str,
        payload: bytes,
        layer_name: str,
        units: CadUnit,
        crs_code: int,
    ) -> CadConversionRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        org_id, project_id = context.organization_id, context.project_id

        if crs_code not in (4326, 3857, 4756, 5899):
            raise PlatformValidationError(
                "explicit georeferenced CRS (4326, 3857, 4756, 5899) required; "
                "ungeoreferenced CAD publication is rejected",
                code="UNGEOREFERENCED_CAD_REJECTED",
            )

        conv_id = uuid4()
        lower = filename.lower()
        fmt = "dwg" if lower.endswith(".dwg") else "dxf"
        skey = f"cad/{org_id}/{project_id}/{conv_id}.{fmt}"
        sha256_hex, byte_size = self._store.put_bytes(skey, payload)
        now = datetime.now(UTC)

        if fmt == "dwg":
            # Preserve original evidence and reject DWG without licensed adapter
            row = self._session.execute(
                text("""
                    INSERT INTO cad.conversions (
                        id, organization_id, project_id, direction, cad_format, filename,
                        units, crs_code, status, entity_summary, loss_report, storage_key,
                        sha256, byte_size, actor_id, created_at
                    ) VALUES (
                        :id, :org, :proj, 'import', 'dwg', :fname,
                        :units, :crs, 'rejected', CAST(:esum AS jsonb), CAST(:loss AS jsonb),
                        :skey, :sha, :sz, :actor, :now
                    )
                    RETURNING *
                """),
                {
                    "id": conv_id,
                    "org": org_id,
                    "proj": project_id,
                    "fname": filename[:255],
                    "units": units.value,
                    "crs": crs_code,
                    "esum": json.dumps({"detected_format": "dwg"}),
                    "loss": json.dumps({
                        "reason": "DWG_ADAPTER_REQUIRED",
                        "message": "Native DWG requires a separately licensed adapter; "
                        "convert to 2D DXF R2010+ for direct import.",
                    }),
                    "skey": skey,
                    "sha": sha256_hex,
                    "sz": byte_size,
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            ).mappings().one()
            self._session.commit()
            raise PlatformValidationError(
                "DWG requires a separately licensed adapter; original evidence preserved.",
                code="DWG_ADAPTER_REQUIRED",
                details={"conversion_id": str(row["id"]), "sha256": sha256_hex},
            )

        family, features, entity_summary, loss_report = parse_dxf_2d(payload, units=units)

        # Publish as a new project-owned spatial source & layer (kind='derived_processing')
        out_source_id = uuid4()
        out_layer_id = uuid4()
        clean_name = layer_name.strip()[:200] or "CAD DXF Layer"
        cad_fields = [
            SourceField(
                organization_id=org_id,
                project_id=project_id,
                source_id=out_source_id,
                field_id=fid,
                name=fname,
                ordinal=ordinal,
                type=FieldType.TEXT,
                nullable=False,
                schema_revision="0" * 64,
            )
            for ordinal, (fid, fname) in enumerate(
                [("cad_layer", "CAD Layer"), ("cad_entity", "CAD Entity")]
            )
        ]
        schema_rev = schema_revision_digest(
            cad_fields, GeometryFamily(family), GeometryDimensions.XY
        )
        content_rev = hashlib.sha256(f"{out_source_id}:{sha256_hex}".encode()).hexdigest()
        ref_key = f"cad_dxf_{str(out_source_id).replace('-', '')[:12]}"

        self._session.execute(
            text("""
                INSERT INTO spatial.data_sources (
                    id, organization_id, project_id, name, kind, reference_key,
                    fixture_version, manifest_digest, source_asset_id, lifecycle,
                    validation_state, validation_reason, source_crs, stored_crs,
                    schema_state, geometry_family, dimensions, feature_count_state,
                    feature_count, extent_state, extent, catalog_revision,
                    content_revision, schema_revision, created_at, updated_at, retired_at
                ) VALUES (
                    :id, :org, :proj, :name, 'derived_processing', :rkey,
                    'cad_dxf_2d', :mdig, NULL, 'active',
                    'ready', NULL, :crs, :crs,
                    'known', :gfam, 'XY', 'known',
                    0, 'empty', NULL, 1,
                    :crev, :srev, :now, :now, NULL
                )
            """),
            {
                "id": out_source_id,
                "org": org_id,
                "proj": project_id,
                "name": clean_name,
                "rkey": ref_key,
                "mdig": sha256_hex,
                "crs": crs_code,
                "gfam": family,
                "crev": content_rev,
                "srev": schema_rev,
                "now": now,
            },
        )

        for ordinal, (fid, fname) in enumerate(
            [("cad_layer", "CAD Layer"), ("cad_entity", "CAD Entity")]
        ):
            self._session.execute(
                text("""
                    INSERT INTO spatial.source_fields (
                        organization_id, project_id, source_id, field_id,
                        name, ordinal, type, nullable, schema_revision
                    ) VALUES (:org, :proj, :src, :fid, :fname, :ord, 'text', false, :srev)
                """),
                {
                    "org": org_id,
                    "proj": project_id,
                    "src": out_source_id,
                    "fid": fid,
                    "fname": fname,
                    "ord": ordinal,
                    "srev": schema_rev,
                },
            )

        for feat in features:
            wkt = geometry_to_wkt(feat["geometry"])
            self._session.execute(
                text("""
                    INSERT INTO spatial.reference_features (
                        organization_id, project_id, source_id, feature_id,
                        attributes, geometry, geometry_state, content_revision, schema_revision
                    ) VALUES (
                        :org, :proj, :src, :fid,
                        CAST(:attrs AS jsonb),
                        ST_SetSRID(ST_GeomFromText(:wkt), :srid),
                        'present', :crev, :srev
                    )
                """),
                {
                    "org": org_id,
                    "proj": project_id,
                    "src": out_source_id,
                    "fid": feat["feature_id"],
                    "attrs": json.dumps(feat["attributes"]),
                    "wkt": wkt,
                    "srid": crs_code,
                    "crev": content_rev,
                    "srev": schema_rev,
                },
            )

        stats = self._session.execute(
            text("""
                SELECT COUNT(*)::int AS cnt,
                       ST_XMin(ST_Extent(geometry)) AS min_x,
                       ST_YMin(ST_Extent(geometry)) AS min_y,
                       ST_XMax(ST_Extent(geometry)) AS max_x,
                       ST_YMax(ST_Extent(geometry)) AS max_y
                FROM spatial.reference_features
                WHERE organization_id = :org AND project_id = :proj AND source_id = :src
            """),
            {"org": org_id, "proj": project_id, "src": out_source_id},
        ).mappings().one()
        self._session.execute(
            text("""
                UPDATE spatial.data_sources
                SET feature_count = :cnt,
                    extent_state = 'available',
                    extent = CAST(:ext AS jsonb)
                WHERE organization_id = :org AND project_id = :proj AND id = :src
            """),
            {
                "org": org_id,
                "proj": project_id,
                "src": out_source_id,
                "cnt": int(stats["cnt"]),
                "ext": json.dumps({
                    "min_x": float(stats["min_x"]),
                    "min_y": float(stats["min_y"]),
                    "max_x": float(stats["max_x"]),
                    "max_y": float(stats["max_y"]),
                    "crs_code": int(crs_code),
                }),
            },
        )
        self._session.execute(
            text("""
                INSERT INTO spatial.layers (
                    id, organization_id, project_id, source_id, name,
                    lifecycle, layer_revision, created_at, updated_at, retired_at
                ) VALUES (:lid, :org, :proj, :src, :name, 'active', 1, :now, :now, NULL)
            """),
            {
                "lid": out_layer_id,
                "org": org_id,
                "proj": project_id,
                "src": out_source_id,
                "name": clean_name,
                "now": now,
            },
        )

        audit_id = uuid4()
        append_project_audit(
            self._session,
            context,
            audit_id=audit_id,
            action="cad.dxf.import",
            resource_type="data_source",
            resource_id=out_source_id,
            metadata={"filename": filename[:255], "crs_code": crs_code, "units": units.value},
            created_at=now,
        )

        row = self._session.execute(
            text("""
                INSERT INTO cad.conversions (
                    id, organization_id, project_id, direction, cad_format, filename,
                    units, crs_code, status, entity_summary, loss_report, storage_key,
                    sha256, byte_size, source_id, layer_id, content_revision,
                    actor_id, created_at
                ) VALUES (
                    :id, :org, :proj, 'import', 'dxf', :fname,
                    :units, :crs, 'succeeded', CAST(:esum AS jsonb), CAST(:loss AS jsonb),
                    :skey, :sha, :sz, :src, :lid, :crev, :actor, :now
                )
                RETURNING *
            """),
            {
                "id": conv_id,
                "org": org_id,
                "proj": project_id,
                "fname": filename[:255],
                "units": units.value,
                "crs": crs_code,
                "esum": json.dumps(entity_summary),
                "loss": json.dumps(loss_report),
                "skey": skey,
                "sha": sha256_hex,
                "sz": byte_size,
                "src": out_source_id,
                "lid": out_layer_id,
                "crev": content_rev,
                "actor": context.actor.actor_id,
                "now": now,
            },
        ).mappings().one()
        self._session.commit()
        return _conv_from_row(row)

    def export_dxf(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        units: CadUnit = CadUnit.METER,
    ) -> tuple[CadConversionRecord, bytes]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        org_id, project_id = context.organization_id, context.project_id

        meta = self._session.execute(
            text("""
                SELECT l.id AS layer_id, l.name AS layer_name,
                       s.id AS source_id, s.stored_crs, s.content_revision
                FROM spatial.layers l
                JOIN spatial.data_sources s
                  ON s.organization_id = l.organization_id
                 AND s.project_id = l.project_id
                 AND s.id = l.source_id
                WHERE l.organization_id = :org AND l.project_id = :proj AND l.id = :lid
            """),
            {"org": org_id, "proj": project_id, "lid": layer_id},
        ).mappings().first()
        if meta is None:
            raise PlatformNotFoundError("layer not found")

        frows = self._session.execute(
            text("""
                SELECT feature_id, ST_AsGeoJSON(geometry)::jsonb AS geom
                FROM spatial.reference_features
                WHERE organization_id = :org AND project_id = :proj AND source_id = :src
                ORDER BY feature_id ASC LIMIT 10000
            """),
            {"org": org_id, "proj": project_id, "src": meta["source_id"]},
        ).mappings().all()
        features = [
            {"feature_id": str(r["feature_id"]), "geometry": dict(r["geom"])}
            for r in frows
            if r["geom"] is not None
        ]
        dxf_bytes = write_dxf_2d(features, layer_name=str(meta["layer_name"]), units=units)
        conv_id = uuid4()
        fname = f"export-{conv_id}.dxf"
        skey = f"cad/{org_id}/{project_id}/{fname}"
        sha256_hex, byte_size = self._store.put_bytes(skey, dxf_bytes)
        now = datetime.now(UTC)

        row = self._session.execute(
            text("""
                INSERT INTO cad.conversions (
                    id, organization_id, project_id, direction, cad_format, filename,
                    units, crs_code, status, entity_summary, loss_report, storage_key,
                    sha256, byte_size, source_id, layer_id, content_revision,
                    actor_id, created_at
                ) VALUES (
                    :id, :org, :proj, 'export', 'dxf', :fname,
                    :units, :crs, 'succeeded', CAST(:esum AS jsonb), CAST(:loss AS jsonb),
                    :skey, :sha, :sz, :src, :lid, :crev, :actor, :now
                )
                RETURNING *
            """),
            {
                "id": conv_id,
                "org": org_id,
                "proj": project_id,
                "fname": fname,
                "units": units.value,
                "crs": int(meta["stored_crs"]),
                "esum": json.dumps({"exported_features": len(features), "dxf_version": "R2010"}),
                "loss": json.dumps({
                    "attributes_omitted_in_dxf_geometry": True,
                    "silent_loss": False,
                }),
                "skey": skey,
                "sha": sha256_hex,
                "sz": byte_size,
                "src": meta["source_id"],
                "lid": layer_id,
                "crev": str(meta["content_revision"]),
                "actor": context.actor.actor_id,
                "now": now,
            },
        ).mappings().one()
        self._session.commit()
        return _conv_from_row(row), dxf_bytes

    def list_conversions(self, *, context: AuthorizationContext) -> list[CadConversionRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = self._session.execute(
            text("""
                SELECT * FROM cad.conversions
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY created_at DESC LIMIT 50
            """),
            {"org": context.organization_id, "proj": context.project_id},
        ).mappings().all()
        return [_conv_from_row(r) for r in rows]
