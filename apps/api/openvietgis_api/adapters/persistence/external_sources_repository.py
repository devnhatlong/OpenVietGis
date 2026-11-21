"""R010 RLS-enforced repository for external source allowlist & read-only connections."""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
from openvietgis_api.domains.external_sources.domain import (
    AllowlistedHostRecord,
    ExternalConnectionRecord,
    ExternalProtocol,
    default_external_capabilities,
    validate_endpoint_against_allowlist,
    validate_safe_hostname,
)
from openvietgis_api.domains.platform_errors import (
    PlatformConflictError,
    PlatformNotFoundError,
    PlatformValidationError,
)


def _allowlist_from_row(row: RowMapping) -> AllowlistedHostRecord:
    return AllowlistedHostRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        hostname=str(row["hostname"]),
        allowed_schemes=tuple(str(s) for s in row["allowed_schemes"]),
        allowed_ports=tuple(int(p) for p in row["allowed_ports"]),
        secret_ref_name=str(row["secret_ref_name"]) if row["secret_ref_name"] else None,
        enabled=bool(row["enabled"]),
        created_by_actor_id=row["created_by_actor_id"],
        created_at=row["created_at"],
    )


def _conn_from_row(row: RowMapping) -> ExternalConnectionRecord:
    return ExternalConnectionRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        project_id=row["project_id"],
        allowlist_id=row["allowlist_id"],
        name=str(row["name"]),
        protocol=ExternalProtocol(str(row["protocol"])),
        endpoint_url=str(row["endpoint_url"]),
        layer_identifier=str(row["layer_identifier"]),
        attribution=str(row["attribution"]),
        license_text=str(row["license_text"]),
        crs_codes=tuple(int(c) for c in row["crs_codes"]),
        # Old records may contain optimistic capability flags. Enforce the
        # current metadata-only policy on every read, not only at creation.
        capabilities=default_external_capabilities(ExternalProtocol(str(row["protocol"]))),
        read_only=bool(row["read_only"]),
        cache_generation=int(row["cache_generation"]),
        lifecycle=str(row["lifecycle"]),
        created_by_actor_id=row["created_by_actor_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqlExternalSourcesRepository:
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

    def register_allowlisted_host(
        self,
        *,
        context: AuthorizationContext,
        hostname: str,
        allowed_schemes: list[str] | None = None,
        allowed_ports: list[int] | None = None,
        secret_ref_name: str | None = None,
    ) -> AllowlistedHostRecord:
        self._bind_org(context)
        assert context.organization_id is not None and context.actor.actor_id is not None
        clean_host = validate_safe_hostname(hostname)
        schemes = [s.lower() for s in (allowed_schemes or ["https"])]
        if any(s not in ("http", "https") for s in schemes):
            raise PlatformValidationError("allowed_schemes must be http or https")
        ports = [int(p) for p in (allowed_ports or [443])]
        if any(p < 1 or p > 65535 for p in ports):
            raise PlatformValidationError("allowed_ports must be 1..65535")

        existing = self._session.execute(
            text("""
                SELECT id FROM external_sources.allowlisted_hosts
                WHERE organization_id = :org AND hostname = :host
            """),
            {"org": context.organization_id, "host": clean_host},
        ).first()
        if existing is not None:
            raise PlatformConflictError(
                f"host {clean_host!r} already allowlisted", code="HOST_EXISTS"
            )

        now = datetime.now(UTC)
        row = self._session.execute(
            text("""
                INSERT INTO external_sources.allowlisted_hosts (
                    id, organization_id, hostname, allowed_schemes, allowed_ports,
                    secret_ref_name, enabled, created_by_actor_id, created_at
                ) VALUES (
                    :id, :org, :host, CAST(:schemes AS jsonb), CAST(:ports AS jsonb),
                    :sref, true, :actor, :now
                )
                RETURNING *
            """),
            {
                "id": uuid4(),
                "org": context.organization_id,
                "host": clean_host,
                "schemes": json.dumps(schemes),
                "ports": json.dumps(ports),
                "sref": secret_ref_name.strip()[:128] if secret_ref_name else None,
                "actor": context.actor.actor_id,
                "now": now,
            },
        ).mappings().one()
        self._session.commit()
        return _allowlist_from_row(row)

    def list_allowlisted_hosts(
        self, *, context: AuthorizationContext
    ) -> list[AllowlistedHostRecord]:
        self._bind_org(context)
        assert context.organization_id is not None
        rows = self._session.execute(
            text("""
                SELECT * FROM external_sources.allowlisted_hosts
                WHERE organization_id = :org ORDER BY hostname ASC
            """),
            {"org": context.organization_id},
        ).mappings().all()
        return [_allowlist_from_row(r) for r in rows]

    def create_connection(
        self,
        *,
        context: AuthorizationContext,
        allowlist_id: UUID,
        name: str,
        protocol: ExternalProtocol,
        endpoint_url: str,
        layer_identifier: str,
        attribution: str,
        license_text: str,
        crs_codes: list[int],
    ) -> ExternalConnectionRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        assert context.actor.actor_id is not None

        arow = self._session.execute(
            text("""
                SELECT * FROM external_sources.allowlisted_hosts
                WHERE organization_id = :org AND id = :aid
            """),
            {"org": context.organization_id, "aid": allowlist_id},
        ).mappings().first()
        if arow is None:
            raise PlatformNotFoundError("allowlisted host not found")
        allowlist = _allowlist_from_row(arow)

        clean_url, _, _ = validate_endpoint_against_allowlist(endpoint_url, allowlist)
        if not crs_codes or any(c not in (4326, 3857, 4756, 5899) for c in crs_codes):
            raise PlatformValidationError(
                "crs_codes must contain supported EPSG codes (4326, 3857, 4756, 5899)",
                code="UNSUPPORTED_CRS",
            )
        caps = default_external_capabilities(protocol)
        now = datetime.now(UTC)
        row = self._session.execute(
            text("""
                INSERT INTO external_sources.connections (
                    id, organization_id, project_id, allowlist_id, name, protocol,
                    endpoint_url, layer_identifier, attribution, license_text,
                    crs_codes, capabilities, read_only, cache_generation, lifecycle,
                    created_by_actor_id, created_at, updated_at
                ) VALUES (
                    :id, :org, :proj, :aid, :name, :proto,
                    :url, :lid, :attr, :lic,
                    CAST(:crs AS jsonb), CAST(:caps AS jsonb), true, 1, 'active',
                    :actor, :now, :now
                )
                RETURNING *
            """),
            {
                "id": uuid4(),
                "org": context.organization_id,
                "proj": context.project_id,
                "aid": allowlist_id,
                "name": name.strip()[:200] or "External Layer",
                "proto": protocol.value,
                "url": clean_url,
                "lid": layer_identifier.strip()[:200] or "default",
                "attr": attribution.strip()[:300] or "External Provider",
                "lic": license_text.strip()[:300] or "Provider License Terms Apply",
                "crs": json.dumps(crs_codes),
                "caps": json.dumps(caps),
                "actor": context.actor.actor_id,
                "now": now,
            },
        ).mappings().one()
        self._session.commit()
        return _conn_from_row(row)

    def list_connections(self, *, context: AuthorizationContext) -> list[ExternalConnectionRecord]:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_READ)
        assert context.organization_id is not None and context.project_id is not None
        rows = self._session.execute(
            text("""
                SELECT * FROM external_sources.connections
                WHERE organization_id = :org AND project_id = :proj
                ORDER BY created_at DESC
            """),
            {"org": context.organization_id, "proj": context.project_id},
        ).mappings().all()
        return [_conn_from_row(r) for r in rows]

    def invalidate_cache(
        self, *, context: AuthorizationContext, connection_id: UUID
    ) -> ExternalConnectionRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        now = datetime.now(UTC)
        row = self._session.execute(
            text("""
                UPDATE external_sources.connections
                SET cache_generation = cache_generation + 1, updated_at = :now
                WHERE organization_id = :org AND project_id = :proj AND id = :cid
                RETURNING *
            """),
            {
                "org": context.organization_id,
                "proj": context.project_id,
                "cid": connection_id,
                "now": now,
            },
        ).mappings().first()
        if row is None:
            raise PlatformNotFoundError("external connection not found")
        self._session.commit()
        return _conn_from_row(row)

    def revoke_connection(
        self, *, context: AuthorizationContext, connection_id: UUID
    ) -> ExternalConnectionRecord:
        prepare_project_scope(self._session, context, permission=Permission.PROJECT_EDIT)
        assert context.organization_id is not None and context.project_id is not None
        now = datetime.now(UTC)
        row = self._session.execute(
            text("""
                UPDATE external_sources.connections
                SET lifecycle = 'revoked', cache_generation = cache_generation + 1,
                    updated_at = :now
                WHERE organization_id = :org AND project_id = :proj AND id = :cid
                RETURNING *
            """),
            {
                "org": context.organization_id,
                "proj": context.project_id,
                "cid": connection_id,
                "now": now,
            },
        ).mappings().first()
        if row is None:
            raise PlatformNotFoundError("external connection not found")
        self._session.commit()
        return _conn_from_row(row)
