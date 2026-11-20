"""Restricted-runtime RLS-enforced SQL/PostGIS repository for R005 transfers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.rls import (
    bind_authenticated_actor,
    bind_authenticated_service_actor,
)
from openvietgis_api.adapters.persistence.spatial_repository import (
    _FEATURE_COLUMNS,
    SqlSpatialRepository,
    _feature_from_row,
    _read_native_wkb,
    _source_from_row,
)
from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.spatial.crs import (
    TM3_PIPELINE,
    PipelineStep,
    get_transformation_profile,
)
from openvietgis_api.domains.spatial.domain import (
    CatalogChange,
    CatalogOperation,
    ChangedValue,
    DataSource,
    FieldType,
    GeometryFamily,
    Layer,
    LayerRevision,
    Lifecycle,
    NativeGeometry,
    ReferenceFeature,
    ResourceType,
    SourceField,
    SourceRevision,
    SpatialValidationError,
    ValidationState,
    validate_ready_geometry,
)
from openvietgis_api.domains.tenancy.domain import ActorType
from openvietgis_api.domains.transfers.domain import (
    ArtifactState,
    DerivedArtifact,
    JobAttempt,
    JobKind,
    JobStatus,
    SourceAsset,
    TransferFormat,
    TransferJob,
)
from openvietgis_api.domains.transfers.ports import (
    TransferConflictError,
    TransferNotFoundError,
    TransferValidationError,
)


def _req_actor_id(context: AuthorizationContext) -> UUID:
    assert context.actor.actor_id is not None
    return context.actor.actor_id


def _wkt(geom: NativeGeometry) -> str:
    coords: Any = geom.coordinates
    if geom.type == "Point":
        return f"POINT({float(coords[0])!r} {float(coords[1])!r})"
    if geom.type == "LineString":
        pts = ", ".join(f"{float(p[0])!r} {float(p[1])!r}" for p in coords)
        return f"LINESTRING({pts})"
    rings = []
    for ring in coords:
        pts = ", ".join(f"{float(p[0])!r} {float(p[1])!r}" for p in ring)
        rings.append(f"({pts})")
    return f"POLYGON({', '.join(rings)})"


def _asset_from_row(row: RowMapping) -> SourceAsset:
    return SourceAsset(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        filename=row["filename"],
        detected_format=TransferFormat(row["detected_format"]),
        byte_size=int(row["byte_size"]),
        sha256=row["sha256"],
        storage_key=row["storage_key"],
        uploaded_by_type=ActorType(row["uploaded_by_type"]),
        uploaded_by_id=row["uploaded_by_id"],
        uploaded_by_display=row["uploaded_by_display"],
        created_at=row["created_at"],
    )


def _attempt_from_row(row: RowMapping) -> JobAttempt:
    return JobAttempt(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        job_id=row["job_id"],
        attempt_number=int(row["attempt_number"]),
        status=row["status"],
        actor_type=ActorType(row["actor_type"]),
        actor_id=row["actor_id"],
        credential_id=row["credential_id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error_code=row["error_code"],
        error_message=row["error_message"],
    )


def _artifact_from_row(row: RowMapping) -> DerivedArtifact:
    return DerivedArtifact(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        job_id=row["job_id"],
        source_id=row["source_id"],
        layer_id=row["layer_id"],
        source_content_revision=row["source_content_revision"],
        source_schema_revision=row["source_schema_revision"],
        output_format=TransferFormat(row["output_format"]),
        output_crs=int(row["output_crs"]),
        filename=row["filename"],
        content_type=row["content_type"],
        byte_size=int(row["byte_size"]),
        sha256=row["sha256"],
        storage_key=row["storage_key"],
        comparison_report=dict(row["comparison_report"]),
        created_by_type=ActorType(row["created_by_type"]),
        created_by_id=row["created_by_id"],
        created_by_display=row["created_by_display"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        state=ArtifactState(row["state"]),
    )


def _job_from_row(
    row: RowMapping,
    *,
    attempts: tuple[JobAttempt, ...] = (),
    artifact: DerivedArtifact | None = None,
) -> TransferJob:
    return TransferJob(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        operation_id=row["operation_id"],
        kind=JobKind(row["kind"]),
        request_fingerprint=row["request_fingerprint"],
        status=JobStatus(row["status"]),
        actor_type=ActorType(row["actor_type"]),
        actor_id=row["actor_id"],
        actor_display_snapshot=row["actor_display_snapshot"],
        credential_id=row["credential_id"],
        source_asset_id=row["source_asset_id"],
        target_source_id=row["target_source_id"],
        target_layer_id=row["target_layer_id"],
        source_content_revision=row["source_content_revision"],
        source_schema_revision=row["source_schema_revision"],
        artifact_id=row["artifact_id"],
        attempt_count=int(row["attempt_count"]),
        options_json=dict(row["options_json"] or {}),
        inspection_report=dict(row["inspection_report"]) if row["inspection_report"] else None,
        result_report=dict(row["result_report"]) if row["result_report"] else None,
        error_code=row["error_code"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        attempts=attempts,
        artifact=artifact,
    )


class SqlTransferRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _ensure_actor_bound(self, context: AuthorizationContext) -> None:
        if context.actor.actor_type == "human":
            bind_authenticated_actor(self._session, context.actor)
        elif context.actor.actor_type == "service_principal" and context.credential_id is not None:
            bind_authenticated_service_actor(
                self._session,
                context.actor,
                organization_id=context.organization_id,
                credential_id=context.credential_id,
            )

    def _scope(self, context: AuthorizationContext, *, write: bool) -> dict[str, UUID]:
        self._ensure_actor_bound(context)
        permission = Permission.PROJECT_EDIT if write else Permission.PROJECT_READ
        SqlSpatialRepository(self._session).prepare_scope(
            context=context,
            permission=permission,
            mutation=write,
        )
        assert context.project_id is not None
        return {"organization": context.organization_id, "project": context.project_id}

    def verify_project_authority(self, *, context: AuthorizationContext, write: bool) -> None:
        self._scope(context, write=write)

    def create_source_asset(
        self, *, context: AuthorizationContext, asset: SourceAsset
    ) -> SourceAsset:
        params = self._scope(context, write=True)
        self._session.execute(
            text("""
                INSERT INTO transfers.source_assets (
                    id, organization_id, project_id, filename, detected_format,
                    byte_size, sha256, storage_key, uploaded_by_type,
                    uploaded_by_id, uploaded_by_display, created_at
                ) VALUES (
                    :id, :organization, :project, :filename, :fmt,
                    :byte_size, :sha256, :storage_key, :actor_type,
                    :actor_id, :actor_display, :created_at
                )
            """),
            params
            | {
                "id": asset.id,
                "filename": asset.filename,
                "fmt": asset.detected_format.value,
                "byte_size": asset.byte_size,
                "sha256": asset.sha256,
                "storage_key": asset.storage_key,
                "actor_type": asset.uploaded_by_type.value,
                "actor_id": asset.uploaded_by_id,
                "actor_display": asset.uploaded_by_display,
                "created_at": asset.created_at,
            },
        )
        return asset

    def get_source_asset(
        self, *, context: AuthorizationContext, asset_id: UUID
    ) -> SourceAsset | None:
        params = self._scope(context, write=False)
        row = (
            self._session.execute(
                text("""
                SELECT * FROM transfers.source_assets
                WHERE organization_id = :organization AND project_id = :project AND id = :id
            """),
                params | {"id": asset_id},
            )
            .mappings()
            .one_or_none()
        )
        return _asset_from_row(row) if row is not None else None

    def _hydrate_job(self, params: dict[str, UUID], row: RowMapping) -> TransferJob:
        attempt_rows = (
            self._session.execute(
                text("""
                SELECT * FROM transfers.job_attempts
                WHERE organization_id = :organization AND project_id = :project AND job_id = :job
                ORDER BY attempt_number ASC
            """),
                params | {"job": row["id"]},
            )
            .mappings()
            .all()
        )
        artifact: DerivedArtifact | None = None
        if row["artifact_id"] is not None:
            arow = (
                self._session.execute(
                    text("""
                    SELECT * FROM transfers.derived_artifacts
                    WHERE organization_id = :organization AND project_id = :project AND id = :aid
                """),
                    params | {"aid": row["artifact_id"]},
                )
                .mappings()
                .one_or_none()
            )
            if arow is not None:
                artifact = _artifact_from_row(arow)
        return _job_from_row(
            row,
            attempts=tuple(_attempt_from_row(r) for r in attempt_rows),
            artifact=artifact,
        )

    def get_job_by_operation(
        self, *, context: AuthorizationContext, operation_id: UUID, lock: bool = False
    ) -> TransferJob | None:
        params = self._scope(context, write=False)
        suffix = " FOR UPDATE" if lock else ""
        row = (
            self._session.execute(
                text(f"""
                SELECT * FROM transfers.jobs
                WHERE organization_id = :organization AND project_id = :project
                  AND operation_id = :op{suffix}
            """),
                params | {"op": operation_id},
            )
            .mappings()
            .one_or_none()
        )
        return self._hydrate_job(params, row) if row is not None else None

    def get_job(
        self, *, context: AuthorizationContext, job_id: UUID, lock: bool = False
    ) -> TransferJob | None:
        params = self._scope(context, write=False)
        suffix = " FOR UPDATE" if lock else ""
        row = (
            self._session.execute(
                text(f"""
                SELECT * FROM transfers.jobs
                WHERE organization_id = :organization AND project_id = :project
                  AND id = :id{suffix}
            """),
                params | {"id": job_id},
            )
            .mappings()
            .one_or_none()
        )
        return self._hydrate_job(params, row) if row is not None else None

    def list_jobs(
        self, *, context: AuthorizationContext, limit: int = 50
    ) -> tuple[TransferJob, ...]:
        params = self._scope(context, write=False)
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM transfers.jobs
                WHERE organization_id = :organization AND project_id = :project
                ORDER BY created_at DESC
                LIMIT :limit
            """),
                params | {"limit": max(1, min(limit, 100))},
            )
            .mappings()
            .all()
        )
        return tuple(self._hydrate_job(params, row) for row in rows)

    def create_job(self, *, context: AuthorizationContext, job: TransferJob) -> TransferJob:
        params = self._scope(context, write=(job.kind == JobKind.IMPORT))
        self._session.execute(
            text("""
                INSERT INTO transfers.jobs (
                    id, organization_id, project_id, operation_id, kind,
                    request_fingerprint, status, actor_type, actor_id,
                    actor_display_snapshot, credential_id, source_asset_id,
                    target_source_id, target_layer_id, source_content_revision,
                    source_schema_revision, artifact_id, attempt_count,
                    options_json, inspection_report, result_report,
                    error_code, error_message, created_at, updated_at, completed_at
                ) VALUES (
                    :id, :organization, :project, :op, :kind,
                    :fp, :status, :actor_type, :actor_id,
                    :actor_display, :cred_id, :asset_id,
                    :target_source_id, :target_layer_id, :content_rev,
                    :schema_rev, :artifact_id, :attempt_count,
                    CAST(:options AS jsonb), CAST(:inspection AS jsonb), CAST(:result AS jsonb),
                    :err_code, :err_msg, :created_at, :updated_at, :completed_at
                )
            """),
            params
            | {
                "id": job.id,
                "op": job.operation_id,
                "kind": job.kind.value,
                "fp": job.request_fingerprint,
                "status": job.status.value,
                "actor_type": job.actor_type.value,
                "actor_id": job.actor_id,
                "actor_display": job.actor_display_snapshot,
                "cred_id": job.credential_id,
                "asset_id": job.source_asset_id,
                "target_source_id": job.target_source_id,
                "target_layer_id": job.target_layer_id,
                "content_rev": job.source_content_revision,
                "schema_rev": job.source_schema_revision,
                "artifact_id": job.artifact_id,
                "attempt_count": job.attempt_count,
                "options": json.dumps(job.options_json),
                "inspection": json.dumps(job.inspection_report) if job.inspection_report else None,
                "result": json.dumps(job.result_report) if job.result_report else None,
                "err_code": job.error_code,
                "err_msg": job.error_message,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "completed_at": job.completed_at,
            },
        )
        return job

    def record_attempt(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        attempt_number: int,
        status: str,
        started_at: datetime,
        finished_at: datetime | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        params = self._scope(context, write=False)
        self._session.execute(
            text("""
                INSERT INTO transfers.job_attempts (
                    id, organization_id, project_id, job_id, attempt_number,
                    status, actor_type, actor_id, credential_id,
                    started_at, finished_at, error_code, error_message
                ) VALUES (
                    :id, :organization, :project, :job_id, :attempt_number,
                    :status, :actor_type, :actor_id, :cred_id,
                    :started_at, :finished_at, :err_code, :err_msg
                )
            """),
            params
            | {
                "id": uuid4(),
                "job_id": job_id,
                "attempt_number": attempt_number,
                "status": status,
                "actor_type": str(context.actor.actor_type),
                "actor_id": context.actor.actor_id,
                "cred_id": context.credential_id,
                "started_at": started_at,
                "finished_at": finished_at,
                "err_code": error_code,
                "err_msg": error_message,
            },
        )

    def update_job(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        status: JobStatus,
        attempt_count: int | None = None,
        target_source_id: UUID | None = None,
        target_layer_id: UUID | None = None,
        source_content_revision: str | None = None,
        source_schema_revision: str | None = None,
        artifact_id: UUID | None = None,
        inspection_report: dict[str, Any] | None = None,
        result_report: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> TransferJob:
        params = self._scope(context, write=False)
        now = datetime.now(UTC)
        self._session.execute(
            text("""
                UPDATE transfers.jobs
                SET status = :status,
                    attempt_count = COALESCE(:attempt_count, attempt_count),
                    target_source_id = COALESCE(:target_source_id, target_source_id),
                    target_layer_id = COALESCE(:target_layer_id, target_layer_id),
                    source_content_revision = COALESCE(:content_rev, source_content_revision),
                    source_schema_revision = COALESCE(:schema_rev, source_schema_revision),
                    artifact_id = COALESCE(:artifact_id, artifact_id),
                    inspection_report = COALESCE(CAST(:inspection AS jsonb), inspection_report),
                    result_report = COALESCE(CAST(:result AS jsonb), result_report),
                    error_code = :err_code,
                    error_message = :err_msg,
                    updated_at = :updated_at,
                    completed_at = COALESCE(:completed_at, completed_at)
                WHERE organization_id = :organization AND project_id = :project AND id = :id
            """),
            params
            | {
                "id": job_id,
                "status": status.value,
                "attempt_count": attempt_count,
                "target_source_id": target_source_id,
                "target_layer_id": target_layer_id,
                "content_rev": source_content_revision,
                "schema_rev": source_schema_revision,
                "artifact_id": artifact_id,
                "inspection": json.dumps(inspection_report) if inspection_report else None,
                "result": json.dumps(result_report) if result_report else None,
                "err_code": error_code,
                "err_msg": error_message,
                "updated_at": now,
                "completed_at": completed_at,
            },
        )
        updated = self.get_job(context=context, job_id=job_id)
        assert updated is not None
        return updated

    def validate_and_transform_geometries(
        self,
        *,
        context: AuthorizationContext,
        geometries: Sequence[NativeGeometry],
        source_crs: int,
        target_crs: int,
        expected_family: str,
    ) -> tuple[NativeGeometry, ...]:
        self._scope(context, write=False)
        if not geometries:
            return ()
        family = GeometryFamily(expected_family)
        # Validate native domain + PostGIS ST_IsValid in batches
        for idx, geom in enumerate(geometries):
            try:
                validate_ready_geometry(geom, family, source_crs)
            except SpatialValidationError as exc:
                raise TransferValidationError(
                    "INVALID_GEOMETRY",
                    f"Feature at index {idx} failed geometry validation.",
                ) from exc

        batch_size = 2000
        validated: list[NativeGeometry] = []
        for start in range(0, len(geometries), batch_size):
            chunk = geometries[start : start + batch_size]
            records = [{"idx": i, "wkt": _wkt(g)} for i, g in enumerate(chunk)]
            rows = (
                self._session.execute(
                    text("""
                    SELECT r.idx,
                           ST_IsValid(g) AS valid,
                           ST_IsEmpty(g) AS empty
                    FROM jsonb_to_recordset(CAST(:records AS jsonb)) AS r(idx integer, wkt text),
                         LATERAL ST_GeomFromText(r.wkt, :srid) AS g
                """),
                    {"records": json.dumps(records), "srid": source_crs},
                )
                .mappings()
                .all()
            )
            for row in rows:
                if row["empty"] or not row["valid"]:
                    raise TransferValidationError(
                        "INVALID_GEOMETRY",
                        f"Feature at index {start + int(row['idx'])} failed PostGIS ST_IsValid.",
                    )
            validated.extend(chunk)

        if source_crs == target_crs:
            return tuple(validated)

        profile = get_transformation_profile(source_crs, target_crs)
        if profile is None:
            raise TransferValidationError(
                "UNSUPPORTED_TRANSFORMATION",
                f"No approved transformation from EPSG:{source_crs} to EPSG:{target_crs}.",
            )

        def _check_area(items: Sequence[NativeGeometry]) -> None:
            for item in items:
                verts = validate_ready_geometry(item, expected_srid=item.srid)
                if any(not profile.geographic_bounds.contains(x, y) for x, y in verts):
                    raise TransferValidationError(
                        "TRANSFORMATION_OUT_OF_AREA",
                        "Geometry vertex is outside the approved transformation area of use.",
                    )

        def _apply_step(
            items: Sequence[NativeGeometry], step: PipelineStep
        ) -> tuple[NativeGeometry, ...]:
            out: list[NativeGeometry] = []
            fn = "ST_InverseTransformPipeline" if step.inverse else "ST_TransformPipeline"
            for start in range(0, len(items), batch_size):
                chunk = items[start : start + batch_size]
                records = [{"idx": i, "wkt": _wkt(g)} for i, g in enumerate(chunk)]
                try:
                    rows = (
                        self._session.execute(
                            text(
                                f"""
                            SELECT r.idx,
                                   ST_AsBinary(transformed, 'NDR') AS wkb,
                                   ST_SRID(transformed) AS srid,
                                   ST_IsValid(transformed) AS valid
                            FROM jsonb_to_recordset(CAST(:records AS jsonb))
                                AS r(idx integer, wkt text),
                            LATERAL (
                                SELECT {fn}(
                                    ST_GeomFromText(r.wkt, :in_srid),
                                    :pipeline,
                                    :out_srid
                                ) AS transformed
                            ) AS step
                            ORDER BY r.idx ASC
                        """
                            ),
                            {
                                "records": json.dumps(records),
                                "in_srid": step.source_code,
                                "out_srid": step.target_code,
                                "pipeline": step.pipeline,
                            },
                        )
                        .mappings()
                        .all()
                    )
                except SQLAlchemyError as exc:
                    raise TransferValidationError(
                        "TRANSFORMATION_FAILED",
                        "Approved coordinate transformation pipeline failed.",
                    ) from exc
                for row in rows:
                    if not row["valid"] or row["wkb"] is None:
                        raise TransferValidationError(
                            "TRANSFORMATION_INVALID_OUTPUT",
                            "Coordinate transformation produced invalid geometry.",
                        )
                    decoded = _read_native_wkb(bytes(row["wkb"]), step.target_code)
                    validate_ready_geometry(decoded, family, step.target_code, output_roundoff=True)
                    out.append(decoded)
            return tuple(out)

        current: tuple[NativeGeometry, ...] = tuple(validated)
        if source_crs in (4326, 4756):
            _check_area(current)
        for step in profile.steps:
            current = _apply_step(current, step)
            if step.target_code in (4326, 4756):
                _check_area(current)
        if target_crs == 5899:
            checked = _apply_step(current, PipelineStep(5899, 4756, TM3_PIPELINE, True))
            _check_area(checked)
        return current

    def publish_imported_source_and_layer(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        asset: SourceAsset,
        source: DataSource,
        fields: Sequence[SourceField],
        features: Sequence[ReferenceFeature],
        layer_id: UUID,
        layer_name: str,
        result_report: dict[str, Any],
    ) -> TransferJob:
        # FR-032 / FR-030: Re-verify current authority + cancel boundary right inside publication TX
        params = self._scope(context, write=True)
        locked = self._session.execute(
            text("""
                SELECT status FROM transfers.jobs
                WHERE organization_id = :organization AND project_id = :project AND id = :id
                FOR UPDATE
            """),
            params | {"id": job_id},
        ).scalar_one_or_none()
        if locked is None:
            raise TransferNotFoundError("Transfer job not found.")
        if locked in (JobStatus.CANCELLED.value, JobStatus.CANCEL_REQUESTED.value):
            raise TransferConflictError("JOB_CANCELLED", "Import cancelled before publication.")
        if locked == JobStatus.DENIED.value:
            raise TransferConflictError("JOB_DENIED", "Import authority was denied.")

        # 1. Insert spatial.data_sources
        self._session.execute(
            text("""
                INSERT INTO spatial.data_sources (
                    id, organization_id, project_id, name, kind, reference_key,
                    fixture_version, manifest_digest, source_asset_id, lifecycle,
                    validation_state, validation_reason, source_crs, stored_crs, schema_state,
                    geometry_family, dimensions, feature_count_state, feature_count,
                    extent_state, extent, catalog_revision, content_revision, schema_revision,
                    created_at, updated_at, retired_at
                ) VALUES (
                    :id, :organization, :project, :name, :kind, :reference_key, :fixture_version,
                    :manifest_digest, :asset_id, :lifecycle, :validation_state, NULL,
                    :source_crs, :stored_crs, :schema_state, :family, :dimensions, :count_state,
                    :count, :extent_state, CAST(:extent AS jsonb), :revision, :content, :schema,
                    :created_at, :updated_at, NULL
                )
            """),
            params
            | {
                "id": source.id,
                "name": source.name,
                "kind": source.kind.value,
                "reference_key": source.reference_key,
                "fixture_version": source.fixture_version,
                "manifest_digest": source.manifest_digest,
                "asset_id": asset.id,
                "lifecycle": source.lifecycle.value,
                "validation_state": source.validation_state.value,
                "source_crs": source.source_crs,
                "stored_crs": source.stored_crs,
                "schema_state": source.schema_state.value,
                "family": source.geometry_family.value,
                "dimensions": source.dimensions.value,
                "count_state": source.feature_count_state.value,
                "count": source.feature_count,
                "extent_state": source.extent_state.value,
                "extent": json.dumps(asdict(source.extent)) if source.extent is not None else None,
                "revision": source.catalog_revision,
                "content": source.content_revision,
                "schema": source.schema_revision,
                "created_at": source.created_at,
                "updated_at": source.updated_at,
            },
        )

        # 2. Insert spatial.source_fields
        if fields:
            self._session.execute(
                text("""
                    INSERT INTO spatial.source_fields (
                        organization_id, project_id, source_id,
                        field_id, name, ordinal, type, nullable, schema_revision
                    )
                    SELECT :organization, :project, :source, r.field_id, r.name, r.ordinal,
                           r.type, r.nullable, :schema
                    FROM jsonb_to_recordset(CAST(:records AS jsonb))
                        AS r(field_id text, name text, ordinal integer, type text, nullable boolean)
                """),
                params
                | {
                    "source": source.id,
                    "schema": source.schema_revision,
                    "records": json.dumps(
                        [
                            {
                                "field_id": f.field_id,
                                "name": f.name,
                                "ordinal": f.ordinal,
                                "type": f.type.value,
                                "nullable": f.nullable,
                            }
                            for f in fields
                        ]
                    ),
                },
            )

        # 3. Insert spatial.reference_features in bounded batches
        batch_size = 2500
        for start in range(0, len(features), batch_size):
            chunk = features[start : start + batch_size]
            self._session.execute(
                text("""
                    INSERT INTO spatial.reference_features (
                        organization_id, project_id, source_id,
                        feature_id, attributes, geometry, geometry_state,
                        content_revision, schema_revision
                    )
                    SELECT :organization, :project, :source, r.feature_id, r.attributes,
                           ST_GeomFromText(r.wkt, :srid), r.geometry_state, :content, :schema
                    FROM jsonb_to_recordset(CAST(:records AS jsonb))
                        AS r(feature_id text, attributes jsonb, wkt text, geometry_state text)
                """),
                params
                | {
                    "source": source.id,
                    "srid": source.stored_crs,
                    "content": source.content_revision,
                    "schema": source.schema_revision,
                    "records": json.dumps(
                        [
                            {
                                "feature_id": feat.feature_id,
                                "attributes": dict(feat.attributes),
                                "wkt": _wkt(feat.geometry) if feat.geometry else None,
                                "geometry_state": feat.geometry_state.value,
                            }
                            for feat in chunk
                        ]
                    ),
                },
            )

        # 4. Insert spatial.layers
        now = source.created_at
        layer = Layer(
            id=layer_id,
            organization_id=context.organization_id,
            project_id=params["project"],
            source_id=source.id,
            name=layer_name,
            lifecycle=Lifecycle.ACTIVE,
            layer_revision=1,
            created_at=now,
            updated_at=now,
            retired_at=None,
        )
        self._session.execute(
            text("""
                INSERT INTO spatial.layers (
                    id, organization_id, project_id, source_id, name,
                    lifecycle, layer_revision, created_at, updated_at, retired_at
                ) VALUES (
                    :id, :organization, :project, :source, :name,
                    'active', 1, :created_at, :updated_at, NULL
                )
            """),
            params
            | {
                "id": layer.id,
                "source": layer.source_id,
                "name": layer.name,
                "created_at": layer.created_at,
                "updated_at": layer.updated_at,
            },
        )

        # 5. Record immutable CatalogChange + AuditEvent for both source & layer
        source_change_id = uuid4()
        source_audit_id = uuid4()
        source_changes = (
            ChangedValue("name", None, source.name),
            ChangedValue("kind", None, source.kind.value),
            ChangedValue("manifest_digest", None, source.manifest_digest),
            ChangedValue("source_asset_id", None, str(asset.id)),
            ChangedValue("source_crs", None, source.source_crs),
            ChangedValue("stored_crs", None, source.stored_crs),
            ChangedValue("feature_count", None, source.feature_count),
            ChangedValue("content_revision", None, source.content_revision),
            ChangedValue("schema_revision", None, source.schema_revision),
        )
        source_change = CatalogChange(
            id=source_change_id,
            organization_id=context.organization_id,
            project_id=params["project"],
            resource_type=ResourceType.DATA_SOURCE,
            resource_id=source.id,
            source_id=source.id,
            layer_id=None,
            actor_type=ActorType(context.actor.actor_type),
            actor_id=_req_actor_id(context),
            actor_display_snapshot=context.actor.display_name,
            operation=CatalogOperation.IMPORT_SOURCE,
            created_at=now,
            audit_event_id=source_audit_id,
            prior_revision=None,
            new_revision=SourceRevision(1, source.content_revision, source.schema_revision),
            changes=source_changes,
        )
        SqlAuditRepository(self._session).append(
            AuditEvent(
                id=source_audit_id,
                organization_id=context.organization_id,
                actor_type=ActorType(context.actor.actor_type),
                actor_id=_req_actor_id(context),
                actor_display_snapshot=context.actor.display_name,
                action="spatial.catalog.import_source",
                resource_type="data_source",
                resource_id=source.id,
                outcome=AuditOutcome.SUCCESS,
                created_at=now,
                metadata={
                    "project_id": str(context.project_id),
                    "catalog_change_id": str(source_change_id),
                },
            )
        )
        self._insert_catalog_change(params, source_change)

        layer_change_id = uuid4()
        layer_audit_id = uuid4()
        layer_change = CatalogChange(
            id=layer_change_id,
            organization_id=context.organization_id,
            project_id=params["project"],
            resource_type=ResourceType.LAYER,
            resource_id=layer.id,
            source_id=None,
            layer_id=layer.id,
            actor_type=ActorType(context.actor.actor_type),
            actor_id=_req_actor_id(context),
            actor_display_snapshot=context.actor.display_name,
            operation=CatalogOperation.CREATE_LAYER,
            created_at=now,
            audit_event_id=layer_audit_id,
            prior_revision=None,
            new_revision=LayerRevision(1),
            changes=(
                ChangedValue("name", None, layer.name),
                ChangedValue("source_id", None, str(source.id)),
                ChangedValue("lifecycle", None, "active"),
            ),
        )
        SqlAuditRepository(self._session).append(
            AuditEvent(
                id=layer_audit_id,
                organization_id=context.organization_id,
                actor_type=ActorType(context.actor.actor_type),
                actor_id=_req_actor_id(context),
                actor_display_snapshot=context.actor.display_name,
                action="spatial.catalog.create_layer",
                resource_type="layer",
                resource_id=layer.id,
                outcome=AuditOutcome.SUCCESS,
                created_at=now,
                metadata={
                    "project_id": str(context.project_id),
                    "catalog_change_id": str(layer_change_id),
                },
            )
        )
        self._insert_catalog_change(params, layer_change)

        # 6. Mark transfer job succeeded atomically in the same transaction
        done_at = datetime.now(UTC)
        return self.update_job(
            context=context,
            job_id=job_id,
            status=JobStatus.SUCCEEDED,
            target_source_id=source.id,
            target_layer_id=layer.id,
            source_content_revision=source.content_revision,
            source_schema_revision=source.schema_revision,
            result_report=result_report,
            error_code=None,
            error_message=None,
            completed_at=done_at,
        )

    def _insert_catalog_change(self, params: dict[str, UUID], change: CatalogChange) -> None:
        self._session.execute(
            text("""
                INSERT INTO spatial.catalog_changes (
                    id, organization_id, project_id, resource_type, resource_id, source_id,
                    layer_id, actor_type, actor_id, actor_display_snapshot, operation, created_at,
                    audit_event_id, prior_revision, new_revision, changes
                ) VALUES (
                    :id, :organization, :project, :resource_type, :resource_id, :source_id,
                    :layer_id, :actor_type, :actor_id, :actor_display_snapshot, :operation,
                    :created_at, :audit_event_id, CAST(:prior AS jsonb),
                    CAST(:new AS jsonb), CAST(:changes AS jsonb)
                )
            """),
            params
            | {
                "id": change.id,
                "resource_type": change.resource_type.value,
                "resource_id": change.resource_id,
                "source_id": change.source_id,
                "layer_id": change.layer_id,
                "actor_type": change.actor_type.value,
                "actor_id": change.actor_id,
                "actor_display_snapshot": change.actor_display_snapshot,
                "operation": change.operation.value,
                "created_at": change.created_at,
                "audit_event_id": change.audit_event_id,
                "prior": json.dumps(change.prior_revision.to_wire())
                if change.prior_revision is not None
                else None,
                "new": json.dumps(change.new_revision.to_wire()),
                "changes": json.dumps([item.to_wire() for item in change.changes]),
            },
        )

    def load_pinned_export_source(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        expected_content_revision: str,
        expected_schema_revision: str,
    ) -> tuple[DataSource, tuple[SourceField, ...], tuple[ReferenceFeature, ...], str]:
        params = self._scope(context, write=False)
        layer_row = (
            self._session.execute(
                text("""
                SELECT id, source_id, name, lifecycle FROM spatial.layers
                WHERE organization_id = :organization AND project_id = :project AND id = :lid
            """),
                params | {"lid": layer_id},
            )
            .mappings()
            .one_or_none()
        )
        if layer_row is None or layer_row["lifecycle"] != "active":
            raise TransferNotFoundError("Layer not found.")
        source_row = (
            self._session.execute(
                text("""
                SELECT * FROM spatial.data_sources
                WHERE organization_id = :organization AND project_id = :project AND id = :sid
            """),
                params | {"sid": layer_row["source_id"]},
            )
            .mappings()
            .one_or_none()
        )
        if source_row is None or source_row["lifecycle"] != "active":
            raise TransferNotFoundError("Source not found.")
        source = _source_from_row(source_row)
        if source.validation_state != ValidationState.READY:
            raise TransferValidationError("SOURCE_NOT_READY", "Source is not ready for export.")
        if (
            source.content_revision != expected_content_revision
            or source.schema_revision != expected_schema_revision
        ):
            raise TransferConflictError(
                "STALE_READ_PIN",
                "Requested source revision is stale; reload Layer metadata before exporting.",
            )
        field_rows = (
            self._session.execute(
                text("""
                SELECT * FROM spatial.source_fields
                WHERE organization_id = :organization AND project_id = :project
                  AND source_id = :sid AND schema_revision = :schema
                ORDER BY ordinal ASC
            """),
                params | {"sid": source.id, "schema": source.schema_revision},
            )
            .mappings()
            .all()
        )
        fields = tuple(
            SourceField(
                organization_id=r["organization_id"],
                project_id=r["project_id"],
                source_id=r["source_id"],
                field_id=r["field_id"],
                name=r["name"],
                type=FieldType(r["type"]),
                nullable=bool(r["nullable"]),
                ordinal=int(r["ordinal"]),
                schema_revision=r["schema_revision"],
            )
            for r in field_rows
        )
        feat_rows = (
            self._session.execute(
                text(
                    "SELECT "
                    + _FEATURE_COLUMNS
                    + """
                    FROM spatial.reference_features
                    WHERE organization_id = :organization AND project_id = :project
                      AND source_id = :sid
                      AND content_revision = :content
                      AND schema_revision = :schema
                    ORDER BY feature_id ASC
                    """
                ),
                params
                | {
                    "sid": source.id,
                    "content": source.content_revision,
                    "schema": source.schema_revision,
                },
            )
            .mappings()
            .all()
        )
        features = tuple(_feature_from_row(r) for r in feat_rows)
        return source, fields, features, str(layer_row["name"])

    def publish_export_artifact(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        artifact: DerivedArtifact,
        result_report: dict[str, Any],
    ) -> TransferJob:
        # Re-verify current read authority & cancel boundary atomically
        params = self._scope(context, write=False)
        locked = self._session.execute(
            text("""
                SELECT status FROM transfers.jobs
                WHERE organization_id = :organization AND project_id = :project AND id = :id
                FOR UPDATE
            """),
            params | {"id": job_id},
        ).scalar_one_or_none()
        if locked is None:
            raise TransferNotFoundError("Transfer job not found.")
        if locked in (JobStatus.CANCELLED.value, JobStatus.CANCEL_REQUESTED.value):
            raise TransferConflictError("JOB_CANCELLED", "Export cancelled before publication.")

        self._session.execute(
            text("""
                INSERT INTO transfers.derived_artifacts (
                    id, organization_id, project_id, job_id, source_id, layer_id,
                    source_content_revision, source_schema_revision, output_format,
                    output_crs, filename, content_type, byte_size, sha256, storage_key,
                    comparison_report, created_by_type, created_by_id, created_by_display,
                    created_at, expires_at, state
                ) VALUES (
                    :id, :organization, :project, :job_id, :source_id, :layer_id,
                    :content_rev, :schema_rev, :fmt,
                    :crs, :filename, :content_type, :byte_size, :sha256, :storage_key,
                    CAST(:report AS jsonb), :actor_type, :actor_id, :actor_display,
                    :created_at, :expires_at, :state
                )
            """),
            params
            | {
                "id": artifact.id,
                "job_id": artifact.job_id,
                "source_id": artifact.source_id,
                "layer_id": artifact.layer_id,
                "content_rev": artifact.source_content_revision,
                "schema_rev": artifact.source_schema_revision,
                "fmt": artifact.output_format.value,
                "crs": artifact.output_crs,
                "filename": artifact.filename,
                "content_type": artifact.content_type,
                "byte_size": artifact.byte_size,
                "sha256": artifact.sha256,
                "storage_key": artifact.storage_key,
                "report": json.dumps(artifact.comparison_report),
                "actor_type": artifact.created_by_type.value,
                "actor_id": artifact.created_by_id,
                "actor_display": artifact.created_by_display,
                "created_at": artifact.created_at,
                "expires_at": artifact.expires_at,
                "state": artifact.state.value,
            },
        )
        SqlAuditRepository(self._session).append(
            AuditEvent(
                id=uuid4(),
                organization_id=context.organization_id,
                actor_type=ActorType(context.actor.actor_type),
                actor_id=_req_actor_id(context),
                actor_display_snapshot=context.actor.display_name,
                action="transfers.export.completed",
                resource_type="derived_artifact",
                resource_id=artifact.id,
                outcome=AuditOutcome.SUCCESS,
                created_at=artifact.created_at,
                metadata={
                    "project_id": str(context.project_id),
                    "job_id": str(job_id),
                    "source_id": str(artifact.source_id),
                    "content_revision": artifact.source_content_revision,
                    "output_format": artifact.output_format.value,
                    "output_crs": artifact.output_crs,
                },
            )
        )
        return self.update_job(
            context=context,
            job_id=job_id,
            status=JobStatus.SUCCEEDED,
            artifact_id=artifact.id,
            result_report=result_report,
            error_code=None,
            error_message=None,
            completed_at=artifact.created_at,
        )

    def get_artifact(
        self, *, context: AuthorizationContext, artifact_id: UUID
    ) -> DerivedArtifact | None:
        params = self._scope(context, write=False)
        row = (
            self._session.execute(
                text("""
                SELECT * FROM transfers.derived_artifacts
                WHERE organization_id = :organization AND project_id = :project AND id = :id
            """),
                params | {"id": artifact_id},
            )
            .mappings()
            .one_or_none()
        )
        return _artifact_from_row(row) if row is not None else None

    def mark_artifact_state(
        self, *, context: AuthorizationContext, artifact_id: UUID, state: ArtifactState
    ) -> None:
        params = self._scope(context, write=False)
        self._session.execute(
            text("""
                UPDATE transfers.derived_artifacts
                SET state = :state
                WHERE organization_id = :organization AND project_id = :project AND id = :id
            """),
            params | {"id": artifact_id, "state": state.value},
        )

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
