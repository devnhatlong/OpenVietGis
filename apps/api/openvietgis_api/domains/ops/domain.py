"""R015 release inventory and optional entitlement metadata.

A registered roadmap group is not an accepted release. This candidate has no
independently accepted deployment-profile record. The catalog is informative;
it never grants authority or switches resource-level capabilities on or off.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

# Catalog of stable roadmap IDs, not an acceptance checklist. Keep optional
# capabilities distinct from the mandatory team release profile.
RELEASE_CAPABILITIES: tuple[tuple[str, str, str], ...] = (
    ("R001", "Platform Foundation", "M0"),
    ("R002", "Identity, Organization & Tenancy", "M1"),
    ("R003", "Spatial Catalog & CRS (VN-2000)", "M1"),
    ("R004", "Map Workspace", "M1"),
    ("R005", "Import & Export + Durable Jobs", "M1"),
    ("R006", "Editing & Change History", "M2"),
    ("R007", "Attribute & Spatial Query", "M2"),
    ("R008", "Processing & Jobs (Buffer/Clip/Dissolve)", "M2"),
    ("R009", "Cartography & Print Output (PNG/PDF)", "M2"),
    ("R010", "External Sources (SSRF-safe Allowlist)", "M3"),
    ("R011", "Team Collaboration & Reviews", "M3"),
    ("R012", "CAD 2D DXF & Precision COGO", "M3"),
    ("R013", "Field & Offline GeoPackage + Sync", "M3"),
    ("R014", "Internal Extension Platform", "M3"),
    ("R015", "Production Operations & Self-Host Profile", "M3"),
)
RELEASE_IDS = frozenset(item[0] for item in RELEASE_CAPABILITIES)
DEFAULT_REQUESTED_FEATURES = ("R001", "R002", "R003", "R004", "R005", "R006", "R007")
MANDATORY_TEAM_RELEASE = frozenset((*DEFAULT_REQUESTED_FEATURES, "R011", "R015"))


def release_inventory() -> dict[str, Any]:
    """Report release certification separately from implemented/runtime capabilities.

    No positive certification path is currently authorized: there is no approved
    exact-candidate/profile acceptance record. Once a reviewed release gate and
    profile-specific budgets are defined, they must supply evidence here rather
    than infer acceptance from routes, flags, or a green liveness probe.
    """
    items = [
        {
            "id": release_id,
            "name": name,
            "milestone": milestone,
            # Keep the wire key for existing consumers; it refers to certification,
            # NOT application availability, entitlement, or authorization.
            "enabled": False,
            "status": "unverified",
            "reason": "exact_candidate_profile_acceptance_missing",
            "required_for_team": release_id in MANDATORY_TEAM_RELEASE,
        }
        for release_id, name, milestone in RELEASE_CAPABILITIES
    ]
    return {
        "profile": "self_host_team",
        "profile_status": "unverified",
        "verified_candidate": None,
        "verification_record": None,
        "production_ready": False,
        "enabled_semantics": "release_certification",
        "total_releases": len(items),
        "accepted_release_count": sum(item["enabled"] is True for item in items),
        "items": items,
    }


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
