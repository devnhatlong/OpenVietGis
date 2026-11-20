"""R013 RLS-enforced repository for offline GeoPackage bundles & idempotent outbox sync."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.formats.geopackage import write_geopackage
from openvietgis_api.adapters.persistence.editing_repository import SqlEditingRepository
from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.adapters.storage.local_object_store import LocalObjectStore
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.editing.domain import (
    EditOperationInput,
    EditOpType,
    validate_operation_id,
)
from openvietgis_api.domains.field.domain import (
    MAX_OFFLINE_PACKAGE_FEATURES,
    MAX_OFFLINE_TTL_HOURS,
    OfflinePackageRecord,
    SyncBatchRecord,
)
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformForbiddenError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.domains.spatial.domain import FieldType, NativeGeometry
from openvietgis_api.domains.transfers.domain import ExportFieldMapping


def _pkg_from_row(row: RowMapping) -> OfflinePackageRecord:
    return OfflinePackageRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        name=str(row["name"]),
        profile=str(row["profile"]),
        aoi_bbox={k: float(v) for k, v in dict(row["aoi_bbox"]).items()},
        crs_code=int(row["crs_code"]),
        layer_pins=list(row["layer_pins"]),
        feature_count=int(row["feature_count"]),
        storage_key=str(row["storage_key"]),
        sha256=str(row["sha256"]),
        byte_size=int(row["byte_size"]),
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        created_by_actor_id=row["created_by_actor_id"],
        created_at=row["created_at"],
    )


def _sync_from_row(row: RowMapping) -> SyncBatchRecord:
    return SyncBatchRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        package_id=row["package_id"],
        operation_id=str(row["operation_id"]),
        status=str(row["status"]),
        submitted_ops_count=int(row["submitted_ops_count"]),
        applied_changeset_ids=[str(x) for x in row["applied_changeset_ids"]],
        conflicts=list(row["conflicts"]),
        actor_id=row["actor_id"],
        created_at=row["created_at"],
    )


class SqlFieldRepository:
    def __init__(self, session: Session, storage_root: Path) -> None:
        self._session = session
        self._store = LocalObjectStore(storage_root)

    def create_package(
        self,
        *,
        context: AuthorizationContext,
        name: str,
        layer_id: UUID,
        aoi_bbox: dict[str, float],
        ttl_hours: int = 72,
    ) -> OfflinePackageRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        org_id, project_id = context.organization_id, context.project_id

        if not (1 <= ttl_hours <= MAX_OFFLINE_TTL_HOURS):
            raise PlatformValidationError(
                f"ttl_hours must be between 1 and {MAX_OFFLINE_TTL_HOURS}"
            )
        for key in ("min_x", "min_y", "max_x", "max_y"):
            if key not in aoi_bbox:
                raise PlatformValidationError(f"aoi_bbox missing {key!r}")

        meta = self._session.execute(
            text("""
                SELECT l.id AS layer_id, l.name AS layer_name, l.layer_revision,
                       s.id AS source_id, s.stored_crs, s.geometry_family,
                       s.content_revision, s.schema_revision
                FROM spatial.layers l
                JOIN spatial.data_sources s
                  ON s.organization_id = l.organization_id
                 AND s.project_id = l.project_id
                 AND s.id = l.source_id
                WHERE l.organization_id = :org AND l.project_id = :proj AND l.id = :lid
                  AND l.lifecycle = 'active' AND s.validation_state = 'ready'
            """),
            {"org": org_id, "proj": project_id, "lid": layer_id},
        ).mappings().first()
        if meta is None:
            raise PlatformNotFoundError("layer not found or not ready for offline packaging")

        srid = int(meta["stored_crs"])
        fdefs = self._session.execute(
            text("""
                SELECT field_id, name, type FROM spatial.source_fields
                WHERE organization_id = :org AND project_id = :proj AND source_id = :src
                ORDER BY ordinal ASC
            """),
            {"org": org_id, "proj": project_id, "src": meta["source_id"]},
        ).mappings().all()
        mappings = [
            ExportFieldMapping(
                str(fd["field_id"]),
                str(fd["name"]),
                str(fd["field_id"]),
                FieldType(str(fd["type"])),
            )
            for fd in fdefs
        ]

        frows = self._session.execute(
            text("""
                SELECT feature_id, attributes, ST_AsGeoJSON(geometry)::jsonb AS geom
                FROM spatial.reference_features
                WHERE organization_id = :org AND project_id = :proj AND source_id = :src
                  AND ST_Intersects(
                      geometry,
                      ST_MakeEnvelope(:min_x, :min_y, :max_x, :max_y, :srid)
                  )
                ORDER BY feature_id ASC
                LIMIT :lim
            """),
            {
                "org": org_id,
                "proj": project_id,
                "src": meta["source_id"],
                "min_x": float(aoi_bbox["min_x"]),
                "min_y": float(aoi_bbox["min_y"]),
                "max_x": float(aoi_bbox["max_x"]),
                "max_y": float(aoi_bbox["max_y"]),
                "srid": srid,
                "lim": MAX_OFFLINE_PACKAGE_FEATURES,
            },
        ).mappings().all()

        gpkg_rows: list[tuple[str, dict[str, Any], NativeGeometry]] = []
        for fr in frows:
            g = fr["geom"]
            if g is None:
                continue
            gpkg_rows.append((
                str(fr["feature_id"]),
                dict(fr["attributes"]),
                NativeGeometry(type=str(g["type"]), coordinates=g["coordinates"], srid=srid),
            ))

        gpkg_bytes, _, _ = write_geopackage(
            layer_name="field_layer",
            crs_code=srid,
            geometry_family=str(meta["geometry_family"]),
            field_mappings=mappings,
            features=gpkg_rows,
        )

        pkg_id = uuid4()
        skey = f"field/{org_id}/{project_id}/{pkg_id}.gpkg"
        sha256_hex, byte_size = self._store.put_bytes(skey, gpkg_bytes)
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=ttl_hours)
        pins = [
            {
                "layer_id": str(meta["layer_id"]),
                "layer_revision": int(meta["layer_revision"]),
                "source_id": str(meta["source_id"]),
                "content_revision": str(meta["content_revision"]),
                "schema_revision": str(meta["schema_revision"]),
            }
        ]

        row = self._session.execute(
            text("""
                INSERT INTO field.offline_packages (
                    id, organization_id, project_id, name, profile, aoi_bbox, crs_code,
                    layer_pins, feature_count, storage_key, sha256, byte_size,
                    expires_at, created_by_actor_id, created_at
                ) VALUES (
                    :id, :org, :proj, :name, 'standard_pwa', CAST(:bbox AS jsonb), :crs,
                    CAST(:pins AS jsonb), :fcnt, :skey, :sha, :sz,
                    :exp, :actor, :now
                )
                RETURNING *
            """),
            {
                "id": pkg_id,
                "org": org_id,
                "proj": project_id,
                "name": name.strip()[:200] or "Offline Field Package",
                "bbox": json.dumps(aoi_bbox),
                "crs": srid,
                "pins": json.dumps(pins),
                "fcnt": len(gpkg_rows),
                "skey": skey,
                "sha": sha256_hex,
                "sz": byte_size,
                "exp": expires_at,
                "actor": context.actor.actor_id,
                "now": now,
            },
        ).mappings().one()
        self._session.commit()
        return _pkg_from_row(row)

    def download_package(
        self, *, context: AuthorizationContext, package_id: UUID
    ) -> tuple[OfflinePackageRecord, bytes]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        row = self._session.execute(
            text("""
                SELECT * FROM field.offline_packages
                WHERE organization_id = :org AND project_id = :proj AND id = :pid
            """),
            {"org": context.organization_id, "proj": context.project_id, "pid": package_id},
        ).mappings().first()
        if row is None:
            raise PlatformNotFoundError("offline package not found")
        pkg = _pkg_from_row(row)
        if pkg.revoked_at is not None:
            raise PlatformForbiddenError("offline package has been revoked", code="PACKAGE_REVOKED")
        if pkg.expires_at <= datetime.now(UTC):
            raise PlatformForbiddenError("offline package has expired", code="PACKAGE_EXPIRED")
        data = self._store.get_bytes(pkg.storage_key, expected_sha256=pkg.sha256)
        return pkg, data

    def revoke_package(
        self, *, context: AuthorizationContext, package_id: UUID
    ) -> OfflinePackageRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        now = datetime.now(UTC)
        row = self._session.execute(
            text("""
                UPDATE field.offline_packages
                SET revoked_at = COALESCE(revoked_at, :now)
                WHERE organization_id = :org AND project_id = :proj AND id = :pid
                RETURNING *
            """),
            {
                "org": context.organization_id,
                "proj": context.project_id,
                "pid": package_id,
                "now": now,
            },
        ).mappings().first()
        if row is None:
            raise PlatformNotFoundError("offline package not found")
        self._session.commit()
        return _pkg_from_row(row)

    def list_packages(self, *, context: AuthorizationContext) -> list[OfflinePackageRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = self._session.execute(
            text("""
                SELECT * FROM field.offline_packages
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY created_at DESC LIMIT 50
            """),
            {"org": context.organization_id, "proj": context.project_id},
        ).mappings().all()
        return [_pkg_from_row(r) for r in rows]

    def sync_outbox(
        self,
        *,
        context: AuthorizationContext,
        package_id: UUID,
        operation_id: str,
        operations: list[dict[str, Any]],
    ) -> SyncBatchRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        org_id, project_id = context.organization_id, context.project_id
        clean_op = validate_operation_id(operation_id)

        # Idempotent replay
        existing = self._session.execute(
            text("""
                SELECT * FROM field.sync_batches
                WHERE organization_id = :org AND project_id = :proj AND operation_id = :op
            """),
            {"org": org_id, "proj": project_id, "op": clean_op},
        ).mappings().first()
        if existing is not None:
            return _sync_from_row(existing)

        prow = self._session.execute(
            text("""
                SELECT * FROM field.offline_packages
                WHERE organization_id = :org AND project_id = :proj AND id = :pid
            """),
            {"org": org_id, "proj": project_id, "pid": package_id},
        ).mappings().first()
        if prow is None:
            raise PlatformNotFoundError("offline package not found")
        pkg = _pkg_from_row(prow)
        if pkg.revoked_at is not None or pkg.expires_at <= datetime.now(UTC):
            raise PlatformForbiddenError(
                "cannot sync from revoked or expired offline package",
                code="PACKAGE_INVALID",
            )

        pin = pkg.layer_pins[0]
        source_id = UUID(str(pin["source_id"]))
        base_rev = str(pin["content_revision"])
        edit_ops = [
            EditOperationInput(
                op_type=EditOpType(str(o["op_type"])),
                feature_id=str(o["feature_id"]),
                geometry=o.get("geometry"),
                properties=o.get("properties"),
            )
            for o in operations
        ]

        applied_ids: list[str] = []
        conflicts: list[dict[str, object]] = []
        status = "applied"
        try:
            cs = SqlEditingRepository(self._session).commit_changeset(
                context=context,
                source_id=source_id,
                base_content_revision=base_rev,
                operation_id=f"field-sync-{clean_op}",
                summary=f"Offline field sync from package {pkg.name}",
                operations=edit_ops,
            )
            applied_ids.append(str(cs.id))
        except PlatformConflictError as exc:
            self._session.rollback()
            status = "conflict"
            conflicts.append({
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "resolution": "explicit_conflict_review_required",
            })

        # Re-prepare scope in fresh tx after commit or rollback
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        now = datetime.now(UTC)
        row = self._session.execute(
            text("""
                INSERT INTO field.sync_batches (
                    id, organization_id, project_id, package_id, operation_id,
                    status, submitted_ops_count, applied_changeset_ids, conflicts,
                    actor_id, created_at
                ) VALUES (
                    :id, :org, :proj, :pid, :op,
                    :st, :cnt, CAST(:aids AS jsonb), CAST(:confs AS jsonb),
                    :actor, :now
                )
                RETURNING *
            """),
            {
                "id": uuid4(),
                "org": org_id,
                "proj": project_id,
                "pid": package_id,
                "op": clean_op,
                "st": status,
                "cnt": len(operations),
                "aids": json.dumps(applied_ids),
                "confs": json.dumps(conflicts),
                "actor": context.actor.actor_id,
                "now": now,
            },
        ).mappings().one()
        self._session.commit()
        return _sync_from_row(row)
