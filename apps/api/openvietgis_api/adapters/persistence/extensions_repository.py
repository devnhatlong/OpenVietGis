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
from openvietgis_api.adapters.persistence.scope_helper import prepare_project_scope
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.extensions.domain import (
    ExtensionDataRecord,
    ExtensionManifestRecord,
    ProjectActivationRecord,
    validate_manifest_contract,
    validate_record_against_schema,
)
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformNotFoundError,
)


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
        ui_contributions=list(row["ui_contributions"]),
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
        revision=int(row["revision"]),
        activated_by_actor_id=row["activated_by_actor_id"],
        activated_at=row["activated_at"],
        disabled_by_actor_id=row["disabled_by_actor_id"],
        disabled_at=row["disabled_at"],
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
        revision=int(row["revision"]),
        operation_id=row["operation_id"],
        created_by_actor_id=row["created_by_actor_id"],
        updated_by_actor_id=row["updated_by_actor_id"],
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
        ui_contributions: list[dict[str, Any]],
    ) -> ExtensionManifestRecord:
        self._bind_org(context)
        assert context.organization_id is not None and context.actor.actor_id is not None
        validate_manifest_contract(
            extension_key=extension_key,
            version=version,
            api_compatibility=api_compatibility,
            permissions=permissions,
            commands=commands,
            capabilities=capabilities,
            entity_schemas=entity_schemas,
            ui_contributions=ui_contributions,
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
                    entity_schemas, ui_contributions, enabled, registered_by_actor_id, created_at
                ) VALUES (
                    :id, :org, :key, :ver, :compat,
                    :dname, :desc, CAST(:perms AS jsonb), CAST(:cmds AS jsonb),
                    CAST(:caps AS jsonb), CAST(:schemas AS jsonb), CAST(:ui AS jsonb),
                    true, :actor, :now
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
                    "ui": json.dumps(ui_contributions),
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
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
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

        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO extensions.project_activations (
                    id, organization_id, project_id, manifest_id, extension_key,
                    status, revision, activated_by_actor_id, activated_at,
                    disabled_by_actor_id, disabled_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :mid, :key,
                    'active', 1, :actor, :now, NULL, NULL, :now
                )
                ON CONFLICT (organization_id, project_id, extension_key) DO UPDATE
                SET manifest_id = EXCLUDED.manifest_id,
                    status = 'active',
                    revision = extensions.project_activations.revision + 1,
                    disabled_by_actor_id = NULL,
                    disabled_at = NULL,
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
        self._session.commit()
        return _act_from_row(row)

    def disable_for_project(
        self, *, context: AuthorizationContext, extension_key: str
    ) -> ProjectActivationRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None
        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                UPDATE extensions.project_activations
                SET status = 'disabled',
                    revision = revision + 1,
                    disabled_by_actor_id = :actor,
                    disabled_at = :now,
                    updated_at = :now
                WHERE organization_id = :org AND project_id = :proj
                  AND extension_key = :key AND status = 'active'
                RETURNING *
            """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "key": extension_key,
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            row = (
                self._session.execute(
                    text("""
                    SELECT * FROM extensions.project_activations
                    WHERE organization_id = :org AND project_id = :proj
                      AND extension_key = :key
                """),
                    {
                        "org": context.organization_id,
                        "proj": context.project_id,
                        "key": extension_key,
                    },
                )
                .mappings()
                .first()
            )
        if row is None:
            raise PlatformNotFoundError("project extension activation not found")
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

    def _active_schema(
        self, *, context: AuthorizationContext, extension_key: str
    ) -> dict[str, dict[str, Any]]:
        assert context.organization_id is not None and context.project_id is not None
        act = (
            self._session.execute(
                text("""
                SELECT m.entity_schemas
                FROM extensions.project_activations a
                JOIN extensions.manifests m ON m.id = a.manifest_id
                WHERE a.organization_id = :org AND a.project_id = :proj
                  AND a.extension_key = :key AND a.status = 'active'
                  AND m.enabled = true
            """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "key": extension_key,
                },
            )
            .mappings()
            .first()
        )
        if act is None:
            raise PlatformNotFoundError(
                f"extension {extension_key!r} is not active in this project"
            )
        return dict(act["entity_schemas"])

    def create_record(
        self,
        *,
        context: AuthorizationContext,
        extension_key: str,
        entity_name: str,
        payload: dict[str, Any],
        linked_layer_id: UUID | None = None,
        linked_feature_id: str | None = None,
        operation_id: UUID | None = None,
    ) -> ExtensionDataRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None

        schemas = self._active_schema(context=context, extension_key=extension_key)
        cleaned = validate_record_against_schema(
            entity_name=entity_name,
            payload=payload,
            entity_schemas=schemas,
        )
        if operation_id is not None:
            existing = (
                self._session.execute(
                    text("""
                    SELECT * FROM extensions.records
                    WHERE organization_id = :org AND project_id = :proj
                      AND extension_key = :key AND operation_id = :op
                """),
                    {
                        "org": context.organization_id,
                        "proj": context.project_id,
                        "key": extension_key,
                        "op": operation_id,
                    },
                )
                .mappings()
                .first()
            )
            if existing is not None:
                return _rec_from_row(existing)

        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO extensions.records (
                    id, organization_id, project_id, extension_key, entity_name,
                    payload, linked_layer_id, linked_feature_id, revision, operation_id,
                    created_by_actor_id, updated_by_actor_id, created_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :key, :ename,
                    CAST(:pay AS jsonb), :lid, :fid, 1, :op,
                    :actor, :actor, :now, :now
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
                    "op": operation_id,
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        self._session.commit()
        return _rec_from_row(row)

    def update_record(
        self,
        *,
        context: AuthorizationContext,
        extension_key: str,
        record_id: UUID,
        expected_revision: int,
        payload: dict[str, Any],
        operation_id: UUID | None = None,
    ) -> ExtensionDataRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None

        current = (
            self._session.execute(
                text("""
                SELECT * FROM extensions.records
                WHERE organization_id = :org AND project_id = :proj
                  AND extension_key = :key AND id = :rid
            """),
                {
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "key": extension_key,
                    "rid": record_id,
                },
            )
            .mappings()
            .first()
        )
        if current is None:
            raise PlatformNotFoundError("extension record not found")
        schemas = self._active_schema(context=context, extension_key=extension_key)
        cleaned = validate_record_against_schema(
            entity_name=str(current["entity_name"]),
            payload=payload,
            entity_schemas=schemas,
        )
        if operation_id is not None:
            prior = (
                self._session.execute(
                    text("""
                    SELECT * FROM extensions.records
                    WHERE organization_id = :org AND project_id = :proj
                      AND extension_key = :key AND operation_id = :op
                """),
                    {
                        "org": context.organization_id,
                        "proj": context.project_id,
                        "key": extension_key,
                        "op": operation_id,
                    },
                )
                .mappings()
                .first()
            )
            if prior is not None:
                if prior["id"] != record_id:
                    raise PlatformConflictError(
                        "operation_id already used by another record",
                        code="OPERATION_REPLAY_CONFLICT",
                    )
                return _rec_from_row(prior)

        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                UPDATE extensions.records
                SET payload = CAST(:pay AS jsonb),
                    revision = revision + 1,
                    operation_id = :op,
                    updated_by_actor_id = :actor,
                    updated_at = :now
                WHERE organization_id = :org AND project_id = :proj
                  AND extension_key = :key AND id = :rid
                  AND revision = :expected
                RETURNING *
            """),
                {
                    "pay": json.dumps(cleaned),
                    "op": operation_id,
                    "actor": context.actor.actor_id,
                    "now": now,
                    "org": context.organization_id,
                    "proj": context.project_id,
                    "key": extension_key,
                    "rid": record_id,
                    "expected": expected_revision,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            self._session.rollback()
            raise PlatformConflictError(
                "extension record revision is stale",
                code="STALE_EXTENSION_RECORD",
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
        self._active_schema(context=context, extension_key=extension_key)
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
