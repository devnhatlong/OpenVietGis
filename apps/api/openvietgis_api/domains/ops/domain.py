"""R015 Production Operations & Release Capabilities domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

RELEASE_CAPABILITIES: list[dict[str, Any]] = [
    {"id": "R001", "name": "Platform Foundation", "enabled": True, "milestone": "M0"},
    {"id": "R002", "name": "Identity, Organization & Tenancy", "enabled": True, "milestone": "M1"},
    {"id": "R003", "name": "Spatial Catalog & CRS (VN-2000)", "enabled": True, "milestone": "M1"},
    {"id": "R004", "name": "Map Workspace", "enabled": True, "milestone": "M1"},
    {"id": "R005", "name": "Import & Export + Durable Jobs", "enabled": True, "milestone": "M1"},
    {"id": "R006", "name": "Editing & Change History", "enabled": True, "milestone": "M2"},
    {"id": "R007", "name": "Attribute & Spatial Query", "enabled": True, "milestone": "M2"},
    {
        "id": "R008",
        "name": "Processing & Jobs (Buffer/Clip/Dissolve)",
        "enabled": True,
        "milestone": "M2",
    },
    {
        "id": "R009",
        "name": "Cartography & Print Output (PNG/PDF)",
        "enabled": True,
        "milestone": "M2",
    },
    {
        "id": "R010",
        "name": "External Sources (SSRF-safe Allowlist)",
        "enabled": True,
        "milestone": "M3",
    },
    {"id": "R011", "name": "Team Collaboration & Reviews", "enabled": True, "milestone": "M3"},
    {"id": "R012", "name": "CAD 2D DXF & Precision COGO", "enabled": True, "milestone": "M3"},
    {"id": "R013", "name": "Field & Offline GeoPackage + Sync", "enabled": True, "milestone": "M3"},
    {"id": "R014", "name": "Internal Extension Platform", "enabled": True, "milestone": "M3"},
    {
        "id": "R015",
        "name": "Production Operations & Self-Host Profile",
        "enabled": True,
        "milestone": "M3",
    },
]


@dataclass(frozen=True, slots=True)
class OrganizationEntitlementRecord:
    organization_id: UUID
    deployment_profile: str
    plan_tier: str
    max_projects: int
    max_storage_mb: int
    features_enabled: list[str]
    updated_by_actor_id: UUID
    updated_at: datetime
