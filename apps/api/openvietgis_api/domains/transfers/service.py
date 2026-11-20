"""R005 Import, Export, and Durable Job application service (pure domain)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.spatial.crs import get_transformation_profile
from openvietgis_api.domains.spatial.domain import (
    DataSource,
    Extent,
    ExtentState,
    FeatureCountState,
    GeometryDimensions,
    GeometryState,
    Lifecycle,
    ReferenceFeature,
    SchemaState,
    SourceField,
    SourceKind,
    ValidationState,
    canonical_attribute_value,
    validate_ready_geometry,
)
from openvietgis_api.domains.spatial.service import derive_source_pins
from openvietgis_api.domains.tenancy.domain import ActorType
from openvietgis_api.domains.transfers.domain import (
    ARTIFACT_TTL_HOURS,
    MAX_TRANSFER_FEATURES,
    MAX_UPLOAD_BYTES,
    SUPPORTED_CRS_CODES,
    SUPPORTED_ENCODINGS,
    TERMINAL_JOB_STATUSES,
    ArtifactState,
    ConversionDisclosure,
    DerivedArtifact,
    ExportPreviewReport,
    ImportInspectionReport,
    InspectedField,
    JobKind,
    JobStatus,
    SourceAsset,
    TransferFormat,
    TransferJob,
    ValidationFinding,
    can_transition,
    canonical_fingerprint,
    normalize_encoding,
    plan_export_mapping,
    resolve_crs_transform,
    sanitize_filename,
)
from openvietgis_api.domains.transfers.ports import (
    FormatCodecPort,
    ObjectStorePort,
    TransferArtifactUnavailableError,
    TransferConflictError,
    TransferError,
    TransferLimitExceededError,
    TransferNotFoundError,
    TransferRepository,
    TransferValidationError,
)


def _req_uuid(value: UUID | None) -> UUID:
    if value is None:
        raise TransferValidationError("MISSING_SCOPE_ID", "Required scope UUID is missing.")
    return value


def _compute_extent(geometries: Sequence[Any], crs_code: int) -> tuple[ExtentState, Extent | None]:
    if not geometries:
        return ExtentState.EMPTY, None
    xs: list[float] = []
    ys: list[float] = []

    def _collect(coords: Any) -> None:
        if isinstance(coords, (list, tuple)) and coords:
            if isinstance(coords[0], (int, float)):
                xs.append(float(coords[0]))
                ys.append(float(coords[1]))
            else:
                for item in coords:
                    _collect(item)

    for geom in geometries:
        _collect(geom.coordinates)
    if not xs or not ys:
        return ExtentState.EMPTY, None
    return (
        ExtentState.AVAILABLE,
        Extent(min(xs), min(ys), max(xs), max(ys), crs_code),
    )


@dataclass(slots=True)
class TransferService:
    repository: TransferRepository
    store: ObjectStorePort
    codec: FormatCodecPort

    def upload_and_inspect(
        self,
        *,
        context: AuthorizationContext,
        filename: str,
        payload: bytes,
    ) -> tuple[SourceAsset, ImportInspectionReport]:
        self.repository.verify_project_authority(context=context, write=True)
        if not payload:
            raise TransferValidationError("EMPTY_UPLOAD", "Uploaded file is empty.")
        if len(payload) > MAX_UPLOAD_BYTES:
            raise TransferLimitExceededError(
                "UPLOAD_SIZE_EXCEEDED",
                f"Uploaded file exceeds maximum allowed size of {MAX_UPLOAD_BYTES} bytes.",
            )
        detected_format = self.codec.detect_format(payload)
        safe_name = sanitize_filename(filename, fallback=f"upload.{detected_format.value}")
        asset_id = uuid4()
        storage_key = f"assets/{context.organization_id}/{context.project_id}/{asset_id}.bin"
        sha256, byte_size = self.store.put_bytes(storage_key, payload)
        asset = SourceAsset(
            id=asset_id,
            organization_id=context.organization_id,
            project_id=_req_uuid(context.project_id),
            filename=safe_name,
            detected_format=detected_format,
            byte_size=byte_size,
            sha256=sha256,
            storage_key=storage_key,
            uploaded_by_type=ActorType(context.actor.actor_type),
            uploaded_by_id=_req_uuid(context.actor.actor_id),
            uploaded_by_display=context.actor.display_name,
            created_at=datetime.now(UTC),
        )
        try:
            persisted = self.repository.create_source_asset(context=context, asset=asset)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            self.store.delete_object(storage_key)
            raise
        report = self._build_inspection(
            asset=persisted,
            payload=payload,
            selected_member=None,
            declared_source_crs=None,
            target_crs=None,
            declared_encoding=None,
        )
        return persisted, report

    def inspect_asset(
        self,
        *,
        context: AuthorizationContext,
        source_asset_id: UUID,
        selected_member: str | None = None,
        declared_source_crs: int | None = None,
        target_crs: int | None = None,
        declared_encoding: str | None = None,
    ) -> tuple[SourceAsset, ImportInspectionReport]:
        self.repository.verify_project_authority(context=context, write=True)
        asset = self.repository.get_source_asset(context=context, asset_id=source_asset_id)
        if asset is None:
            raise TransferNotFoundError("Source asset not found.")
        payload = self.store.get_bytes(asset.storage_key, expected_sha256=asset.sha256)
        report = self._build_inspection(
            asset=asset,
            payload=payload,
            selected_member=selected_member,
            declared_source_crs=declared_source_crs,
            target_crs=target_crs,
            declared_encoding=declared_encoding,
        )
        return asset, report

    def _build_inspection(
        self,
        *,
        asset: SourceAsset,
        payload: bytes,
        selected_member: str | None,
        declared_source_crs: int | None,
        target_crs: int | None,
        declared_encoding: str | None,
    ) -> ImportInspectionReport:
        normalized_enc = normalize_encoding(declared_encoding)
        if declared_encoding is not None and normalized_enc not in SUPPORTED_ENCODINGS:
            raise TransferValidationError(
                "UNSUPPORTED_ENCODING",
                "Declared text encoding is not in the accepted encoding profile.",
            )
        members = self.codec.list_members(asset.detected_format, payload, encoding=normalized_enc)
        eligible_members = [m for m in members if m.eligible]
        chosen = selected_member
        requires_member_selection = False
        if chosen is None:
            if len(eligible_members) == 1:
                chosen = eligible_members[0].name
            elif len(eligible_members) > 1:
                requires_member_selection = True
        elif not any(m.name == chosen for m in members):
            raise TransferValidationError(
                "UNKNOWN_MEMBER", "Selected dataset member does not exist."
            )

        findings: list[ValidationFinding] = []
        conversions: list[ConversionDisclosure] = []
        resolved_source_crs: int | None = declared_source_crs
        resolved_target_crs: int | None = target_crs
        resolved_encoding: str | None = normalized_enc
        requires_crs_resolution = False
        requires_encoding_resolution = False
        feature_count = 0
        geometry_family: str | None = None
        dimensions: str | None = None
        extent: dict[str, float | int] | None = None
        fields: tuple[InspectedField, ...] = ()

        if chosen is not None:
            member_info = next(m for m in members if m.name == chosen)
            if not member_info.eligible:
                findings.append(
                    ValidationFinding(
                        severity="error",
                        code="INELIGIBLE_MEMBER",
                        message=member_info.reason or "Selected member is not supported.",
                    )
                )
            else:
                parsed = self.codec.parse_member(
                    asset.detected_format,
                    payload,
                    member_name=chosen,
                    declared_crs=declared_source_crs,
                    declared_encoding=normalized_enc,
                )
                findings.extend(parsed.findings)
                feature_count = len(parsed.features)
                geometry_family = parsed.geometry_family.value
                dimensions = parsed.dimensions.value
                extent = parsed.extent
                fields = parsed.fields
                resolved_encoding = parsed.detected_encoding
                requires_encoding_resolution = parsed.requires_encoding_resolution

                if parsed.detected_crs is not None:
                    if (
                        declared_source_crs is not None
                        and declared_source_crs != parsed.detected_crs
                    ):
                        findings.append(
                            ValidationFinding(
                                severity="error",
                                code="CRS_DECLARATION_CONFLICT",
                                message=(
                                    f"Declared CRS EPSG:{declared_source_crs} conflicts with "
                                    f"file CRS EPSG:{parsed.detected_crs}."
                                ),
                            )
                        )
                    resolved_source_crs = parsed.detected_crs
                elif declared_source_crs is not None:
                    if declared_source_crs not in SUPPORTED_CRS_CODES:
                        findings.append(
                            ValidationFinding(
                                severity="error",
                                code="UNSUPPORTED_CRS",
                                message=f"Declared CRS EPSG:{declared_source_crs} is unsupported.",
                            )
                        )
                    else:
                        resolved_source_crs = declared_source_crs
                        conversions.append(
                            ConversionDisclosure(
                                code="EXPLICIT_CRS_ASSIGNMENT",
                                message=(
                                    f"Missing file CRS resolved explicitly to "
                                    f"EPSG:{declared_source_crs}."
                                ),
                                requires_approval=False,
                            )
                        )
                else:
                    requires_crs_resolution = True
                    findings.append(
                        ValidationFinding(
                            severity="error",
                            code="MISSING_CRS",
                            message=(
                                "Source CRS is missing or unrecognized; "
                                "select an approved EPSG profile."
                            ),
                        )
                    )

                if requires_encoding_resolution:
                    findings.append(
                        ValidationFinding(
                            severity="error",
                            code="AMBIGUOUS_ENCODING",
                            message=(
                                "Text encoding is ambiguous; "
                                "select an approved encoding explicitly."
                            ),
                        )
                    )

                if resolved_source_crs is not None:
                    resolved_target_crs = target_crs or resolved_source_crs
                    if resolved_target_crs not in SUPPORTED_CRS_CODES:
                        findings.append(
                            ValidationFinding(
                                severity="error",
                                code="UNSUPPORTED_TARGET_CRS",
                                message=f"Target CRS EPSG:{resolved_target_crs} is unsupported.",
                            )
                        )
                    elif resolved_target_crs != resolved_source_crs:
                        profile = get_transformation_profile(
                            resolved_source_crs, resolved_target_crs
                        )
                        if profile is None:
                            findings.append(
                                ValidationFinding(
                                    severity="error",
                                    code="UNSUPPORTED_TRANSFORMATION",
                                    message=(
                                        f"No verified transformation from "
                                        f"EPSG:{resolved_source_crs} "
                                        f"to EPSG:{resolved_target_crs}."
                                    ),
                                )
                            )
                        else:
                            conversions.append(
                                ConversionDisclosure(
                                    code="CRS_TRANSFORMATION",
                                    message=(
                                        f"Transform coordinates from EPSG:{resolved_source_crs} "
                                        f"to EPSG:{resolved_target_crs} ({profile.operation_id})."
                                    ),
                                    requires_approval=False,
                                )
                            )
                    renamed = tuple(
                        f"{f.source_name}->{f.field_id}"
                        for f in fields
                        if f.source_name != f.field_id
                    )
                    if renamed:
                        conversions.append(
                            ConversionDisclosure(
                                code="FIELD_ID_NORMALIZATION",
                                message=(
                                    "Source field names mapped to canonical "
                                    "stable field identities."
                                ),
                                requires_approval=False,
                                affected_fields=renamed,
                            )
                        )
        elif not eligible_members:
            findings.append(
                ValidationFinding(
                    severity="error",
                    code="NO_ELIGIBLE_MEMBERS",
                    message="Dataset contains no supported vector layer members.",
                )
            )

        has_errors = any(f.severity == "error" for f in findings)
        confirmable = (
            chosen is not None
            and not requires_member_selection
            and not requires_crs_resolution
            and not requires_encoding_resolution
            and resolved_source_crs is not None
            and resolved_target_crs is not None
            and not has_errors
        )
        fingerprint = canonical_fingerprint(
            {
                "kind": "import",
                "asset_id": str(asset.id),
                "asset_sha256": asset.sha256,
                "format": asset.detected_format.value,
                "member": chosen,
                "source_crs": resolved_source_crs,
                "target_crs": resolved_target_crs,
                "encoding": resolved_encoding,
            }
        )
        return ImportInspectionReport(
            asset_sha256=asset.sha256,
            detected_format=asset.detected_format,
            members=members,
            selected_member=chosen,
            requires_member_selection=requires_member_selection,
            requires_crs_resolution=requires_crs_resolution,
            requires_encoding_resolution=requires_encoding_resolution,
            resolved_source_crs=resolved_source_crs,
            target_crs=resolved_target_crs,
            resolved_encoding=resolved_encoding,
            sample_only=False,
            feature_count=feature_count,
            geometry_family=geometry_family,
            dimensions=dimensions,
            extent=extent,
            fields=fields,
            findings=tuple(findings),
            conversions=tuple(conversions),
            confirmable=confirmable,
            inspection_fingerprint=fingerprint,
        )

    def confirm_import(
        self,
        *,
        context: AuthorizationContext,
        operation_id: UUID,
        source_asset_id: UUID,
        selected_member: str,
        source_name: str,
        layer_name: str,
        declared_source_crs: int | None,
        target_crs: int | None,
        declared_encoding: str | None,
        approved_conversions: Sequence[str],
        inspection_fingerprint: str,
    ) -> TransferJob:
        self.repository.verify_project_authority(context=context, write=True)
        asset = self.repository.get_source_asset(context=context, asset_id=source_asset_id)
        if asset is None:
            raise TransferNotFoundError("Source asset not found.")
        payload = self.store.get_bytes(asset.storage_key, expected_sha256=asset.sha256)
        inspection = self._build_inspection(
            asset=asset,
            payload=payload,
            selected_member=selected_member,
            declared_source_crs=declared_source_crs,
            target_crs=target_crs,
            declared_encoding=declared_encoding,
        )
        if inspection.inspection_fingerprint != inspection_fingerprint:
            raise TransferConflictError(
                "STALE_INSPECTION",
                "Import inspection fingerprint does not match current asset or options.",
            )
        request_fp = canonical_fingerprint(
            {
                "inspection_fingerprint": inspection.inspection_fingerprint,
                "source_name": source_name.strip(),
                "layer_name": layer_name.strip(),
                "approved_conversions": sorted(set(approved_conversions)),
            }
        )
        existing = self.repository.get_job_by_operation(
            context=context, operation_id=operation_id, lock=True
        )
        if existing is not None:
            if existing.request_fingerprint != request_fp:
                raise TransferConflictError(
                    "OPERATION_INTENT_CONFLICT",
                    "This import operation_id was already used with a different request.",
                )
            return existing

        if not inspection.confirmable:
            first_error = next((f for f in inspection.findings if f.severity == "error"), None)
            raise TransferValidationError(
                first_error.code if first_error else "IMPORT_NOT_CONFIRMABLE",
                first_error.message if first_error else "Import validation failed.",
            )
        required_approvals = {c.code for c in inspection.conversions if c.requires_approval}
        missing_approvals = required_approvals - set(approved_conversions)
        if missing_approvals:
            joined = ", ".join(sorted(missing_approvals))
            raise TransferValidationError(
                "UNAPPROVED_CONVERSION",
                f"Explicit approval required for conversions: {joined}.",
            )

        now = datetime.now(UTC)
        job_id = uuid4()
        options_json: dict[str, Any] = {
            "selected_member": selected_member,
            "source_name": source_name.strip(),
            "layer_name": layer_name.strip(),
            "declared_source_crs": declared_source_crs,
            "target_crs": inspection.target_crs,
            "declared_encoding": inspection.resolved_encoding,
            "approved_conversions": sorted(set(approved_conversions)),
        }
        job = TransferJob(
            id=job_id,
            organization_id=context.organization_id,
            project_id=_req_uuid(context.project_id),
            operation_id=operation_id,
            kind=JobKind.IMPORT,
            request_fingerprint=request_fp,
            status=JobStatus.ACTIVE,
            actor_type=ActorType(context.actor.actor_type),
            actor_id=_req_uuid(context.actor.actor_id),
            actor_display_snapshot=context.actor.display_name,
            credential_id=context.credential_id,
            source_asset_id=asset.id,
            target_source_id=None,
            target_layer_id=None,
            source_content_revision=None,
            source_schema_revision=None,
            artifact_id=None,
            attempt_count=1,
            options_json=options_json,
            inspection_report=inspection.to_wire(),
            result_report=None,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self.repository.create_job(context=context, job=job)
        self.repository.record_attempt(
            context=context,
            job_id=job_id,
            attempt_number=1,
            status="active",
            started_at=now,
        )
        self.repository.commit()
        return self._execute_import_attempt(
            context=context,
            job_id=job_id,
            asset=asset,
            payload=payload,
            inspection=inspection,
            source_name=source_name.strip(),
            layer_name=layer_name.strip(),
        )

    def _execute_import_attempt(
        self,
        *,
        context: AuthorizationContext,
        job_id: UUID,
        asset: SourceAsset,
        payload: bytes,
        inspection: ImportInspectionReport,
        source_name: str,
        layer_name: str,
    ) -> TransferJob:
        try:
            assert inspection.selected_member is not None
            assert inspection.resolved_source_crs is not None
            assert inspection.target_crs is not None
            parsed = self.codec.parse_member(
                asset.detected_format,
                payload,
                member_name=inspection.selected_member,
                declared_crs=inspection.resolved_source_crs,
                declared_encoding=inspection.resolved_encoding,
            )
            if any(f.severity == "error" for f in parsed.findings):
                err = next(f for f in parsed.findings if f.severity == "error")
                raise TransferValidationError(err.code, err.message)
            if len(parsed.features) > MAX_TRANSFER_FEATURES:
                raise TransferLimitExceededError(
                    "FEATURE_LIMIT_EXCEEDED",
                    f"Feature count exceeds limit of {MAX_TRANSFER_FEATURES}.",
                )

            geometries = [f.geometry for f in parsed.features]
            validated_geoms = self.repository.validate_and_transform_geometries(
                context=context,
                geometries=geometries,
                source_crs=inspection.resolved_source_crs,
                target_crs=inspection.target_crs,
                expected_family=parsed.geometry_family.value,
            )

            source_id = uuid4()
            layer_id = uuid4()
            now = datetime.now(UTC)
            placeholder = "0" * 64
            domain_fields = tuple(
                SourceField(
                    organization_id=context.organization_id,
                    project_id=_req_uuid(context.project_id),
                    source_id=source_id,
                    field_id=f.field_id,
                    name=f.name,
                    type=f.type,
                    nullable=f.nullable,
                    ordinal=f.ordinal,
                    schema_revision=placeholder,
                )
                for f in parsed.fields
            )
            domain_features = []
            for rec, geom in zip(parsed.features, validated_geoms, strict=True):
                validate_ready_geometry(
                    geom, parsed.geometry_family, inspection.target_crs, output_roundoff=True
                )
                canonical_attrs = {
                    fld.field_id: canonical_attribute_value(fld, rec.attributes.get(fld.field_id))
                    for fld in domain_fields
                }
                domain_features.append(
                    ReferenceFeature(
                        organization_id=context.organization_id,
                        project_id=_req_uuid(context.project_id),
                        source_id=source_id,
                        feature_id=rec.feature_id,
                        attributes=canonical_attrs,
                        geometry_state=GeometryState.PRESENT,
                        geometry=geom,
                        content_revision=placeholder,
                        schema_revision=placeholder,
                    )
                )

            extent_state, extent = _compute_extent(validated_geoms, inspection.target_crs)
            ref_key = f"imp_{asset.id.hex[:12]}_{source_id.hex[:12]}"
            provisional_source = DataSource(
                id=source_id,
                organization_id=context.organization_id,
                project_id=_req_uuid(context.project_id),
                name=source_name,
                kind=SourceKind.IMPORTED_FILE,
                reference_key=ref_key,
                fixture_version=f"{asset.detected_format.value}:{inspection.selected_member}"[:100],
                manifest_digest=asset.sha256,
                source_asset_id=asset.id,
                lifecycle=Lifecycle.ACTIVE,
                validation_state=ValidationState.READY,
                validation_reason=None,
                source_crs=inspection.resolved_source_crs,
                stored_crs=inspection.target_crs,
                schema_state=SchemaState.KNOWN,
                geometry_family=parsed.geometry_family,
                dimensions=GeometryDimensions.XY,
                feature_count_state=FeatureCountState.KNOWN,
                feature_count=len(domain_features),
                extent_state=extent_state,
                extent=extent,
                catalog_revision=1,
                content_revision=placeholder,
                schema_revision=placeholder,
                created_at=now,
                updated_at=now,
                retired_at=None,
            )
            pinned = derive_source_pins(provisional_source, domain_fields, domain_features)
            op_id = resolve_crs_transform(inspection.resolved_source_crs, inspection.target_crs)
            result_report: dict[str, Any] = {
                "asset_id": str(asset.id),
                "asset_sha256": asset.sha256,
                "format": asset.detected_format.value,
                "selected_member": inspection.selected_member,
                "source_id": str(pinned.source.id),
                "layer_id": str(layer_id),
                "content_revision": pinned.source.content_revision,
                "schema_revision": pinned.source.schema_revision,
                "feature_count": len(pinned.features),
                "source_crs": inspection.resolved_source_crs,
                "stored_crs": inspection.target_crs,
                "transformation_operation_id": op_id,
                "encoding": inspection.resolved_encoding,
            }
            published = self.repository.publish_imported_source_and_layer(
                context=context,
                job_id=job_id,
                asset=asset,
                source=pinned.source,
                fields=pinned.fields,
                features=pinned.features,
                layer_id=layer_id,
                layer_name=layer_name,
                result_report=result_report,
            )
            self.repository.commit()
            return published
        except TransferError as exc:
            self.repository.rollback()
            self.repository.update_job(
                context=context,
                job_id=job_id,
                status=JobStatus.FAILED,
                error_code=exc.code,
                error_message=exc.message[:500],
                completed_at=datetime.now(UTC),
            )
            self.repository.commit()
            raise
        except Exception as exc:
            self.repository.rollback()
            self.repository.update_job(
                context=context,
                job_id=job_id,
                status=JobStatus.RECOVERABLE_FAILED,
                error_code="IMPORT_EXECUTION_INTERRUPTED",
                error_message=(
                    "Import execution did not complete; retry with fresh authorization."
                ),
                completed_at=None,
            )
            self.repository.commit()
            raise exc

    def preview_export(
        self,
        *,
        context: AuthorizationContext,
        layer_id: UUID,
        content_revision: str,
        schema_revision: str,
        output_format: TransferFormat,
        output_crs: int,
    ) -> ExportPreviewReport:
        self.repository.verify_project_authority(context=context, write=False)
        source, fields, features, _layer_name = self.repository.load_pinned_export_source(
            context=context,
            layer_id=layer_id,
            expected_content_revision=content_revision,
            expected_schema_revision=schema_revision,
        )
        if source.stored_crs is None:
            raise TransferValidationError("MISSING_CRS", "Source has no verified stored CRS.")
        has_long_text = any(
            isinstance(v, str) and len(v.encode("utf-8")) > 254
            for feat in features
            for v in feat.attributes.values()
        )
        try:
            mappings, disclosures, op_id = plan_export_mapping(
                fields,
                output_format,
                source.stored_crs,
                output_crs,
                has_long_text=has_long_text,
            )
        except ValueError as exc:
            raise TransferValidationError("UNSUPPORTED_EXPORT_PROFILE", str(exc)) from None

        fingerprint = canonical_fingerprint(
            {
                "kind": "export",
                "layer_id": str(layer_id),
                "source_id": str(source.id),
                "content_revision": content_revision,
                "schema_revision": schema_revision,
                "output_format": output_format.value,
                "output_crs": output_crs,
                "disclosures": [d.code for d in disclosures],
            }
        )
        return ExportPreviewReport(
            layer_id=layer_id,
            source_id=source.id,
            content_revision=content_revision,
            schema_revision=schema_revision,
            output_format=output_format,
            source_crs=source.stored_crs,
            output_crs=output_crs,
            transformation_operation_id=op_id,
            feature_count=len(features),
            geometry_family=source.geometry_family.value,
            field_mappings=mappings,
            disclosures=disclosures,
            confirmable=True,
            preview_fingerprint=fingerprint,
        )

    def confirm_export(
        self,
        *,
        context: AuthorizationContext,
        operation_id: UUID,
        layer_id: UUID,
        content_revision: str,
        schema_revision: str,
        output_format: TransferFormat,
        output_crs: int,
        approved_disclosures: Sequence[str],
        preview_fingerprint: str,
    ) -> TransferJob:
        self.repository.verify_project_authority(context=context, write=False)
        preview = self.preview_export(
            context=context,
            layer_id=layer_id,
            content_revision=content_revision,
            schema_revision=schema_revision,
            output_format=output_format,
            output_crs=output_crs,
        )
        if preview.preview_fingerprint != preview_fingerprint:
            raise TransferConflictError(
                "STALE_PREVIEW",
                "Export preview fingerprint does not match current revision or options.",
            )
        request_fp = canonical_fingerprint(
            {
                "preview_fingerprint": preview.preview_fingerprint,
                "approved_disclosures": sorted(set(approved_disclosures)),
            }
        )
        existing = self.repository.get_job_by_operation(
            context=context, operation_id=operation_id, lock=True
        )
        if existing is not None:
            if existing.request_fingerprint != request_fp:
                raise TransferConflictError(
                    "OPERATION_INTENT_CONFLICT",
                    "This export operation_id was already used with a different request.",
                )
            return existing

        required_approvals = {d.code for d in preview.disclosures if d.requires_approval}
        missing = required_approvals - set(approved_disclosures)
        if missing:
            joined = ", ".join(sorted(missing))
            raise TransferValidationError(
                "UNAPPROVED_LOSS",
                f"Explicit approval required for export differences: {joined}.",
            )

        now = datetime.now(UTC)
        job_id = uuid4()
        job = TransferJob(
            id=job_id,
            organization_id=context.organization_id,
            project_id=_req_uuid(context.project_id),
            operation_id=operation_id,
            kind=JobKind.EXPORT,
            request_fingerprint=request_fp,
            status=JobStatus.ACTIVE,
            actor_type=ActorType(context.actor.actor_type),
            actor_id=_req_uuid(context.actor.actor_id),
            actor_display_snapshot=context.actor.display_name,
            credential_id=context.credential_id,
            source_asset_id=None,
            target_source_id=preview.source_id,
            target_layer_id=layer_id,
            source_content_revision=content_revision,
            source_schema_revision=schema_revision,
            artifact_id=None,
            attempt_count=1,
            options_json={
                "output_format": output_format.value,
                "output_crs": output_crs,
                "approved_disclosures": sorted(set(approved_disclosures)),
            },
            inspection_report=preview.to_wire(),
            result_report=None,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self.repository.create_job(context=context, job=job)
        self.repository.record_attempt(
            context=context,
            job_id=job_id,
            attempt_number=1,
            status="active",
            started_at=now,
        )
        self.repository.commit()

        artifact_key: str | None = None
        try:
            source, fields, features, layer_name = self.repository.load_pinned_export_source(
                context=context,
                layer_id=layer_id,
                expected_content_revision=content_revision,
                expected_schema_revision=schema_revision,
            )
            assert source.stored_crs is not None
            geoms = [f.geometry for f in features if f.geometry is not None]
            if len(geoms) != len(features):
                raise TransferValidationError(
                    "MISSING_GEOMETRY", "Cannot export features without verified geometry."
                )
            output_geoms = self.repository.validate_and_transform_geometries(
                context=context,
                geometries=geoms,
                source_crs=source.stored_crs,
                target_crs=output_crs,
                expected_family=source.geometry_family.value,
            )
            export_records = [
                (feat.feature_id, dict(feat.attributes), out_geom)
                for feat, out_geom in zip(features, output_geoms, strict=True)
            ]
            out_bytes, ext, content_type = self.codec.write_dataset(
                output_format,
                layer_name=layer_name,
                crs_code=output_crs,
                geometry_family=source.geometry_family.value,
                field_mappings=preview.field_mappings,
                features=export_records,
            )
            artifact_id = uuid4()
            artifact_key = (
                f"artifacts/{context.organization_id}/{context.project_id}/{artifact_id}.{ext}"
            )
            sha256, byte_size = self.store.put_bytes(artifact_key, out_bytes)
            done_at = datetime.now(UTC)
            safe_stem = sanitize_filename(layer_name, fallback="export")
            filename = f"{safe_stem}-{content_revision[:8]}.{ext}"
            null_counts = {
                f.field_id: sum(1 for feat in features if feat.attributes.get(f.field_id) is None)
                for f in fields
            }
            comparison_report: dict[str, Any] = {
                "source_id": str(source.id),
                "layer_id": str(layer_id),
                "source_content_revision": content_revision,
                "source_schema_revision": schema_revision,
                "output_format": output_format.value,
                "source_crs": source.stored_crs,
                "output_crs": output_crs,
                "transformation_operation_id": preview.transformation_operation_id,
                "expected_feature_count": len(features),
                "exported_feature_count": len(export_records),
                "geometry_family": source.geometry_family.value,
                "field_mappings": [m.to_wire() for m in preview.field_mappings],
                "approved_disclosures": sorted(set(approved_disclosures)),
                "lossless_profile": output_format == TransferFormat.GEOPACKAGE,
                "null_counts_by_field": null_counts,
                "artifact_sha256": sha256,
                "artifact_byte_size": byte_size,
                "independent_reader_verified": False,
                "note": (
                    "Exact revision exported; run independent GIS reader check "
                    "for external verification."
                ),
            }
            artifact = DerivedArtifact(
                id=artifact_id,
                organization_id=context.organization_id,
                project_id=_req_uuid(context.project_id),
                job_id=job_id,
                source_id=source.id,
                layer_id=layer_id,
                source_content_revision=content_revision,
                source_schema_revision=schema_revision,
                output_format=output_format,
                output_crs=output_crs,
                filename=filename,
                content_type=content_type,
                byte_size=byte_size,
                sha256=sha256,
                storage_key=artifact_key,
                comparison_report=comparison_report,
                created_by_type=ActorType(context.actor.actor_type),
                created_by_id=_req_uuid(context.actor.actor_id),
                created_by_display=context.actor.display_name,
                created_at=done_at,
                expires_at=done_at + timedelta(hours=ARTIFACT_TTL_HOURS),
                state=ArtifactState.READY,
            )
            published = self.repository.publish_export_artifact(
                context=context,
                job_id=job_id,
                artifact=artifact,
                result_report=comparison_report,
            )
            self.repository.commit()
            return published
        except TransferError as exc:
            self.repository.rollback()
            if artifact_key is not None:
                self.store.delete_object(artifact_key)
            self.repository.update_job(
                context=context,
                job_id=job_id,
                status=JobStatus.FAILED,
                error_code=exc.code,
                error_message=exc.message[:500],
                completed_at=datetime.now(UTC),
            )
            self.repository.commit()
            raise
        except Exception as exc:
            self.repository.rollback()
            if artifact_key is not None:
                self.store.delete_object(artifact_key)
            self.repository.update_job(
                context=context,
                job_id=job_id,
                status=JobStatus.RECOVERABLE_FAILED,
                error_code="EXPORT_EXECUTION_INTERRUPTED",
                error_message="Export did not complete; retry with fresh authorization.",
                completed_at=None,
            )
            self.repository.commit()
            raise exc

    def list_jobs(
        self, *, context: AuthorizationContext, limit: int = 50
    ) -> tuple[TransferJob, ...]:
        self.repository.verify_project_authority(context=context, write=False)
        return self.repository.list_jobs(context=context, limit=limit)

    def get_job(self, *, context: AuthorizationContext, job_id: UUID) -> TransferJob:
        self.repository.verify_project_authority(context=context, write=False)
        job = self.repository.get_job(context=context, job_id=job_id)
        if job is None:
            raise TransferNotFoundError("Transfer job not found.")
        return job

    def cancel_job(self, *, context: AuthorizationContext, job_id: UUID) -> TransferJob:
        job = self.repository.get_job(context=context, job_id=job_id, lock=True)
        if job is None:
            raise TransferNotFoundError("Transfer job not found.")
        self.repository.verify_project_authority(
            context=context, write=(job.kind == JobKind.IMPORT)
        )
        if job.status in TERMINAL_JOB_STATUSES:
            return job
        if not can_transition(job.status, JobStatus.CANCELLED):
            raise TransferConflictError(
                "JOB_CANCEL_UNAVAILABLE", "Job cannot be cancelled in its current state."
            )
        updated = self.repository.update_job(
            context=context,
            job_id=job_id,
            status=JobStatus.CANCELLED,
            error_code="CANCELLED_BY_ACTOR",
            error_message="Cancelled before publication.",
            completed_at=datetime.now(UTC),
        )
        self.repository.commit()
        return updated

    def retry_job(self, *, context: AuthorizationContext, job_id: UUID) -> TransferJob:
        job = self.repository.get_job(context=context, job_id=job_id, lock=True)
        if job is None:
            raise TransferNotFoundError("Transfer job not found.")
        self.repository.verify_project_authority(
            context=context, write=(job.kind == JobKind.IMPORT)
        )
        if job.status != JobStatus.RECOVERABLE_FAILED:
            raise TransferConflictError(
                "JOB_NOT_RETRYABLE",
                "Only recoverable failed jobs may be retried.",
            )
        next_attempt = job.attempt_count + 1
        now = datetime.now(UTC)
        self.repository.update_job(
            context=context,
            job_id=job_id,
            status=JobStatus.ACTIVE,
            attempt_count=next_attempt,
            error_code=None,
            error_message=None,
        )
        self.repository.record_attempt(
            context=context,
            job_id=job_id,
            attempt_number=next_attempt,
            status="active",
            started_at=now,
        )
        self.repository.commit()
        if job.kind == JobKind.IMPORT:
            assert job.source_asset_id is not None
            asset = self.repository.get_source_asset(context=context, asset_id=job.source_asset_id)
            if asset is None:
                raise TransferNotFoundError("Source asset unavailable for retry.")
            payload = self.store.get_bytes(asset.storage_key, expected_sha256=asset.sha256)
            opts = job.options_json
            inspection = self._build_inspection(
                asset=asset,
                payload=payload,
                selected_member=opts.get("selected_member"),
                declared_source_crs=opts.get("declared_source_crs"),
                target_crs=opts.get("target_crs"),
                declared_encoding=opts.get("declared_encoding"),
            )
            return self._execute_import_attempt(
                context=context,
                job_id=job_id,
                asset=asset,
                payload=payload,
                inspection=inspection,
                source_name=str(opts["source_name"]),
                layer_name=str(opts["layer_name"]),
            )
        raise TransferConflictError(
            "EXPORT_RETRY_UNSUPPORTED",
            "Re-issue an authorized export preview and confirm for this revision.",
        )

    def get_artifact(self, *, context: AuthorizationContext, artifact_id: UUID) -> DerivedArtifact:
        self.repository.verify_project_authority(context=context, write=False)
        artifact = self.repository.get_artifact(context=context, artifact_id=artifact_id)
        if artifact is None:
            raise TransferNotFoundError("Derived artifact not found.")
        return artifact

    def download_artifact(
        self, *, context: AuthorizationContext, artifact_id: UUID
    ) -> tuple[DerivedArtifact, bytes]:
        self.repository.verify_project_authority(context=context, write=False)
        artifact = self.repository.get_artifact(context=context, artifact_id=artifact_id)
        if artifact is None:
            raise TransferNotFoundError("Derived artifact not found.")
        if artifact.state == ArtifactState.EXPIRED or datetime.now(UTC) >= artifact.expires_at:
            if artifact.state != ArtifactState.EXPIRED:
                self.repository.mark_artifact_state(
                    context=context, artifact_id=artifact_id, state=ArtifactState.EXPIRED
                )
                self.repository.commit()
            raise TransferArtifactUnavailableError(
                "ARTIFACT_EXPIRED",
                "Export artifact has expired; request a new authorized export.",
            )
        if artifact.state != ArtifactState.READY:
            raise TransferArtifactUnavailableError(
                "ARTIFACT_UNAVAILABLE",
                "Export artifact is unavailable; request a new authorized export.",
            )
        try:
            data = self.store.get_bytes(artifact.storage_key, expected_sha256=artifact.sha256)
        except TransferArtifactUnavailableError:
            self.repository.mark_artifact_state(
                context=context, artifact_id=artifact_id, state=ArtifactState.UNAVAILABLE
            )
            self.repository.commit()
            raise
        return artifact, data
