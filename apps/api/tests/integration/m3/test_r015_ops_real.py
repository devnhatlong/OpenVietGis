"""Real PostgreSQL/PostGIS integration tests for R014 Core Extension Platform & R015 Ops."""

from __future__ import annotations

from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client


def test_r014_core_extension_platform_generic_contracts(migrated_database: None) -> None:
    world = seed_access_world()
    org_base = f"/api/v1/organizations/{world.organization_id}"
    proj_base = f"{org_base}/projects/{world.project_id}"

    with _client(world.owner_user_id) as client:
        # 1. Reject cross-namespace permission injection
        bad_perm = client.post(
            f"{org_base}/extensions/manifests",
            json={
                "extension_key": "sample_ext",
                "version": "1.0.0",
                "api_compatibility": "1.x",
                "display_name": "Sample Extension",
                "permissions": ["project.delete"],
                "entity_schemas": {
                    "item": {"fields": {"code": {"type": "text", "required": True}}}
                },
            },
        )
        assert bad_perm.status_code == 422
        assert bad_perm.json()["code"] == "INVALID_PERMISSION_NAMESPACE"

        # 2. Register valid generic extension manifest
        reg = client.post(
            f"{org_base}/extensions/manifests",
            json={
                "extension_key": "survey_notes",
                "version": "1.0.0",
                "api_compatibility": "1.x",
                "display_name": "Survey Notes Extension",
                "permissions": ["ext.survey_notes.read", "ext.survey_notes.write"],
                "commands": [{"id": "log_note", "label": "Log Survey Note"}],
                "capabilities": ["note_registry"],
                "entity_schemas": {
                    "note": {
                        "fields": {
                            "title": {"type": "text", "required": True},
                            "priority": {"type": "integer", "required": True},
                        }
                    }
                },
            },
        )
        assert reg.status_code == 201, reg.text
        mid = reg.json()["id"]

        # 3. Activate in project & create schema-validated record
        act = client.post(
            f"{proj_base}/extensions/activations",
            json={"manifest_id": mid},
        )
        assert act.status_code == 201 and act.json()["status"] == "active"

        bad_rec = client.post(
            f"{proj_base}/extensions/survey_notes/records",
            json={"entity_name": "note", "payload": {"title": "Bad", "priority": "not-an-int"}},
        )
        assert bad_rec.status_code == 422

        rec = client.post(
            f"{proj_base}/extensions/survey_notes/records",
            json={"entity_name": "note", "payload": {"title": "Benchmark A", "priority": 1}},
        )
        assert rec.status_code == 201, rec.text

        listed = client.get(f"{proj_base}/extensions/survey_notes/records")
        assert listed.status_code == 200 and len(listed.json()["items"]) == 1


def test_r015_production_ops_health_metrics_and_entitlements(migrated_database: None) -> None:
    world = seed_access_world()
    org_base = f"/api/v1/organizations/{world.organization_id}"

    with _client(world.owner_user_id) as client:
        live = client.get("/api/v1/ops/health/live")
        assert live.status_code == 200 and live.json()["status"] == "alive"

        ready = client.get("/api/v1/ops/health/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "ready"
        assert ready.json()["database"] == "ok"
        assert ready.json()["artifact_store"] == "ok"

        metrics = client.get("/api/v1/ops/metrics")
        assert metrics.status_code == 200
        assert "openvietgis_up 1" in metrics.text
        assert "openvietgis_release_capabilities_enabled 15" in metrics.text

        caps = client.get("/api/v1/ops/release-capabilities")
        assert caps.status_code == 200
        assert caps.json()["total_releases"] == 15

        # Entitlement distinct from authorization & non-destructive on plan change
        ent = client.put(
            f"{org_base}/ops/entitlement",
            json={
                "deployment_profile": "self_host_team",
                "plan_tier": "team_standard",
                "max_projects": 250,
                "max_storage_mb": 20480,
                "features_enabled": ["R001", "R002", "R005", "R006", "R011", "R015"],
            },
        )
        assert ent.status_code == 200, ent.text
        assert ent.json()["authorization_distinct"] is True
        assert ent.json()["data_deletion_on_plan_change"] is False
        assert ent.json()["plan_tier"] == "team_standard"

        # Downgrading plan tier never deletes existing project
        down = client.put(
            f"{org_base}/ops/entitlement",
            json={
                "deployment_profile": "self_host_team",
                "plan_tier": "self_host_community",
                "max_projects": 10,
                "max_storage_mb": 1024,
                "features_enabled": ["R001", "R002"],
            },
        )
        assert down.status_code == 200
        proj = client.get(f"{org_base}/projects/{world.project_id}")
        assert proj.status_code == 200
