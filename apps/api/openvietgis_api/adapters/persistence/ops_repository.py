"""R015 Production Operations repository (readiness, metrics, non-destructive entitlements)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from openvietgis_api.adapters.persistence.rls import (
    bind_authenticated_actor,
    bind_authenticated_service_actor,
    require_member_context,
)
from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.ops.domain import OrganizationEntitlementRecord
from openvietgis_api.domains.platform_errors import PlatformValidationError


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

    def check_readiness(self, storage_dir: Path) -> dict[str, Any]:
        pg_ver = str(self._session.execute(text("SELECT version()")).scalar_one())
        postgis_ver = str(self._session.execute(text("SELECT PostGIS_Lib_Version()")).scalar_one())
        storage_dir.mkdir(parents=True, exist_ok=True)
        probe = storage_dir / ".ready_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {
            "status": "ready",
            "database": "ok",
            "postgresql_version": pg_ver.split(",")[0],
            "postgis_version": postgis_ver,
            "artifact_store": "ok",
            "checked_at": datetime.now(UTC).isoformat(),
        }

    def render_prometheus_metrics(self) -> str:
        db_ok = 1
        postgis_ok = 1
        try:
            self._session.execute(text("SELECT 1")).scalar_one()
            self._session.execute(text("SELECT PostGIS_Lib_Version()")).scalar_one()
        except Exception:
            db_ok = 0
            postgis_ok = 0
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
            "# HELP openvietgis_release_capabilities_enabled Total enabled release slices.",
            "# TYPE openvietgis_release_capabilities_enabled gauge",
            "openvietgis_release_capabilities_enabled 15",
            "",
        ]
        return "\n".join(lines)

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

    def get_entitlement(
        self, *, context: AuthorizationContext
    ) -> OrganizationEntitlementRecord | None:
        self._bind_org(context)
        assert context.organization_id is not None
        row = self._session.execute(
            text("""
                SELECT * FROM ops.organization_entitlements
                WHERE organization_id = :org
            """),
            {"org": context.organization_id},
        ).mappings().first()
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
        self._bind_org(context)
        assert context.organization_id is not None and context.actor.actor_id is not None
        if deployment_profile not in ("self_host_team", "cloud_saas", "enterprise_private"):
            raise PlatformValidationError("invalid deployment_profile")
        if plan_tier not in ("self_host_community", "team_standard", "enterprise"):
            raise PlatformValidationError("invalid plan_tier")
        if max_projects < 1 or max_storage_mb < 64:
            raise PlatformValidationError("invalid quota limits")

        now = datetime.now(UTC)
        row = self._session.execute(
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
        ).mappings().one()
        self._session.commit()
        return _ent_from_row(row)
