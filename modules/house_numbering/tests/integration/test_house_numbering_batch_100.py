"""HN019 acceptance for 100-document batch generation and audit emission."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client

from modules.house_numbering.migrate import upgrade as migrate_house_numbering
from modules.house_numbering.tests.integration.test_house_numbering_runtime import (
    _seed_source,
)


def test_document_batch_100_synthetic_buildings(migrated_database: None) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    line_source = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_batch_route_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="route-batch",
        wkt="LINESTRING(0 0,1000 0)",
        extent={"min_x": 0, "min_y": 0, "max_x": 1000, "max_y": 0, "crs_code": 3857},
    )
    org = f"/api/v1/organizations/{world.organization_id}"
    project = f"{org}/projects/{world.project_id}"
    module = f"{project}/modules/house-numbering"

    with _client(world.owner_user_id) as client:
        manifest = client.post(f"{org}/extensions/official/house_numbering/register")
        assert manifest.status_code == 201, manifest.text
        active = client.post(
            f"{project}/extensions/activations",
            json={"manifest_id": manifest.json()["id"]},
        )
        assert active.status_code == 201, active.text

        rule = client.post(
            f"{module}/rules",
            json={
                "version": "BATCH-100-019",
                "status": "authoritative",
                "authority_ref": "SYNTHETIC-BATCH-AUTHORITY",
                "left_odd": True,
                "suffix_style": "letters",
                "max_distance_m": 100,
            },
        )
        assert rule.status_code == 201, rule.text
        rule_id = UUID(rule.json()["id"])

        route = client.post(
            f"{module}/routes",
            json={
                "name": "Batch 100 route",
                "route_type": "street",
                "source_id": str(line_source),
                "feature_id": "route-batch",
                "direction_state": "forward",
                "source_label": "synthetic batch fixture",
                "status": "confirmed",
            },
        )
        assert route.status_code == 201, route.text
        route_id = UUID(route.json()["id"])

        building_ids: list[UUID] = []
        for index in range(100):
            x = 5 + index * 8
            source_id = _seed_source(
                organization_id=world.organization_id,
                project_id=world.project_id,
                reference_key=f"hn_batch_point_{index}_{uuid4().hex[:8]}",
                family="Point",
                feature_id=f"batch-{index}",
                wkt=f"POINT({x} -3)",
                extent={
                    "min_x": x,
                    "min_y": -3,
                    "max_x": x,
                    "max_y": -3,
                    "crs_code": 3857,
                },
            )
            building = client.post(
                f"{module}/buildings",
                json={
                    "route_id": str(route_id),
                    "source_id": str(source_id),
                    "feature_id": f"batch-{index}",
                    "parcel_ref": f"BATCH-{index + 1:03d}",
                    "eligibility": "eligible",
                },
            )
            assert building.status_code == 201, building.text
            building_ids.append(UUID(building.json()["id"]))

        with get_admin_engine().begin() as connection:
            for index, building_id in enumerate(building_ids, start=1):
                connection.execute(
                    text(
                        """
                        INSERT INTO house_numbering.address_numbers (
                            id,organization_id,project_id,building_id,route_id,number_text,kind,
                            side,measure_m,rule_id,revision,created_by_actor_id,updated_by_actor_id,
                            created_at,updated_at
                        ) VALUES (
                            :id,:org,:project,:building,:route,:number,'approved',
                            'right',:measure,:rule,1,:actor,:actor,now(),now()
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "org": world.organization_id,
                        "project": world.project_id,
                        "building": building_id,
                        "route": route_id,
                        "number": str(index * 2),
                        "measure": float(index * 8),
                        "rule": rule_id,
                        "actor": world.owner_user_id,
                    },
                )

        batch = client.post(
            f"{module}/documents/batch",
            json={
                "building_ids": [str(value) for value in building_ids],
                "doc_type": "plate",
                "output_format": "pdf",
                "template_revision": "batch-100-v1",
                "template_verified": True,
            },
        )
        assert batch.status_code == 201, batch.text
        items = batch.json()["items"]
        assert len(items) == 100
        assert all(item["status"] == "official" for item in items)
        assert all(item["artifact_id"] for item in items)

        for item in (items[0], items[-1]):
            downloaded = client.get(f"{module}/documents/{item['id']}/download")
            assert downloaded.status_code == 200, downloaded.text
            assert downloaded.content.startswith(b"%PDF")

    with get_admin_engine().connect() as connection:
        document_count = connection.execute(
            text(
                """
                SELECT count(*) FROM house_numbering.documents
                WHERE organization_id=:org AND project_id=:project
                  AND doc_type='plate' AND status='official'
                """
            ),
            {"org": world.organization_id, "project": world.project_id},
        ).scalar_one()
        audit_count = connection.execute(
            text(
                """
                SELECT count(*) FROM audit.audit_events
                WHERE organization_id=:org
                  AND action='house_numbering.document.issue'
                  AND resource_type='house_numbering_document'
                """
            ),
            {"org": world.organization_id},
        ).scalar_one()
    assert document_count == 100
    assert audit_count >= 100
