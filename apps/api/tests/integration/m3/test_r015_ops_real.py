"""Real PostgreSQL/PostGIS integration tests for R014 Core Extension Platform & R015 Ops."""

from __future__ import annotations

from pathlib import Path

import pytest

from openvietgis_api.config import get_settings
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


def test_r015_production_ops_health_metrics_and_entitlements(
    migrated_database: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENVIETGIS_ARTIFACT_STORE_DIR", str(tmp_path))
    get_settings.cache_clear()
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
        assert ready.json()["production_ready"] is False
        assert ready.json()["scope"] == "dependency_probe_only"

        missing_store = tmp_path / "no-such-storage"
        monkeypatch.setenv("OPENVIETGIS_ARTIFACT_STORE_DIR", str(missing_store))
        get_settings.cache_clear()
        not_ready = client.get("/api/v1/ops/health/ready")
        assert not_ready.status_code == 503
        assert not_ready.json()["artifact_store"] == "unavailable"
        assert not missing_store.exists()
        monkeypatch.setenv("OPENVIETGIS_ARTIFACT_STORE_DIR", str(tmp_path))
        get_settings.cache_clear()

        metrics = client.get("/api/v1/ops/metrics")
        assert metrics.status_code == 200
        assert "openvietgis_up 1" in metrics.text
        assert "openvietgis_release_capabilities_enabled 0\n" in metrics.text
        assert "openvietgis_release_inventory_count 15\n" in metrics.text
        assert "openvietgis_release_gate_ready 0\n" in metrics.text

        caps = client.get("/api/v1/ops/release-capabilities")
        assert caps.status_code == 200
        assert caps.json()["total_releases"] == 15
        assert caps.json()["accepted_release_count"] == 0
        assert caps.json()["profile_status"] == "unverified"
        assert caps.json()["production_ready"] is False
        assert all(
            item["enabled"] is False and item["status"] == "unverified"
            for item in caps.json()["items"]
        )

        # This is unapproved commercial configuration metadata, not enforcement.
        defaults = client.get(f"{org_base}/ops/entitlement")
        assert defaults.status_code == 200
        assert defaults.json()["enforcement"] == "metadata_only"
        assert defaults.json()["features_enabled"] == [
            "R001",
            "R002",
            "R003",
            "R004",
            "R005",
            "R006",
            "R007",
        ]

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
        assert ent.json()["enforcement"] == "metadata_only"

        for invalid_features in (["R999"], ["R001", "R001"]):
            invalid = client.put(
                f"{org_base}/ops/entitlement",
                json={"features_enabled": invalid_features},
            )
            assert invalid.status_code == 422, invalid.text

        with _client(world.member_user_id) as member:
            visible = member.get(f"{org_base}/ops/entitlement")
            assert visible.status_code == 200
            denied = member.put(
                f"{org_base}/ops/entitlement",
                json={"features_enabled": ["R001"]},
            )
            assert denied.status_code == 403
        with _client(world.wrong_user_id) as outsider:
            assert outsider.get(f"{org_base}/ops/entitlement").status_code == 404
            assert outsider.put(f"{org_base}/ops/entitlement", json={}).status_code == 404
        current = client.get(f"{org_base}/ops/entitlement")
        assert current.json()["plan_tier"] == "team_standard"

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
        events = client.get(f"{org_base}/audit-events")
        assert events.status_code == 200
        entitlement_events = [
            event for event in events.json() if event["action"] == "ops.entitlement.configure"
        ]
        assert len(entitlement_events) == 2
        assert all(
            event["actor_id"] == str(world.owner_user_id)
            and event["resource_id"] == str(world.organization_id)
            for event in entitlement_events
        )
