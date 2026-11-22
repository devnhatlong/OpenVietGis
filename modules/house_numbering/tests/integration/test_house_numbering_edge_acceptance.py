"""HN019 edge acceptance: lifecycle, geometry, concurrency, approval and offline replay."""

from __future__ import annotations

import io
from dataclasses import replace
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import text
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_authorization import _grant
from tests.integration.spatial.test_sources import _client

from modules.house_numbering.migrate import upgrade as migrate_house_numbering
from modules.house_numbering.tests.integration.test_house_numbering_runtime import (
    _seed_source,
)
from modules.land_asset.workflow import build_inspection_payload
from modules.land_asset.workflow import load_manifest as load_land_manifest


def _activate_house(client, world):
    org = f"/api/v1/organizations/{world.organization_id}"
    project = f"{org}/projects/{world.project_id}"
    manifest = client.post(f"{org}/extensions/official/house_numbering/register")
    assert manifest.status_code == 201, manifest.text
    active = client.post(
        f"{project}/extensions/activations",
        json={"manifest_id": manifest.json()["id"]},
    )
    assert active.status_code == 201, active.text
    return org, project, f"{project}/modules/house-numbering", manifest.json()


def _sibling_project(owner, world):
    response = owner.post(
        f"/api/v1/organizations/{world.organization_id}/projects",
        json={
            "name": "HN sibling",
            "slug": f"hn-sibling-{uuid4().hex[:12]}",
            "workspace_id": str(world.workspace_a_id),
        },
    )
    assert response.status_code == 201, response.text
    return replace(world, project_id=UUID(response.json()["id"]))


def _create_rule(
    client, module, *, version: str, authoritative: bool, distance: float = 5
):
    response = client.post(
        f"{module}/rules",
        json={
            "version": version,
            "status": "authoritative" if authoritative else "draft",
            "authority_ref": f"SYNTH-{version}" if authoritative else None,
            "left_odd": True,
            "suffix_style": "letters",
            "max_distance_m": distance,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_route(
    client,
    module,
    *,
    name: str,
    source_id,
    feature_id: str,
    parent_route_id: str | None = None,
    prefix: str | None = None,
):
    response = client.post(
        f"{module}/routes",
        json={
            "name": name,
            "route_type": "alley" if parent_route_id else "street",
            "parent_route_id": parent_route_id,
            "prefix": prefix,
            "source_id": str(source_id),
            "feature_id": feature_id,
            "direction_state": "forward",
            "source_label": "HN019 edge fixture",
            "status": "confirmed",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_building(
    client,
    module,
    *,
    route_id: str,
    source_id,
    feature_id: str,
    parcel_ref: str | None = None,
):
    response = client.post(
        f"{module}/buildings",
        json={
            "route_id": route_id,
            "source_id": str(source_id),
            "feature_id": feature_id,
            "parcel_ref": parcel_ref,
            "eligibility": "eligible",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_lifecycle_scope_and_land_asset_coexistence(migrated_database: None) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    outsider_world = seed_access_world()
    org = f"/api/v1/organizations/{world.organization_id}"
    project = f"{org}/projects/{world.project_id}"

    with (
        _client(world.owner_user_id) as owner,
        _client(world.member_user_id, raise_server_exceptions=False) as editor,
        _client(
            outsider_world.owner_user_id, raise_server_exceptions=False
        ) as outsider,
    ):
        _grant(owner, world, "membership", str(world.member_membership_id), "editor")

        denied_register = editor.post(
            f"{org}/extensions/official/house_numbering/register"
        )
        assert denied_register.status_code == 403, denied_register.text

        manifest = owner.post(f"{org}/extensions/official/house_numbering/register")
        assert manifest.status_code == 201, manifest.text

        denied_activate = editor.post(
            f"{project}/extensions/activations",
            json={"manifest_id": manifest.json()["id"]},
        )
        assert denied_activate.status_code == 403, denied_activate.text

        active = owner.post(
            f"{project}/extensions/activations",
            json={"manifest_id": manifest.json()["id"]},
        )
        assert active.status_code == 201, active.text

        denied_disable = editor.post(f"{project}/extensions/house_numbering/disable")
        assert denied_disable.status_code == 403, denied_disable.text

        module = f"{project}/modules/house-numbering"
        assert outsider.get(f"{module}/routes").status_code in {403, 404}

        sibling = _sibling_project(owner, world)
        sibling_module = (
            f"/api/v1/organizations/{world.organization_id}/projects/{sibling.project_id}"
            "/modules/house-numbering"
        )
        assert owner.get(f"{sibling_module}/routes").status_code == 404

        land_manifest = owner.post(
            f"{org}/extensions/manifests", json=load_land_manifest()
        )
        assert land_manifest.status_code == 201, land_manifest.text
        land_active = owner.post(
            f"{project}/extensions/activations",
            json={"manifest_id": land_manifest.json()["id"]},
        )
        assert land_active.status_code == 201, land_active.text
        inspection = build_inspection_payload(
            asset_code="HN019-LAND",
            land_use_code="ODT",
            area_m2=123.5,
            condition_score=5,
            inspector_note="Synthetic coexistence",
        )
        stored = owner.post(
            f"{project}/extensions/land_asset/records",
            json={"entity_name": "asset_inspection", "payload": inspection},
        )
        assert stored.status_code == 201, stored.text

        rule = _create_rule(owner, module, version="COEXIST-019", authoritative=True)
        assert rule["status"] == "authoritative"
        land_records = owner.get(f"{project}/extensions/land_asset/records")
        assert land_records.status_code == 200, land_records.text
        assert land_records.json()["items"][0]["payload"]["asset_code"] == "HN019-LAND"


def test_geometry_preview_and_proposal_guards(migrated_database: None) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    straight = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_edge_straight_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="straight",
        wkt="LINESTRING(0 0,100 0)",
        extent={"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 0, "crs_code": 3857},
    )
    bend = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_edge_bend_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="bend",
        wkt="LINESTRING(0 0,10 0,10 10)",
        extent={"min_x": 0, "min_y": 0, "max_x": 10, "max_y": 10, "crs_code": 3857},
    )
    p1 = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_edge_p1_{uuid4().hex[:8]}",
        family="Point",
        feature_id="p1",
        wkt="POINT(20 -1)",
        extent={"min_x": 20, "min_y": -1, "max_x": 20, "max_y": -1, "crs_code": 3857},
    )
    p2 = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_edge_p2_{uuid4().hex[:8]}",
        family="Point",
        feature_id="p2",
        wkt="POINT(40 -1)",
        extent={"min_x": 40, "min_y": -1, "max_x": 40, "max_y": -1, "crs_code": 3857},
    )

    with _client(world.owner_user_id, raise_server_exceptions=False) as client:
        _, _, module, _ = _activate_house(client, world)
        draft_rule = _create_rule(
            client, module, version="DRAFT-EDGE-019", authoritative=False, distance=5
        )
        auth_rule = _create_rule(
            client, module, version="AUTH-EDGE-019", authoritative=True, distance=5
        )

        parent = _create_route(
            client,
            module,
            name="Parent",
            source_id=straight,
            feature_id="straight",
        )
        alley = _create_route(
            client,
            module,
            name="Nested alley",
            source_id=straight,
            feature_id="straight",
            parent_route_id=parent["id"],
            prefix="155/3",
        )
        bend_route = _create_route(
            client,
            module,
            name="Bend",
            source_id=bend,
            feature_id="bend",
        )
        b1 = _create_building(
            client,
            module,
            route_id=alley["id"],
            source_id=p1,
            feature_id="p1",
            parcel_ref="EDGE-PARCEL-1",
        )
        b2 = _create_building(
            client, module, route_id=alley["id"], source_id=p2, feature_id="p2"
        )
        with get_admin_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO house_numbering.evidence (
                        id,organization_id,project_id,building_id,route_id,origin,
                        raw_number,source_reference,evidence_date,confidence,
                        private_ref,created_by_actor_id,created_at
                    ) VALUES (
                        :id,:org,:project,:building,:route,'certificate',
                        '155/3/2','EDGE-CERT-1',NULL,'authoritative',
                        NULL,:actor,now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "org": world.organization_id,
                    "project": world.project_id,
                    "building": UUID(b1["id"]),
                    "route": UUID(alley["id"]),
                    "actor": world.owner_user_id,
                },
            )

        contextual = client.post(
            f"{module}/inspect",
            json={
                "x": 20,
                "y": -1,
                "crs_code": 3857,
                "route_id": alley["id"],
                "rule_id": auth_rule["id"],
                "existing_building_id": b1["id"],
            },
        )
        assert contextual.status_code == 200, contextual.text
        assert contextual.json()["context"]["building"]["parcel_ref"] == "EDGE-PARCEL-1"
        assert contextual.json()["context"]["evidence"][0]["origin"] == "certificate"
        assert contextual.json()["context"]["evidence"][0]["raw_number"] == "155/3/2"

        on_route = client.post(
            f"{module}/inspect",
            json={
                "x": 20,
                "y": 0,
                "crs_code": 3857,
                "route_id": alley["id"],
                "rule_id": auth_rule["id"],
            },
        )
        assert on_route.status_code == 200, on_route.text
        assert on_route.json()["suggestion"]["reason"] == "ambiguous_route_side"

        tie = client.post(
            f"{module}/inspect",
            json={
                "x": 9,
                "y": 1,
                "crs_code": 3857,
                "route_id": bend_route["id"],
                "rule_id": auth_rule["id"],
            },
        )
        assert tie.status_code == 200, tie.text
        assert tie.json()["suggestion"]["reason"] == "ambiguous_route_side"

        far = client.post(
            f"{module}/inspect",
            json={
                "x": 20,
                "y": -10,
                "crs_code": 3857,
                "route_id": alley["id"],
                "rule_id": auth_rule["id"],
            },
        )
        assert far.status_code == 200, far.text
        assert far.json()["suggestion"] == {
            "number": None,
            "reason": "outside_route_distance",
            "rule_version": "AUTH-EDGE-019",
        }
        assert (
            client.post(
                f"{module}/inspect",
                json={
                    "x": 20,
                    "y": -1,
                    "crs_code": 0,
                    "route_id": alley["id"],
                    "rule_id": auth_rule["id"],
                },
            ).status_code
            == 422
        )

        draft_preview = client.post(
            f"{module}/previews",
            json={
                "building_ids": [b1["id"]],
                "rule_id": draft_rule["id"],
                "operation_id": str(uuid4()),
            },
        )
        assert draft_preview.status_code == 201, draft_preview.text
        assert draft_preview.json()["candidate_changes"][0]["number"].startswith(
            "155/3/"
        )

        changed = client.patch(
            f"{module}/buildings/{b1['id']}/eligibility",
            json={"expected_revision": 1, "eligibility": "eligible", "reason": None},
        )
        assert changed.status_code == 200, changed.text
        stale_apply = client.post(
            f"{module}/previews/{draft_preview.json()['id']}/apply"
        )
        assert stale_apply.status_code == 409, stale_apply.text
        with get_admin_engine().connect() as c:
            assert (
                c.execute(
                    text(
                        "SELECT count(*) FROM house_numbering.address_numbers "
                        "WHERE organization_id=:org AND project_id=:project AND building_id=:building"
                    ),
                    {
                        "org": world.organization_id,
                        "project": world.project_id,
                        "building": UUID(b1["id"]),
                    },
                ).scalar_one()
                == 0
            )

        preview = client.post(
            f"{module}/previews",
            json={
                "building_ids": [b1["id"]],
                "rule_id": draft_rule["id"],
                "operation_id": str(uuid4()),
            },
        )
        assert preview.status_code == 201, preview.text
        first_apply = client.post(f"{module}/previews/{preview.json()['id']}/apply")
        assert first_apply.status_code == 200, first_apply.text
        second_apply = client.post(f"{module}/previews/{preview.json()['id']}/apply")
        assert second_apply.status_code == 200, second_apply.text
        assert (
            first_apply.json()["items"][0]["id"]
            == second_apply.json()["items"][0]["id"]
        )

        draft_proposal = client.post(
            f"{module}/proposals",
            json={
                "scope_kind": "route",
                "scope_id": alley["id"],
                "rule_id": draft_rule["id"],
                "building_ids": [b1["id"]],
            },
        )
        assert draft_proposal.status_code == 201, draft_proposal.text
        draft_pid = draft_proposal.json()["proposal"]["id"]
        submitted = client.post(
            f"{module}/proposals/{draft_pid}/transition",
            json={"expected_revision": 1, "action": "submit"},
        )
        assert submitted.status_code == 200, submitted.text
        assert (
            client.post(
                f"{module}/proposals/{draft_pid}/transition",
                json={"expected_revision": 2, "action": "approve"},
            ).status_code
            == 409
        )
        no_reason = client.post(
            f"{module}/proposals/{draft_pid}/transition",
            json={"expected_revision": 2, "action": "reject"},
        )
        assert no_reason.status_code == 422, no_reason.text
        rejected = client.post(
            f"{module}/proposals/{draft_pid}/transition",
            json={
                "expected_revision": 2,
                "action": "reject",
                "comment": "Synthetic correction required",
            },
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "draft"

        withdrawal_proposal = client.post(
            f"{module}/proposals",
            json={
                "scope_kind": "route",
                "scope_id": alley["id"],
                "rule_id": auth_rule["id"],
                "building_ids": [b1["id"]],
            },
        )
        assert withdrawal_proposal.status_code == 201, withdrawal_proposal.text
        withdrawal_id = withdrawal_proposal.json()["proposal"]["id"]
        withdrawal_submitted = client.post(
            f"{module}/proposals/{withdrawal_id}/transition",
            json={"expected_revision": 1, "action": "submit"},
        )
        assert withdrawal_submitted.status_code == 200, withdrawal_submitted.text
        missing_withdraw_reason = client.post(
            f"{module}/proposals/{withdrawal_id}/transition",
            json={"expected_revision": 2, "action": "withdraw"},
        )
        assert missing_withdraw_reason.status_code == 422, missing_withdraw_reason.text
        withdrawn = client.post(
            f"{module}/proposals/{withdrawal_id}/transition",
            json={
                "expected_revision": 2,
                "action": "withdraw",
                "comment": "Synthetic owner withdrawal",
            },
        )
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == "draft"

        authoritative_proposal = client.post(
            f"{module}/proposals",
            json={
                "scope_kind": "route",
                "scope_id": alley["id"],
                "rule_id": auth_rule["id"],
                "building_ids": [b1["id"]],
            },
        )
        assert authoritative_proposal.status_code == 201, authoritative_proposal.text
        pid = authoritative_proposal.json()["proposal"]["id"]
        sub = client.post(
            f"{module}/proposals/{pid}/transition",
            json={"expected_revision": 1, "action": "submit"},
        )
        assert sub.status_code == 200, sub.text
        stale = client.post(
            f"{module}/proposals/{pid}/transition",
            json={"expected_revision": 1, "action": "approve"},
        )
        assert stale.status_code == 409, stale.text
        approved = client.post(
            f"{module}/proposals/{pid}/transition",
            json={"expected_revision": 2, "action": "approve"},
        )
        assert approved.status_code == 200, approved.text

        direction_locked = client.put(
            f"{module}/routes/{alley['id']}",
            json={
                "expected_revision": 1,
                "name": "Nested alley",
                "direction_state": "reverse",
                "status": "confirmed",
            },
        )
        assert direction_locked.status_code == 409, direction_locked.text
        assert client.delete(f"{module}/routes/{alley['id']}").status_code == 409

        # A duplicate may exist while proposed, but must fail before becoming official.
        with get_admin_engine().begin() as c:
            duplicate_number = first_apply.json()["items"][0]["number_text"]
            c.execute(
                text(
                    """
                    INSERT INTO house_numbering.address_numbers (
                        id,organization_id,project_id,building_id,route_id,number_text,kind,
                        side,measure_m,rule_id,revision,created_by_actor_id,updated_by_actor_id,
                        created_at,updated_at
                    ) VALUES (
                        :id,:org,:project,:building,:route,:number,'proposed',
                        'right',40,:rule,1,:actor,:actor,now(),now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "org": world.organization_id,
                    "project": world.project_id,
                    "building": UUID(b2["id"]),
                    "route": UUID(alley["id"]),
                    "number": duplicate_number,
                    "rule": UUID(auth_rule["id"]),
                    "actor": world.owner_user_id,
                },
            )
        duplicate_proposal = client.post(
            f"{module}/proposals",
            json={
                "scope_kind": "route",
                "scope_id": alley["id"],
                "rule_id": auth_rule["id"],
                "building_ids": [b2["id"]],
            },
        )
        assert duplicate_proposal.status_code == 201, duplicate_proposal.text
        duplicate_submit = client.post(
            f"{module}/proposals/{duplicate_proposal.json()['proposal']['id']}/transition",
            json={"expected_revision": 1, "action": "submit"},
        )
        assert duplicate_submit.status_code == 409, duplicate_submit.text


def test_offline_batch_of_50_replays_and_conflicts(migrated_database: None) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        _, _, module, _ = _activate_house(client, world)
        image_buffer = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(image_buffer, format="PNG")
        photo = client.post(
            f"{module}/survey/photos",
            files={"file": ("offline.png", image_buffer.getvalue(), "image/png")},
        )
        assert photo.status_code == 201, photo.text
        photo_id = photo.json()["id"]
        operations = [
            {
                "client_uuid": str(uuid4()),
                "condition": "house" if index % 2 == 0 else "vacant",
                "photo_artifact_ids": [photo_id],
            }
            for index in range(50)
        ]
        first = client.post(f"{module}/survey/sync", json={"operations": operations})
        assert first.status_code == 200, first.text
        assert len(first.json()["applied"]) == 50
        assert first.json()["conflicts"] == []

        replay = client.post(f"{module}/survey/sync", json={"operations": operations})
        assert replay.status_code == 200, replay.text
        assert len(replay.json()["replayed"]) == 50
        assert replay.json()["applied"] == []

        changed = [{**operations[0], "condition": "other"}]
        conflict = client.post(f"{module}/survey/sync", json={"operations": changed})
        assert conflict.status_code == 200, conflict.text
        assert conflict.json()["conflicts"] == [
            {
                "client_uuid": operations[0]["client_uuid"],
                "code": "CLIENT_UUID_PAYLOAD_CONFLICT",
            }
        ]


def test_gps_quality_and_delegated_submission(migrated_database: None) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    point_source = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_gps_point_{uuid4().hex[:8]}",
        family="Point",
        feature_id="gps-house",
        wkt="POINT(20 -1)",
        extent={"min_x": 20, "min_y": -1, "max_x": 20, "max_y": -1, "crs_code": 3857},
    )
    line_source = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_gps_line_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="gps-route",
        wkt="LINESTRING(0 0,100 0)",
        extent={"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 0, "crs_code": 3857},
    )

    with (
        _client(world.owner_user_id) as owner,
        _client(world.member_user_id, raise_server_exceptions=False) as editor,
    ):
        _, _, module, _ = _activate_house(owner, world)
        _grant(owner, world, "membership", str(world.member_membership_id), "editor")
        route = _create_route(
            owner,
            module,
            name="GPS route",
            source_id=line_source,
            feature_id="gps-route",
        )
        building = _create_building(
            owner,
            module,
            route_id=route["id"],
            source_id=point_source,
            feature_id="gps-house",
        )

        client_uuid = str(uuid4())
        delegated = {
            "client_uuid": client_uuid,
            "building_id": building["id"],
            "x": 50,
            "y": -1,
            "crs_code": 3857,
            "gps_accuracy_m": 5,
            "recorded_by_actor_id": str(world.member_user_id),
            "condition": "house",
            "photo_artifact_ids": [],
        }
        synced = owner.post(f"{module}/survey/sync", json={"operations": [delegated]})
        assert synced.status_code == 200, synced.text
        assert len(synced.json()["applied"]) == 1
        assert synced.json()["warnings"][0]["code"] == "GPS_DEVIATION"
        assert synced.json()["warnings"][0]["accuracy_m"] == 5.0
        assert synced.json()["warnings"][0]["deviation_m"] > 20

        survey_id = UUID(synced.json()["applied"][0])
        with get_admin_engine().connect() as connection:
            survey = (
                connection.execute(
                    text(
                        """
                        SELECT recorded_by_actor_id,submitted_by_actor_id,crs_code,
                               gps_accuracy_m,gps_deviation_m,warnings,payload_fingerprint
                        FROM house_numbering.surveys
                        WHERE organization_id=:org AND project_id=:project AND id=:id
                        """
                    ),
                    {
                        "org": world.organization_id,
                        "project": world.project_id,
                        "id": survey_id,
                    },
                )
                .mappings()
                .one()
            )
        assert survey["recorded_by_actor_id"] == world.member_user_id
        assert survey["submitted_by_actor_id"] == world.owner_user_id
        assert survey["crs_code"] == 3857
        assert survey["gps_accuracy_m"] == 5
        assert survey["gps_deviation_m"] > 20
        assert survey["warnings"][0]["code"] == "GPS_DEVIATION"
        assert len(survey["payload_fingerprint"]) == 64

        # Replay remains idempotent even if Core geometry changes after the original sync.
        with get_admin_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE spatial.reference_features
                    SET geometry=ST_GeomFromText('POINT(80 -1)',3857)
                    WHERE organization_id=:org AND project_id=:project
                      AND source_id=:source AND feature_id='gps-house'
                    """
                ),
                {
                    "org": world.organization_id,
                    "project": world.project_id,
                    "source": point_source,
                },
            )
        replay = owner.post(f"{module}/survey/sync", json={"operations": [delegated]})
        assert replay.status_code == 200, replay.text
        assert replay.json()["replayed"] == [str(survey_id)]
        assert replay.json()["applied"] == []

        missing_accuracy = {
            "client_uuid": str(uuid4()),
            "building_id": building["id"],
            "x": 80,
            "y": -1,
            "crs_code": 3857,
            "condition": "other",
            "photo_artifact_ids": [],
        }
        warned = owner.post(
            f"{module}/survey/sync", json={"operations": [missing_accuracy]}
        )
        assert warned.status_code == 200, warned.text
        assert warned.json()["warnings"][0]["code"] == "GPS_ACCURACY_MISSING"

        invalid_delegate = {
            "client_uuid": str(uuid4()),
            "condition": "other",
            "recorded_by_actor_id": str(uuid4()),
            "photo_artifact_ids": [],
        }
        invalid = owner.post(
            f"{module}/survey/sync", json={"operations": [invalid_delegate]}
        )
        assert invalid.status_code == 422, invalid.text

        editor_delegate = {
            "client_uuid": str(uuid4()),
            "condition": "other",
            "recorded_by_actor_id": str(world.owner_user_id),
            "photo_artifact_ids": [],
        }
        denied = editor.post(
            f"{module}/survey/sync", json={"operations": [editor_delegate]}
        )
        assert denied.status_code == 403, denied.text


def test_plaque_split_merge_history_and_role_revocation(
    migrated_database: None,
) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    route_source = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_lineage_route_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="lineage-route",
        wkt="LINESTRING(0 0,200 0)",
        extent={"min_x": 0, "min_y": 0, "max_x": 200, "max_y": 0, "crs_code": 3857},
    )
    point_specs = {
        "original": (20, -3),
        "split-a": (22, -3),
        "split-b": (28, -3),
        "merged": (25, -3),
    }
    sources = {
        name: _seed_source(
            organization_id=world.organization_id,
            project_id=world.project_id,
            reference_key=f"hn_lineage_{name.replace('-', '_')}_{uuid4().hex[:8]}",
            family="Point",
            feature_id=name,
            wkt=f"POINT({xy[0]} {xy[1]})",
            extent={
                "min_x": xy[0],
                "min_y": xy[1],
                "max_x": xy[0],
                "max_y": xy[1],
                "crs_code": 3857,
            },
        )
        for name, xy in point_specs.items()
    }

    with (
        _client(world.owner_user_id) as owner,
        _client(world.member_user_id, raise_server_exceptions=False) as manager,
    ):
        org, _project, module, _ = _activate_house(owner, world)
        rule = _create_rule(
            owner, module, version="LINEAGE-019", authoritative=True, distance=50
        )
        route = _create_route(
            owner,
            module,
            name="Lineage route",
            source_id=route_source,
            feature_id="lineage-route",
        )
        original = _create_building(
            owner,
            module,
            route_id=route["id"],
            source_id=sources["original"],
            feature_id="original",
            parcel_ref="ORIGINAL",
        )
        split_a = _create_building(
            owner,
            module,
            route_id=route["id"],
            source_id=sources["split-a"],
            feature_id="split-a",
            parcel_ref="SPLIT-A",
        )
        split_b = _create_building(
            owner,
            module,
            route_id=route["id"],
            source_id=sources["split-b"],
            feature_id="split-b",
            parcel_ref="SPLIT-B",
        )
        merged = _create_building(
            owner,
            module,
            route_id=route["id"],
            source_id=sources["merged"],
            feature_id="merged",
            parcel_ref="MERGED",
        )

        approved_number_id = uuid4()
        with get_admin_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO house_numbering.address_numbers (
                        id,organization_id,project_id,building_id,route_id,number_text,kind,
                        side,measure_m,rule_id,revision,created_by_actor_id,updated_by_actor_id,
                        created_at,updated_at
                    ) VALUES (
                        :id,:org,:project,:building,:route,'20','approved',
                        'right',20,:rule,1,:actor,:actor,now(),now()
                    )
                    """
                ),
                {
                    "id": approved_number_id,
                    "org": world.organization_id,
                    "project": world.project_id,
                    "building": UUID(original["id"]),
                    "route": UUID(route["id"]),
                    "rule": UUID(rule["id"]),
                    "actor": world.owner_user_id,
                },
            )

        installed = owner.patch(
            f"{module}/buildings/{original['id']}/plaque",
            json={"expected_revision": 1, "status": "installed"},
        )
        assert installed.status_code == 200, installed.text
        assert installed.json()["plaque_status"] == "installed"
        assert installed.json()["revision"] == 2

        denied_without_number = owner.patch(
            f"{module}/buildings/{split_a['id']}/plaque",
            json={"expected_revision": 1, "status": "installed"},
        )
        assert denied_without_number.status_code == 409, denied_without_number.text

        split_operation = str(uuid4())
        split_payload = {
            "relation_kind": "split",
            "operation_id": split_operation,
            "predecessor_building_ids": [original["id"]],
            "successor_building_ids": [split_a["id"], split_b["id"]],
            "expected_revisions": {
                original["id"]: 2,
                split_a["id"]: 1,
                split_b["id"]: 1,
            },
        }
        split = owner.post(f"{module}/buildings/lineage", json=split_payload)
        assert split.status_code == 201, split.text
        assert len(split.json()["items"]) == 2

        replay = owner.post(f"{module}/buildings/lineage", json=split_payload)
        assert replay.status_code == 201, replay.text
        assert {item["id"] for item in replay.json()["items"]} == {
            item["id"] for item in split.json()["items"]
        }

        conflict_payload = {
            **split_payload,
            "successor_building_ids": [split_a["id"], merged["id"]],
            "expected_revisions": {
                original["id"]: 2,
                split_a["id"]: 1,
                merged["id"]: 1,
            },
        }
        operation_conflict = owner.post(
            f"{module}/buildings/lineage", json=conflict_payload
        )
        assert operation_conflict.status_code == 409, operation_conflict.text

        merge_operation = str(uuid4())
        merge = owner.post(
            f"{module}/buildings/lineage",
            json={
                "relation_kind": "merge",
                "operation_id": merge_operation,
                "predecessor_building_ids": [split_a["id"], split_b["id"]],
                "successor_building_ids": [merged["id"]],
                "expected_revisions": {
                    split_a["id"]: 1,
                    split_b["id"]: 1,
                    merged["id"]: 1,
                },
            },
        )
        assert merge.status_code == 201, merge.text
        assert len(merge.json()["items"]) == 2

        history = owner.get(f"{module}/buildings/{merged['id']}/lineage")
        assert history.status_code == 200, history.text
        assert {item["relation_kind"] for item in history.json()["items"]} == {"merge"}

        with get_admin_engine().connect() as connection:
            original_row = (
                connection.execute(
                    text(
                        """
                        SELECT state,plaque_status,revision
                        FROM house_numbering.buildings
                        WHERE organization_id=:org AND project_id=:project AND id=:id
                        """
                    ),
                    {
                        "org": world.organization_id,
                        "project": world.project_id,
                        "id": UUID(original["id"]),
                    },
                )
                .mappings()
                .one()
            )
            preserved = (
                connection.execute(
                    text(
                        """
                        SELECT kind,retired_at,number_text
                        FROM house_numbering.address_numbers
                        WHERE organization_id=:org AND project_id=:project AND id=:id
                        """
                    ),
                    {
                        "org": world.organization_id,
                        "project": world.project_id,
                        "id": approved_number_id,
                    },
                )
                .mappings()
                .one()
            )
            successor_number_count = connection.execute(
                text(
                    """
                    SELECT count(*) FROM house_numbering.address_numbers
                    WHERE organization_id=:org AND project_id=:project
                      AND building_id = ANY(:ids)
                    """
                ),
                {
                    "org": world.organization_id,
                    "project": world.project_id,
                    "ids": [
                        UUID(split_a["id"]),
                        UUID(split_b["id"]),
                        UUID(merged["id"]),
                    ],
                },
            ).scalar_one()
        assert original_row["state"] == "removed"
        assert original_row["plaque_status"] == "removed"
        assert preserved["kind"] == "approved"
        assert preserved["retired_at"] is None
        assert preserved["number_text"] == "20"
        assert successor_number_count == 0

        manager_grant = _grant(
            owner, world, "membership", str(world.member_membership_id), "manager"
        )
        manager_update = manager.patch(
            f"{module}/buildings/{merged['id']}/plaque",
            json={"expected_revision": 1, "status": "planned"},
        )
        assert manager_update.status_code == 200, manager_update.text
        assert manager_update.json()["revision"] == 2

        revoked = owner.post(f"{org}/grants/{manager_grant}/revoke")
        assert revoked.status_code == 204, revoked.text
        after_revoke = manager.patch(
            f"{module}/buildings/{merged['id']}/plaque",
            json={"expected_revision": 2, "status": "not_planned"},
        )
        assert after_revoke.status_code in {403, 404}, after_revoke.text


def test_registry_crud_revision_dependency_and_audit(migrated_database: None) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    line_source = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_crud_line_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="crud-route",
        wkt="LINESTRING(0 0,100 0)",
        extent={"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 0, "crs_code": 3857},
    )
    point_a = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_crud_point_a_{uuid4().hex[:8]}",
        family="Point",
        feature_id="crud-a",
        wkt="POINT(10 -2)",
        extent={"min_x": 10, "min_y": -2, "max_x": 10, "max_y": -2, "crs_code": 3857},
    )
    point_b = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_crud_point_b_{uuid4().hex[:8]}",
        family="Point",
        feature_id="crud-b",
        wkt="POINT(12 -2)",
        extent={"min_x": 12, "min_y": -2, "max_x": 12, "max_y": -2, "crs_code": 3857},
    )

    with _client(world.owner_user_id, raise_server_exceptions=False) as client:
        _, _, module, _ = _activate_house(client, world)
        root = client.post(f"{module}/areas", json={"name": "Root", "kind": "current"})
        assert root.status_code == 201, root.text
        root_body = root.json()
        child = client.post(
            f"{module}/areas",
            json={
                "name": "Child",
                "kind": "historic",
                "parent_id": root_body["id"],
            },
        )
        assert child.status_code == 201, child.text
        child_body = child.json()

        cycle = client.put(
            f"{module}/areas/{root_body['id']}",
            json={
                "expected_revision": root_body["revision"],
                "name": "Root",
                "kind": "current",
                "parent_id": child_body["id"],
                "source_id": None,
                "feature_id": None,
            },
        )
        assert cycle.status_code == 409, cycle.text
        blocked_delete = client.delete(
            f"{module}/areas/{root_body['id']}",
            params={"expected_revision": root_body["revision"]},
        )
        assert blocked_delete.status_code == 409, blocked_delete.text

        renamed = client.put(
            f"{module}/areas/{child_body['id']}",
            json={
                "expected_revision": child_body["revision"],
                "name": "Child renamed",
                "kind": "historic",
                "parent_id": root_body["id"],
                "source_id": None,
                "feature_id": None,
            },
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["revision"] == 2
        stale_area = client.put(
            f"{module}/areas/{child_body['id']}",
            json={
                "expected_revision": 1,
                "name": "stale",
                "kind": "historic",
                "parent_id": root_body["id"],
                "source_id": None,
                "feature_id": None,
            },
        )
        assert stale_area.status_code == 409, stale_area.text
        deleted_child = client.delete(
            f"{module}/areas/{child_body['id']}", params={"expected_revision": 2}
        )
        assert deleted_child.status_code == 204, deleted_child.text

        route = _create_route(
            client,
            module,
            name="CRUD route",
            source_id=line_source,
            feature_id="crud-route",
        )
        building = _create_building(
            client,
            module,
            route_id=route["id"],
            source_id=point_a,
            feature_id="crud-a",
            parcel_ref="PARCEL-A",
        )
        updated = client.put(
            f"{module}/buildings/{building['id']}",
            json={
                "expected_revision": 1,
                "route_id": route["id"],
                "area_id": root_body["id"],
                "parcel_ref": "PARCEL-B",
                "source_id": str(point_b),
                "feature_id": "crud-b",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["revision"] == 2
        assert updated.json()["parcel_ref"] == "PARCEL-B"
        assert updated.json()["linked_feature_id"] == "crud-b"
        stale_building = client.put(
            f"{module}/buildings/{building['id']}",
            json={
                "expected_revision": 1,
                "route_id": route["id"],
                "area_id": root_body["id"],
                "parcel_ref": "stale",
                "source_id": str(point_a),
                "feature_id": "crud-a",
            },
        )
        assert stale_building.status_code == 409, stale_building.text

        area_with_building = client.delete(
            f"{module}/areas/{root_body['id']}",
            params={"expected_revision": root_body["revision"]},
        )
        assert area_with_building.status_code == 409, area_with_building.text
        retired = client.delete(
            f"{module}/buildings/{building['id']}", params={"expected_revision": 2}
        )
        assert retired.status_code == 204, retired.text
        root_deleted = client.delete(
            f"{module}/areas/{root_body['id']}",
            params={"expected_revision": root_body["revision"]},
        )
        assert root_deleted.status_code == 409, root_deleted.text

        protected = _create_building(
            client,
            module,
            route_id=route["id"],
            source_id=point_a,
            feature_id="crud-a",
            parcel_ref="OFFICIAL",
        )
        rule = _create_rule(
            client, module, version="CRUD-OFFICIAL-019", authoritative=True
        )
        with get_admin_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO house_numbering.address_numbers (
                        id,organization_id,project_id,building_id,route_id,number_text,kind,
                        side,measure_m,rule_id,revision,created_by_actor_id,updated_by_actor_id,
                        created_at,updated_at
                    ) VALUES (
                        :id,:org,:project,:building,:route,'88','approved',
                        'right',10,:rule,1,:actor,:actor,now(),now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "org": world.organization_id,
                    "project": world.project_id,
                    "building": UUID(protected["id"]),
                    "route": UUID(route["id"]),
                    "rule": UUID(rule["id"]),
                    "actor": world.owner_user_id,
                },
            )
        protected_delete = client.delete(
            f"{module}/buildings/{protected['id']}", params={"expected_revision": 1}
        )
        assert protected_delete.status_code == 409, protected_delete.text

    with get_admin_engine().connect() as connection:
        actions = set(
            connection.execute(
                text(
                    """
                    SELECT action FROM audit.audit_events
                    WHERE organization_id=:org
                      AND action IN (
                        'house_numbering.area.update',
                        'house_numbering.area.delete',
                        'house_numbering.building.update',
                        'house_numbering.building.retire'
                      )
                    """
                ),
                {"org": world.organization_id},
            ).scalars()
        )
    assert actions == {
        "house_numbering.area.update",
        "house_numbering.area.delete",
        "house_numbering.building.update",
        "house_numbering.building.retire",
    }
