"""R014 RLS-enforced repository for generic extension manifests, activations & records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import (
    bind_authenticated_actor,
    bind_authenticated_service_actor,
    require_member_context,
)
from openvietgis_api.adapters.persistence.scope_helper import (
    append_project_audit,
    prepare_project_scope,
)
from openvietgis_api.adapters.persistence.tenancy_repository import SqlTenancyRepository
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.roles import ORGANIZATION_ROLE_PERMISSIONS
from openvietgis_api.domains.extensions.domain import (
    ExtensionDataRecord,
    ExtensionManifestRecord,
    ProjectActivationRecord,
    validate_manifest_contract,
    validate_record_against_schema,
)
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformForbiddenError,
    PlatformNotFoundError,
    PlatformValidationError,
)
from openvietgis_api.domains.tenancy.domain import MembershipStatus, OrganizationStatus


def _manifest_from_row(row: RowMapping) -> ExtensionManifestRecord:
    return ExtensionManifestRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        extension_key=str(row["extension_key"]),
        version=str(row["version"]),
        api_compatibility=str(row["api_compatibility"]),
        display_name=str(row["display_name"]),
        description=str(row["description"]),
        permissions=[str(x) for x in row["permissions"]],
        commands=list(row["commands"]),
        capabilities=[str(x) for x in row["capabilities"]],
        entity_schemas=dict(row["entity_schemas"]),
        enabled=bool(row["enabled"]),
        registered_by_actor_id=row["registered_by_actor_id"],
        created_at=row["created_at"],
    )


def _act_from_row(row: RowMapping) -> ProjectActivationRecord:
    return ProjectActivationRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        manifest_id=row["manifest_id"],
        extension_key=str(row["extension_key"]),
        status=str(row["status"]),
        activated_by_actor_id=row["activated_by_actor_id"],
        activated_at=row["activated_at"],
        updated_at=row["updated_at"],
    )


def _rec_from_row(row: RowMapping) -> ExtensionDataRecord:
    return ExtensionDataRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        extension_key=str(row["extension_key"]),
        entity_name=str(row["entity_name"]),
        payload=dict(row["payload"]),
        linked_layer_id=row["linked_layer_id"],
        linked_feature_id=str(row["linked_feature_id"]) if row["linked_feature_id"] else None,
        created_by_actor_id=row["created_by_actor_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlExtensionsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _bind_org(self, context: AuthorizationContext) -> None:
        assert context.organization_id is not None
        if context.actor.actor_type == "human":
            bind_authenticated_actor(self._session, context.actor)
        elif context.actor.actor_type == "service_principal" and context.credential_id is not None:
            bind_authenticated_service_actor(
                self._session,
                context.actor,
                organization_id=context.organization_id,
                credential_id=context.credential_id,
            )
        require_member_context(self._session, context, context.organization_id)

    def register_manifest(
        self,
        *,
        context: AuthorizationContext,
        extension_key: str,
        version: str,
        api_compatibility: str,
        display_name: str,
        description: str,
        permissions: list[str],
        commands: list[dict[str, Any]],
        capabilities: list[str],
        entity_schemas: dict[str, dict[str, Any]],
    ) -> ExtensionManifestRecord:
        self._bind_org(context)
        assert context.organization_id is not None and context.actor.actor_id is not None
        # Tenant registration is metadata-only, not installation-wide approval.
        # Only a current human tenant administrator may add a manifest.
        tenant = SqlTenancyRepository(self._session)
        org = tenant.get_organization(context.organization_id, context=context, for_update=True)
        if org is None or org.status != OrganizationStatus.ACTIVE:
            raise PlatformNotFoundError("organization not found")
        if context.actor.actor_type != "human":
            raise PlatformForbiddenError("manifest registration requires human administrator")
        member = tenant.get_membership_for_user(
            context=context,
            organization_id=context.organization_id,
            user_id=context.actor.actor_id,
            for_update=True,
        )
        if (
            member is None
            or member.status != MembershipStatus.ACTIVE
            or Permission.ORGANIZATION_MANAGE_SETTINGS
            not in ORGANIZATION_ROLE_PERMISSIONS[member.role]
        ):
            raise PlatformForbiddenError(
                "manifest registration requires organization settings authority"
            )
        validate_manifest_contract(
            extension_key=extension_key,
            version=version,
            api_compatibility=api_compatibility,
            permissions=permissions,
            entity_schemas=entity_schemas,
        )
        exists = self._session.execute(
            text("""
                SELECT id FROM extensions.manifests
                WHERE organization_id = :org AND extension_key = :key AND version = :ver
            """),
            {"org": context.organization_id, "key": extension_key, "ver": version},
        ).first()
        if exists is not None:
            raise PlatformConflictError(
                f"manifest {extension_key}@{version} already registered",
                code="MANIFEST_EXISTS",
            )
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO extensions.manifests (
                    id, organization_id, extension_key, version, api_compatibility,
                    display_name, description, permissions, commands, capabilities,
                    entity_schemas, enabled, registered_by_actor_id, created_at
                ) VALUES (
                    :id, :org, :key, :ver, :compat,
                    :dname, :desc, CAST(:perms AS jsonb), CAST(:cmds AS jsonb),
                    CAST(:caps AS jsonb), CAST(:schemas AS jsonb), true, :actor, :now
                )
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": context.organization_id,
                    "key": extension_key,
                    "ver": version,
                    "compat": api_compatibility,
                    "dname": display_name.strip()[:200],
                    "desc": description.strip()[:500],
                    "perms": json.dumps(permissions),
                    "cmds": json.dumps(commands),
                    "caps": json.dumps(capabilities),
                    "schemas": json.dumps(entity_schemas),
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._session.commit()
        return _manifest_from_row(row)

    def list_manifests(self, *, context: AuthorizationContext) -> list[ExtensionManifestRecord]:
        self._bind_org(context)
        assert context.organization_id is not None
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM extensions.manifests
                WHERE organization_id = :org ORDER BY extension_key ASC, created_at DESC
            """),
                {"org": context.organization_id},
            )
            .mappings()
            .all()
        )
        return [_manifest_from_row(r) for r in rows]

    def activate_for_project(
        self, *, context: AuthorizationContext, manifest_id: UUID
    ) -> ProjectActivationRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_MANAGE)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None

        mrow = (
            self._session.execute(
                text("""
                SELECT id, extension_key FROM extensions.manifests
                WHERE organization_id = :org AND id = :mid AND enabled = true
            """),
                {"org": context.organization_id, "mid": manifest_id},
            )
            .mappings()
            .first()
        )
        if mrow is None:
            raise PlatformNotFoundError("extension manifest not found")

        existing = self._session.execute(
            text("""
                SELECT manifest_id FROM extensions.project_activations
                WHERE organization_id = :org AND project_id = :proj AND extension_key = :key
                FOR UPDATE
            """),
            {
                "org": context.organization_id,
                "proj": context.project_id,
                "key": mrow["extension_key"],
            },
        ).scalar_one_or_none()
        if existing is not None and existing != manifest_id:
            raise PlatformConflictError(
                "version transitions require a verified migration; implicit replacement is blocked",
                code="EXTENSION_VERSION_TRANSITION_REQUIRED",
            )
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO extensions.project_activations (
                    id, organization_id, project_id, manifest_id, extension_key,
                    status, activated_by_actor_id, activated_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :mid, :key,
                    'active', :actor, :now, :now
                )
                ON CONFLICT (organization_id, project_id, extension_key) DO UPDATE
                SET status = 'active',
                    activated_by_actor_id = EXCLUDED.activated_by_actor_id,
                    activated_at = EXCLUDED.activated_at,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "mid": manifest_id,
                    "key": str(mrow["extension_key"]),
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        append_project_audit(
            self._session,
            context,
            audit_id=uuid4(),
            action="extension.activate",
            resource_type="extension_activation",
            resource_id=row["id"],
            metadata={"manifest_id": str(manifest_id), "extension_key": row["extension_key"]},
            created_at=now,
        )
        self._session.commit()
        return _act_from_row(row)

    def deactivate_for_project(
        self, *, context: AuthorizationContext, activation_id: UUID
    ) -> ProjectActivationRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_MANAGE)
        assert context.organization_id is not None and context.project_id is not None
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                UPDATE extensions.project_activations
                SET status = 'disabled', updated_at = :now
                WHERE id = :id AND organization_id = :org AND project_id = :proj
                RETURNING *
            """),
                {
                    "id": activation_id,
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "now": now,
                },
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise PlatformNotFoundError("extension activation not found")
        append_project_audit(
            self._session,
            context,
            audit_id=uuid4(),
            action="extension.deactivate",
            resource_type="extension_activation",
            resource_id=activation_id,
            metadata={
                "manifest_id": str(row["manifest_id"]),
                "extension_key": row["extension_key"],
            },
            created_at=now,
        )
        self._session.commit()
        return _act_from_row(row)

    def list_activations(self, *, context: AuthorizationContext) -> list[ProjectActivationRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = (
            self._session.execute(
                text("""
                SELECT * FROM extensions.project_activations
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY extension_key ASC
            """),
                {"org": context.organization_id, "proj": context.project_id},
            )
            .mappings()
            .all()
        )
        return [_act_from_row(r) for r in rows]

    def create_record(
        self,
        *,
        context: AuthorizationContext,
        extension_key: str,
        entity_name: str,
        payload: dict[str, Any],
        linked_layer_id: UUID | None = None,
        linked_feature_id: str | None = None,
    ) -> ExtensionDataRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None

        act = (
            self._session.execute(
                text("""
                SELECT m.entity_schemas
                FROM extensions.project_activations a
                JOIN extensions.manifests m ON m.id = a.manifest_id
                WHERE a.organization_id = :org AND a.project_id = :proj
                  AND a.extension_key = :key AND a.status = 'active'
                  AND m.organization_id = :org AND m.enabled AND m.api_compatibility = '1.x'
            """),
                {"org": context.organization_id, "proj": context.project_id, "key": extension_key},
            )
            .mappings()
            .first()
        )
        if act is None:
            raise PlatformNotFoundError(
                f"extension {extension_key!r} is not active in this project"
            )
        cleaned = validate_record_against_schema(
            entity_name=entity_name,
            payload=payload,
            entity_schemas=dict(act["entity_schemas"]),
        )
        if linked_feature_id is not None and linked_layer_id is None:
            raise PlatformValidationError("linked feature requires a layer")
        if linked_layer_id is not None:
            # The current project scope and project mutation lock are already bound.
            # Resolve links only inside the authorized project.
            linked = self._session.execute(
                text("""
                    SELECT l.source_id FROM spatial.layers l
                    JOIN spatial.data_sources s ON s.id = l.source_id
                     AND s.organization_id = l.organization_id AND s.project_id = l.project_id
                    WHERE l.organization_id = :org AND l.project_id = :proj
                      AND l.id = :layer AND l.lifecycle = 'active' AND s.lifecycle = 'active'
                """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "layer": linked_layer_id,
                },
            ).scalar_one_or_none()
            if linked is None:
                raise PlatformNotFoundError("linked layer not found")
            if linked_feature_id is not None:
                found = self._session.execute(
                    text("""
                        SELECT feature_id FROM spatial.reference_features
                        WHERE organization_id = :org AND project_id = :proj
                        AND source_id = :src AND feature_id = :fid
                    """),
                    {
                        "org": context.organization_id,
                        "proj": context.project_id,
                        "src": linked,
                        "fid": linked_feature_id,
                    },
                ).scalar_one_or_none()
                if found is None:
                    raise PlatformNotFoundError("linked feature not found")
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO extensions.records (
                    id, organization_id, project_id, extension_key, entity_name,
                    payload, linked_layer_id, linked_feature_id,
                    created_by_actor_id, created_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :key, :ename,
                    CAST(:pay AS jsonb), :lid, :fid, :actor, :now, :now
                )
                RETURNING *
            """),
                {
                    "id": uuid4(),
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "key": extension_key,
                    "ename": entity_name,
                    "pay": json.dumps(cleaned),
                    "lid": linked_layer_id,
                    "fid": linked_feature_id,
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._session.commit()
        return _rec_from_row(row)

    def list_records(
        self,
        *,
        context: AuthorizationContext,
        extension_key: str,
        entity_name: str | None = None,
    ) -> list[ExtensionDataRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        sql = """
            SELECT * FROM extensions.records
            WHERE organization_id = :org AND project_id = :proj AND extension_key = :key
        """
        params: dict[str, Any] = {
            "org": context.organization_id,
            "proj": context.project_id,
            "key": extension_key,
        }
        if entity_name:
            sql += " AND entity_name = :ename"
            params["ename"] = entity_name
        sql += " ORDER BY created_at DESC LIMIT 200"
        rows = self._session.execute(text(sql), params).mappings().all()
        return [_rec_from_row(r) for r in rows]
