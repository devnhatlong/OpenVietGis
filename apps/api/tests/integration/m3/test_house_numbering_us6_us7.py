"""Real PostGIS acceptance for House Numbering US6-US7."""

from __future__ import annotations

import io
import json
import zipfile
from uuid import uuid4

import ezdxf
from modules.house_numbering.migrate import upgrade as migrate_house_numbering
from sqlalchemy import text

from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.m3.test_house_numbering_runtime import _seed_source
from tests.integration.spatial.test_sources import _client


def _seed_world(world):
    route_source = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_route_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="route-main",
        wkt="LINESTRING(0 0,200 0)",
        extent={"min_x": 0, "min_y": 0, "max_x": 200, "max_y": 0, "crs_code": 3857},
    )
    org_base = f"/api/v1/organizations/{world.organization_id}"
    proj_base = f"{org_base}/projects/{world.project_id}"
    module_base = f"{proj_base}/modules/house-numbering"
    with _client(world.owner_user_id) as client:
        manifest = client.post(f"{org_base}/extensions/official/house_numbering/register")
        assert manifest.status_code == 201, manifest.text
        activated = client.post(
            f"{proj_base}/extensions/activations",
            json={"manifest_id": manifest.json()["id"]},
        )
        assert activated.status_code == 201, activated.text
        rule = client.post(
            f"{module_base}/rules",
            json={
                "version": "us6-us7-rule",
                "status": "authoritative",
                "authority_ref": "SYNTHETIC-AUTHORITY-US6",
                "left_odd": True,
                "suffix_style": "letters",
                "max_distance_m": 100,
            },
        )
        assert rule.status_code == 201, rule.text
        route = client.post(
            f"{module_base}/routes",
            json={
                "name": "Tuyến kiểm thử hồ sơ",
                "route_type": "street",
                "source_id": str(route_source),
                "feature_id": "route-main",
                "direction_state": "forward",
                "source_label": "synthetic integration fixture",
                "status": "confirmed",
            },
        )
        assert route.status_code == 201, route.text
        route_id = route.json()["id"]
        buildings = {}
        for index, name in enumerate("abcdef", start=1):
            x = 10 + (index - 1) * 20
            source = _seed_source(
                organization_id=world.organization_id,
                project_id=world.project_id,
                reference_key=f"hn_doc_{name}_{uuid4().hex[:8]}",
                family="Point",
                feature_id=f"house-{name}",
                wkt=f"POINT({x} -5)",
                extent={
                    "min_x": x,
                    "min_y": -5,
                    "max_x": x,
                    "max_y": -5,
                    "crs_code": 3857,
                },
            )
            response = client.post(
                f"{module_base}/buildings",
                json={
                    "route_id": route_id,
                    "source_id": str(source),
                    "feature_id": f"house-{name}",
                    "eligibility": "eligible",
                    "parcel_ref": f"PARCEL-{name.upper()}",
                },
            )
            assert response.status_code == 201, response.text
            buildings[name] = response.json()["id"]

    with get_admin_engine().begin() as connection:
        for index, name in enumerate("abcdef", start=1):
            connection.execute(
                text(
                    """
                    INSERT INTO house_numbering.address_numbers (
                        id,organization_id,project_id,building_id,route_id,number_text,kind,
                        side,measure_m,rule_id,revision,created_by_actor_id,updated_by_actor_id,
                        created_at,updated_at
                    ) VALUES (
                        :id,:org,:project,:building,:route,:number,'approved','right',:measure,
                        :rule,1,:actor,:actor,now(),now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "org": world.organization_id,
                    "project": world.project_id,
                    "building": buildings[name],
                    "route": route_id,
                    "number": str(100 + (index - 1) * 2),
                    "measure": 10 + (index - 1) * 20,
                    "rule": rule.json()["id"],
                    "actor": world.owner_user_id,
                },
            )
    return org_base, proj_base, module_base, route_id, buildings


def test_house_numbering_us6_documents_and_us7_search_exports_privacy(
    migrated_database: None,
) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    _, _, module_base, _, buildings = _seed_world(world)

    with _client(world.owner_user_id) as client:
        docx = client.post(
            f"{module_base}/documents",
            json={
                "building_id": buildings["a"],
                "doc_type": "certificate",
                "output_format": "docx",
                "template_revision": "tpl-2026.1",
                "template_verified": True,
            },
        )
        assert docx.status_code == 201, docx.text
        assert docx.json()["status"] == "official"
        docx_id = docx.json()["id"]
        downloaded_docx = client.get(f"{module_base}/documents/{docx_id}/download")
        assert downloaded_docx.status_code == 200, downloaded_docx.text
        assert downloaded_docx.content[:2] == b"PK"
        with zipfile.ZipFile(io.BytesIO(downloaded_docx.content)) as archive:
            names = set(archive.namelist())
            assert "word/document.xml" in names
            assert {
                "word/media/map1.png",
                "word/media/map2.png",
                "word/media/map3.png",
            } <= names

        pdf = client.post(
            f"{module_base}/documents",
            json={
                "building_id": buildings["b"],
                "doc_type": "certificate",
                "output_format": "pdf",
                "template_revision": "tpl-2026.1",
                "template_verified": True,
            },
        )
        assert pdf.status_code == 201, pdf.text
        downloaded_pdf = client.get(f"{module_base}/documents/{pdf.json()['id']}/download")
        assert downloaded_pdf.status_code == 200, downloaded_pdf.text
        assert downloaded_pdf.content.startswith(b"%PDF")

        reissue = client.post(
            f"{module_base}/documents",
            json={
                "building_id": buildings["a"],
                "doc_type": "certificate",
                "output_format": "pdf",
                "template_revision": "tpl-2026.2",
                "template_verified": True,
                "replaces_document_id": docx_id,
            },
        )
        assert reissue.status_code == 201, reissue.text
        history = client.get(f"{module_base}/buildings/{buildings['a']}/documents")
        assert history.status_code == 200, history.text
        statuses = {item["status"] for item in history.json()["items"]}
        assert {"official", "reissue_required"} <= statuses

        search = client.get(f"{module_base}/search", params={"query": "100"})
        assert search.status_code == 200, search.text
        assert any(item["building_id"] == buildings["a"] for item in search.json()["items"])
        coordinate = client.get(
            f"{module_base}/search",
            params={
                "x": 10,
                "y": -5,
                "crs_code": 3857,
                "max_distance": 20,
            },
        )
        assert coordinate.status_code == 200, coordinate.text
        assert coordinate.json()["items"][0]["building_id"] == buildings["a"]

        private = client.post(
            f"{module_base}/private-households",
            json={
                "building_id": buildings["a"],
                "purpose": "Synthetic field verification",
                "consent": True,
                "lawful_basis_ref": "SYNTH-CONSENT-01",
                "protected_data": {
                    "name": "demo_resident",
                    "contact": "demo_contact",
                    "record_ref": "SYNTH-001",
                },
            },
        )
        assert private.status_code == 201, private.text
        private_read = client.get(
            f"{module_base}/buildings/{buildings['a']}/private-households",
            params={"purpose": "Synthetic authorized lookup"},
        )
        assert private_read.status_code == 200, private_read.text
        assert private_read.json()["items"][0]["protected_data"]["record_ref"] == "SYNTH-001"

        public_export = client.post(
            f"{module_base}/exports",
            json={
                "fields": [
                    "building_id",
                    "house_number",
                    "route_name",
                    "parcel_number",
                ],
                "output_format": "csv",
                "include_private": False,
            },
        )
        assert public_export.status_code == 201, public_export.text
        public_download = client.get(
            f"{module_base}/exports/{public_export.json()['artifact_id']}/download"
        )
        assert public_download.status_code == 200, public_download.text
        public_text = public_download.content.decode("utf-8-sig")
        for private_value in ("demo_resident", "demo_contact", "SYNTH-001"):
            assert private_value not in public_text

        denied_field = client.post(
            f"{module_base}/exports",
            json={
                "fields": ["house_number", "name"],
                "output_format": "csv",
                "include_private": False,
            },
        )
        assert denied_field.status_code == 422, denied_field.text

        private_export = client.post(
            f"{module_base}/exports",
            json={
                "fields": ["building_id", "name", "contact", "record_ref"],
                "output_format": "csv",
                "include_private": True,
                "purpose": "Synthetic authorized handover",
            },
        )
        assert private_export.status_code == 201, private_export.text
        private_artifact_id = private_export.json()["artifact_id"]
        private_download = client.get(f"{module_base}/exports/{private_artifact_id}/download")
        assert private_download.status_code == 200, private_download.text
        assert b"SYNTH-001" in private_download.content

        dxf = client.post(
            f"{module_base}/exports",
            json={
                "fields": ["building_id", "house_number"],
                "output_format": "dxf",
                "include_private": False,
            },
        )
        assert dxf.status_code == 201, dxf.text
        dxf_download = client.get(f"{module_base}/exports/{dxf.json()['artifact_id']}/download")
        assert dxf_download.status_code == 200, dxf_download.text
        dxf_doc = ezdxf.read(io.StringIO(dxf_download.content.decode("utf-8")))
        assert len(list(dxf_doc.modelspace().query("POINT"))) >= 6

        geojson = client.post(
            f"{module_base}/exports",
            json={
                "fields": ["building_id", "house_number"],
                "output_format": "geojson",
                "include_private": False,
            },
        )
        assert geojson.status_code == 201, geojson.text
        geojson_download = client.get(
            f"{module_base}/exports/{geojson.json()['artifact_id']}/download"
        )
        assert geojson_download.status_code == 200, geojson_download.text
        payload = json.loads(geojson_download.content)
        assert payload["type"] == "FeatureCollection"
        assert len(payload["features"]) >= 6

    with get_admin_engine().begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO org.resource_grants (
                    id,organization_id,subject_kind,membership_id,scope_kind,project_id,role,
                    created_at,created_by_actor_type,created_by_actor_id
                ) VALUES (
                    :id,:org,'membership',:membership,'project',:project,'viewer',
                    now(),'human',:actor
                )
                """
            ),
            {
                "id": uuid4(),
                "org": world.organization_id,
                "membership": world.member_membership_id,
                "project": world.project_id,
                "actor": world.owner_user_id,
            },
        )

    with _client(world.member_user_id, raise_server_exceptions=False) as viewer:
        public_read = viewer.get(f"{module_base}/search", params={"query": "100"})
        assert public_read.status_code == 200, public_read.text

        private_read_denied = viewer.get(
            f"{module_base}/buildings/{buildings['a']}/private-households",
            params={"purpose": "Synthetic denied lookup"},
        )
        assert private_read_denied.status_code in {403, 404}, private_read_denied.text

        private_export_denied = viewer.post(
            f"{module_base}/exports",
            json={
                "fields": ["building_id", "name"],
                "output_format": "csv",
                "include_private": True,
                "purpose": "Synthetic denied export",
            },
        )
        assert private_export_denied.status_code in {403, 404}, private_export_denied.text

        leaked_download = viewer.get(f"{module_base}/exports/{private_artifact_id}/download")
        assert leaked_download.status_code in {403, 404}, leaked_download.text

    with get_admin_engine().connect() as connection:
        log_count = connection.execute(
            text(
                """
                SELECT count(*) FROM house_numbering.access_log
                WHERE organization_id=:org AND project_id=:project
                """
            ),
            {"org": world.organization_id, "project": world.project_id},
        ).scalar_one()
        assert log_count >= 2
