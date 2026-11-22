"""Real PostGIS acceptance for House Numbering US4-US5."""

from __future__ import annotations

import io
import json
import zipfile
from uuid import uuid4

import shapefile
from PIL import Image
from sqlalchemy import text
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client

from modules.house_numbering.migrate import upgrade as migrate_house_numbering
from modules.house_numbering.tests.integration.test_house_numbering_runtime import (
    _seed_source,
)


def _activate_and_seed(world):
    line_source = _seed_source(
        organization_id=world.organization_id,
        project_id=world.project_id,
        reference_key=f"hn_line_{uuid4().hex[:8]}",
        family="LineString",
        feature_id="route-1",
        wkt="LINESTRING(0 0,200 0)",
        extent={"min_x": 0, "min_y": 0, "max_x": 200, "max_y": 0, "crs_code": 3857},
    )
    org_base = f"/api/v1/organizations/{world.organization_id}"
    proj_base = f"{org_base}/projects/{world.project_id}"
    module_base = f"{proj_base}/modules/house-numbering"
    with _client(world.owner_user_id) as client:
        registered = client.post(
            f"{org_base}/extensions/official/house_numbering/register"
        )
        assert registered.status_code == 201, registered.text
        active = client.post(
            f"{proj_base}/extensions/activations",
            json={"manifest_id": registered.json()["id"]},
        )
        assert active.status_code == 201, active.text
        rule = client.post(
            f"{module_base}/rules",
            json={
                "version": "us4-us5-rule",
                "status": "authoritative",
                "authority_ref": "SYNTHETIC-AUTHORITY",
                "left_odd": True,
                "suffix_style": "letters",
                "max_distance_m": 80,
            },
        )
        assert rule.status_code == 201, rule.text
        route = client.post(
            f"{module_base}/routes",
            json={
                "name": "Tuyến kiểm thử US4-US5",
                "route_type": "street",
                "source_id": str(line_source),
                "feature_id": "route-1",
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
                reference_key=f"hn_pt_{name}_{uuid4().hex[:8]}",
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
            building = client.post(
                f"{module_base}/buildings",
                json={
                    "route_id": route_id,
                    "source_id": str(source),
                    "feature_id": f"house-{name}",
                    "eligibility": "eligible",
                    "parcel_ref": f"P-{name.upper()}",
                },
            )
            assert building.status_code == 201, building.text
            buildings[name] = building.json()["id"]
    return org_base, proj_base, module_base, rule.json()["id"], route_id, buildings


def _minimal_xlsx(rows: list[list[str]]) -> bytes:
    def inline_cell(ref: str, value: str) -> str:
        escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>'

    sheet_rows: list[str] = []
    for row_index, values in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(values, start=1):
            column = chr(ord("A") + col_index - 1)
            cells.append(inline_cell(f"{column}{row_index}", value))
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()


def _point_shapefile_zip(raw_number: str) -> bytes:
    shp = io.BytesIO()
    shx = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POINT)
    writer.field("RAW_NUM", "C", size=64)
    writer.point(10.0, -5.0)
    writer.record(raw_number)
    writer.close()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("evidence.shp", shp.getvalue())
        archive.writestr("evidence.shx", shx.getvalue())
        archive.writestr("evidence.dbf", dbf.getvalue())
    return output.getvalue()


def _post_csv_import(client, module_base, origin, rows, filename):
    mapping = {
        "building_id": "building_id",
        "route_id": "route_id",
        "raw_number": "raw_number",
        "source_reference": "source_reference",
    }
    text_data = "building_id,route_id,raw_number,source_reference\n"
    text_data += "\n".join(",".join(row) for row in rows) + "\n"
    response = client.post(
        f"{module_base}/imports",
        data={
            "source_format": "csv",
            "origin": origin,
            "mapping_json": json.dumps(mapping),
            "default_source_reference": filename,
            "default_confidence": "observed",
        },
        files={"file": (filename, text_data.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response, text_data


def test_house_numbering_us4_import_reconcile_and_us5_offline_progress(
    migrated_database: None,
) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    _, _, module_base, _, route_id, buildings = _activate_and_seed(world)

    with _client(world.owner_user_id) as client:
        cert_rows = [
            (buildings["a"], route_id, "100", "cert-A"),
            (buildings["b"], route_id, "102", "cert-B"),
            (buildings["d"], route_id, "106", "cert-D"),
            (buildings["e"], route_id, "108", "cert-E"),
            (buildings["f"], route_id, "110", "cert-F"),
            ("", route_id, "999", "cert-unmatched"),
        ]
        cert, original_text = _post_csv_import(
            client, module_base, "certificate", cert_rows, "certificate.csv"
        )
        body = cert.json()
        assert body["batch"]["read_count"] == 6
        assert body["batch"]["accepted_count"] == 6
        assert body["batch"]["rejected_count"] == 0
        assert body["replayed"] is False

        mapping = {
            "building_id": "building_id",
            "route_id": "route_id",
            "raw_number": "raw_number",
            "source_reference": "source_reference",
        }
        replay = client.post(
            f"{module_base}/imports",
            data={
                "source_format": "csv",
                "origin": "certificate",
                "mapping_json": json.dumps(mapping),
                "default_source_reference": "certificate.csv",
                "default_confidence": "observed",
            },
            files={
                "file": ("certificate.csv", original_text.encode("utf-8"), "text/csv")
            },
        )
        assert replay.status_code == 201, replay.text
        assert replay.json()["replayed"] is True
        assert replay.json()["batch"]["id"] == body["batch"]["id"]

        _post_csv_import(
            client,
            module_base,
            "cad",
            [
                (buildings["a"], route_id, "100", "cad-A"),
                (buildings["b"], route_id, "104", "cad-B"),
                (buildings["d"], route_id, "106", "cad-D"),
                (buildings["e"], route_id, "108", "cad-E"),
                (buildings["f"], route_id, "110", "cad-F"),
            ],
            "cad.csv",
        )
        _post_csv_import(
            client,
            module_base,
            "survey",
            [
                (buildings["a"], route_id, "100", "survey-A"),
                (buildings["b"], route_id, "102", "survey-B"),
                (buildings["c"], route_id, "200", "survey-C"),
                (buildings["d"], route_id, "106", "survey-D"),
                (buildings["f"], route_id, "112", "survey-F"),
            ],
            "survey.csv",
        )

        rebuilt = client.post(
            f"{module_base}/reconciliation/rebuild",
            json={
                "removed_building_ids": [buildings["d"]],
                "estimated_building_ids": [buildings["c"]],
            },
        )
        assert rebuilt.status_code == 200, rebuilt.text
        classes = {item["case_class"] for item in rebuilt.json()["items"]}
        assert {
            "matched",
            "cad_certificate_mismatch",
            "new_building",
            "no_longer_exists",
            "not_surveyed",
            "number_mismatch",
            "certificate_unmatched",
        } <= classes

        image_buffer = io.BytesIO()
        Image.new("RGB", (16, 16), "white").save(image_buffer, format="PNG")
        photo = client.post(
            f"{module_base}/survey/photos",
            files={"file": ("field.png", image_buffer.getvalue(), "image/png")},
        )
        assert photo.status_code == 201, photo.text
        photo_id = photo.json()["id"]

        assignment = client.post(
            f"{module_base}/assignments",
            json={
                "scope_kind": "route",
                "scope_id": route_id,
                "assignee_actor_id": str(world.owner_user_id),
                "starts_on": "2026-11-01",
                "ends_on": "2026-12-31",
                "target_count": 2,
            },
        )
        assert assignment.status_code == 201, assignment.text

        client_a = str(uuid4())
        client_b = str(uuid4())
        operations = [
            {
                "client_uuid": client_a,
                "building_id": buildings["a"],
                "x": 10,
                "y": -5,
                "crs_code": 3857,
                "photo_artifact_ids": [photo_id],
                "condition": "house",
            },
            {
                "client_uuid": client_b,
                "building_id": buildings["b"],
                "x": 30,
                "y": -5,
                "crs_code": 3857,
                "photo_artifact_ids": [],
                "condition": "vacant",
            },
        ]
        synced = client.post(
            f"{module_base}/survey/sync", json={"operations": operations}
        )
        assert synced.status_code == 200, synced.text
        assert len(synced.json()["applied"]) == 2
        assert synced.json()["conflicts"] == []

        replayed = client.post(
            f"{module_base}/survey/sync", json={"operations": operations}
        )
        assert replayed.status_code == 200, replayed.text
        assert len(replayed.json()["replayed"]) == 2

        pending = client.get(f"{module_base}/surveys", params={"state": "submitted"})
        assert pending.status_code == 200, pending.text
        lookup = {
            str(item["client_uuid"]): (item["id"], item["revision"])
            for item in pending.json()["items"]
        }
        for client_uuid in (client_a, client_b):
            survey_id, revision = lookup[client_uuid]
            reviewed = client.post(
                f"{module_base}/surveys/{survey_id}/review",
                json={"expected_revision": revision, "decision": "accepted"},
            )
            assert reviewed.status_code == 200, reviewed.text

        conflict = client.post(
            f"{module_base}/survey/sync",
            json={"operations": [{**operations[0], "condition": "vacant"}]},
        )
        assert conflict.status_code == 200, conflict.text
        assert conflict.json()["conflicts"][0]["code"] == "CLIENT_UUID_PAYLOAD_CONFLICT"

        progress = client.get(f"{module_base}/progress")
        assert progress.status_code == 200, progress.text
        assert progress.json()["positions"] == 2
        assert progress.json()["completion"] == 100.0

        report = client.get(f"{module_base}/progress/report.xlsx")
        assert report.status_code == 200, report.text
        assert report.content[:2] == b"PK"
        with zipfile.ZipFile(io.BytesIO(report.content)) as archive:
            assert "xl/workbook.xml" in archive.namelist()
            assert "xl/worksheets/sheet1.xml" in archive.namelist()

    with get_admin_engine().connect() as connection:
        batch_count = connection.execute(
            text(
                "SELECT count(*) FROM house_numbering.import_batches "
                "WHERE organization_id=:org AND project_id=:project"
            ),
            {"org": world.organization_id, "project": world.project_id},
        ).scalar_one()
        assert batch_count == 3


def test_house_numbering_import_format_matrix(migrated_database: None) -> None:
    migrate_house_numbering()
    world = seed_access_world()
    _, _, module_base, _, route_id, buildings = _activate_and_seed(world)

    with _client(world.owner_user_id) as client:
        cp1258_text = (
            "building_id,route_id,raw_number,source_reference\n"
            f"{buildings['a']},{route_id},Đ12,CP1258-SRC\n"
        )
        cp1258 = client.post(
            f"{module_base}/imports",
            data={
                "source_format": "csv",
                "origin": "legacy",
                "mapping_json": json.dumps(
                    {
                        "building_id": "building_id",
                        "route_id": "route_id",
                        "raw_number": "raw_number",
                        "source_reference": "source_reference",
                    }
                ),
                "default_source_reference": "cp1258.csv",
                "default_confidence": "observed",
            },
            files={
                "file": (
                    "cp1258.csv",
                    cp1258_text.encode("cp1258"),
                    "text/csv",
                )
            },
        )
        assert cp1258.status_code == 201, cp1258.text
        assert cp1258.json()["batch"]["accepted_count"] == 1
        assert cp1258.json()["batch"]["mapping"]["encoding"] == "cp1258"

        xlsx_data = _minimal_xlsx(
            [
                ["building_id", "route_id", "raw_number", "source_reference"],
                [buildings["b"], route_id, "XLSX-14", "XLSX-SRC"],
            ]
        )
        xlsx = client.post(
            f"{module_base}/imports",
            data={
                "source_format": "xlsx",
                "origin": "certificate",
                "mapping_json": json.dumps(
                    {
                        "building_id": "building_id",
                        "route_id": "route_id",
                        "raw_number": "raw_number",
                        "source_reference": "source_reference",
                    }
                ),
                "default_source_reference": "evidence.xlsx",
                "default_confidence": "authoritative",
            },
            files={
                "file": (
                    "evidence.xlsx",
                    xlsx_data,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert xlsx.status_code == 201, xlsx.text
        assert xlsx.json()["batch"]["accepted_count"] == 1
        assert xlsx.json()["batch"]["rejected_count"] == 0

        shp_data = _point_shapefile_zip("SHP-16")
        shp_base = {
            "source_format": "shapefile_zip",
            "origin": "cad",
            "mapping_json": json.dumps({"raw_number": "RAW_NUM"}),
            "default_source_reference": "evidence.zip",
            "default_confidence": "observed",
        }
        shp_without_crs = client.post(
            f"{module_base}/imports",
            data=shp_base,
            files={"file": ("evidence.zip", shp_data, "application/zip")},
        )
        assert shp_without_crs.status_code == 422, shp_without_crs.text
        shp = client.post(
            f"{module_base}/imports",
            data={**shp_base, "source_crs": "3857"},
            files={"file": ("evidence.zip", shp_data, "application/zip")},
        )
        assert shp.status_code == 201, shp.text
        assert shp.json()["batch"]["accepted_count"] == 1
        assert shp.json()["batch"]["source_crs"] == 3857

        with get_admin_engine().connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                    SELECT raw_number,source_reference
                    FROM house_numbering.evidence
                    WHERE organization_id=:org AND project_id=:project
                      AND source_reference IN ('CP1258-SRC','XLSX-SRC','evidence.zip')
                    ORDER BY source_reference
                    """
                    ),
                    {"org": world.organization_id, "project": world.project_id},
                )
                .mappings()
                .all()
            )
        values = {(row["raw_number"], row["source_reference"]) for row in rows}
        assert ("Đ12", "CP1258-SRC") in values
        assert ("XLSX-14", "XLSX-SRC") in values
        assert ("SHP-16", "evidence.zip") in values
