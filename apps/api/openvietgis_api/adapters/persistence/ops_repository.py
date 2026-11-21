"""R015 Production Operations repository (readiness, metrics, non-destructive entitlements)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.audit_repository import SqlAuditRepository
from openvietgis_api.adapters.persistence.authorization_repository import (
    SqlEffectivePermissionProvider,
)
from openvietgis_api.adapters.persistence.rls import (
    bind_authenticated_actor,
    bind_authenticated_service_actor,
    require_member_context,
)
from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.authorization.service import AuthorizationService
from openvietgis_api.domains.ops.domain import (
    RELEASE_IDS,
    OrganizationEntitlementRecord,
    release_inventory,
)
from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.tenancy.domain import ActorType


def _ent_from_row(row: RowMapping) -> OrganizationEntitlementRecord:
    return OrganizationEntitlementRecord(
        organization_id=row["organization_id"],
        deployment_profile=str(row["deployment_profile"]),
        plan_tier=str(row["plan_tier"]),
        max_projects=int(row["max_projects"]),
        max_storage_mb=int(row["max_storage_mb"]),
        features_enabled=[str(x) for x in row["features_enabled"]],
        updated_by_actor_id=row["updated_by_actor_id"],
        updated_at=row["updated_at"],
    )


class SqlOpsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _dependency_status(self) -> dict[str, Any]:
        database: dict[str, Any] = {
            "database": "unavailable",
            "postgis": "unavailable",
            "postgresql_version": None,
            "postgis_version": None,
        }
        try:
            pg_ver = str(self._session.execute(text("SELECT version()")).scalar_one())
            database.update(database="ok", postgresql_version=pg_ver.split(",")[0])
            postgis_ver = str(
                self._session.execute(text("SELECT PostGIS_Lib_Version()")).scalar_one()
            )
            database.update(postgis="ok", postgis_version=postgis_ver)
        except (SQLAlchemyError, RuntimeError):
            # Never expose database connection failures, SQL or secrets.
            self._session.rollback()
        return database

    def check_readiness(self, storage_dir: Path) -> dict[str, Any]:
        database = self._dependency_status()
        artifact_store = "unavailable"
        try:
            # The configured storage should already exist. Do not silently make
            # a replacement directory if the configured path is missing.
            # A unique inode avoids clobbering another probe or a named asset.
            if storage_dir.is_dir() and not storage_dir.is_symlink():
                with TemporaryFile(mode="w+b", dir=storage_dir) as probe:
                    probe.write(b"openvietgis-readiness")
                    probe.flush()
                    probe.seek(0)
                    if probe.read() == b"openvietgis-readiness":
                        artifact_store = "ok"
        except OSError:
            pass
        ready = (
            database["database"] == "ok" and database["postgis"] == "ok" and artifact_store == "ok"
        )
        return {
            "status": "ready" if ready else "not_ready",
            **database,
            "artifact_store": artifact_store,
            "scope": "dependency_probe_only",
            "production_ready": False,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    def render_prometheus_metrics(self) -> str:
        database = self._dependency_status()
        db_ok = int(database["database"] == "ok")
        postgis_ok = int(database["postgis"] == "ok")
        inventory = release_inventory()
        lines = [
            "# HELP openvietgis_up Application liveness indicator.",
            "# TYPE openvietgis_up gauge",
            "openvietgis_up 1",
            "# HELP openvietgis_database_ready PostgreSQL connectivity indicator.",
            "# TYPE openvietgis_database_ready gauge",
            f"openvietgis_database_ready {db_ok}",
            "# HELP openvietgis_postgis_ready PostGIS extension availability.",
            "# TYPE openvietgis_postgis_ready gauge",
            f"openvietgis_postgis_ready {postgis_ok}",
            "# HELP openvietgis_release_capabilities_enabled Total certified release slices.",
            "# TYPE openvietgis_release_capabilities_enabled gauge",
            f"openvietgis_release_capabilities_enabled {inventory['accepted_release_count']}",
            "# HELP openvietgis_release_inventory_count Registered roadmap groups.",
            "# TYPE openvietgis_release_inventory_count gauge",
            f"openvietgis_release_inventory_count {inventory['total_releases']}",
            "# HELP openvietgis_release_gate_ready Accepted deployment profile.",
            "# TYPE openvietgis_release_gate_ready gauge",
            f"openvietgis_release_gate_ready {int(inventory['production_ready'])}",
            "",
        ]
        return "\n".join(lines)

    def _bind_org(self, context: AuthorizationContext, permission: Permission) -> None:
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
        AuthorizationService(SqlEffectivePermissionProvider(self._session)).require(
            context, permission
        )

    def get_entitlement(
        self, *, context: AuthorizationContext
    ) -> OrganizationEntitlementRecord | None:
        self._bind_org(context, Permission.ORGANIZATION_READ)
        assert context.organization_id is not None
        row = (
            self._session.execute(
                text("""
                SELECT * FROM ops.organization_entitlements
                WHERE organization_id = :org
            """),
                {"org": context.organization_id},
            )
            .mappings()
            .first()
        )
        return _ent_from_row(row) if row is not None else None

    def upsert_entitlement(
        self,
        *,
        context: AuthorizationContext,
        deployment_profile: str,
        plan_tier: str,
        max_projects: int,
        max_storage_mb: int,
        features_enabled: list[str],
    ) -> OrganizationEntitlementRecord:
        self._bind_org(context, Permission.ORGANIZATION_MANAGE_SETTINGS)
        assert context.organization_id is not None and context.actor.actor_id is not None
        if deployment_profile not in ("self_host_team", "cloud_saas", "enterprise_private"):
            raise PlatformValidationError("invalid deployment_profile")
        if plan_tier not in ("self_host_community", "team_standard", "enterprise"):
            raise PlatformValidationError("invalid plan_tier")
        if not 1 <= max_projects <= 2_147_483_647 or not 64 <= max_storage_mb <= 2_147_483_647:
            raise PlatformValidationError("invalid quota limits")
        if len(set(features_enabled)) != len(features_enabled):
            raise PlatformValidationError("duplicate requested feature IDs")
        if not set(features_enabled) <= RELEASE_IDS:
            raise PlatformValidationError("unknown requested feature IDs")

        now = datetime.now(UTC)
        row = (
            self._session.execute(
                text("""
                INSERT INTO ops.organization_entitlements (
                    organization_id, deployment_profile, plan_tier,
                    max_projects, max_storage_mb, features_enabled,
                    updated_by_actor_id, updated_at
                ) VALUES (
                    :org, :prof, :tier, :mproj, :mstor, CAST(:feats AS jsonb), :actor, :now
                )
                ON CONFLICT (organization_id) DO UPDATE
                SET deployment_profile = EXCLUDED.deployment_profile,
                    plan_tier = EXCLUDED.plan_tier,
                    max_projects = EXCLUDED.max_projects,
                    max_storage_mb = EXCLUDED.max_storage_mb,
                    features_enabled = EXCLUDED.features_enabled,
                    updated_by_actor_id = EXCLUDED.updated_by_actor_id,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
            """),
                {
                    "org": context.organization_id,
                    "prof": deployment_profile,
                    "tier": plan_tier,
                    "mproj": max_projects,
                    "mstor": max_storage_mb,
                    "feats": json.dumps(features_enabled),
                    "actor": context.actor.actor_id,
                    "now": now,
                },
            )
            .mappings()
            .one()
        )
        SqlAuditRepository(self._session).append(
            AuditEvent(
                id=uuid4(),
                organization_id=context.organization_id,
                actor_type=ActorType(context.actor.actor_type),
                actor_id=context.actor.actor_id,
                actor_display_snapshot=context.actor.display_name,
                action="ops.entitlement.configure",
                resource_type="organization_entitlement",
                resource_id=context.organization_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "deployment_profile": deployment_profile,
                    "plan_tier": plan_tier,
                    "max_projects": max_projects,
                    "max_storage_mb": max_storage_mb,
                    "requested_features": features_enabled,
                    "enforcement": "metadata_only",
                },
                created_at=now,
            )
        )
        self._session.commit()
        return _ent_from_row(row)
