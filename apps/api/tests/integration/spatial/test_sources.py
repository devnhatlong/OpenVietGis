"""US1 independent source registration and native PostGIS metadata acceptance.

HTTP calls use a real R002 session/CSRF and the restricted runtime database role.
Admin queries are read-only or test setup, never a registration implementation.
Expected controls are frozen literals, not values read from the registry under test.
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from openvietgis_api.adapters.persistence.db import get_engine
from openvietgis_api.adapters.persistence.spatial_repository import SqlSpatialRepository
from openvietgis_api.main import create_app
from openvietgis_api.security.sessions import issue_session_token
from tests.fixtures.db_admin import get_admin_engine
from tests.fixtures.identity_tenancy import AccessWorld, seed_access_world

FIELDS = [
    ("fld_feature_code", "Feature code", 0, "text", False),
    ("fld_name", "Name", 1, "text", False),
    ("fld_rank", "Rank", 2, "integer", False),
    ("fld_measure", "Measure", 3, "decimal", True),
    ("fld_active", "Active", 4, "boolean", False),
    ("fld_observed_at", "Observed at", 5, "timestamp", True),
    ("fld_note", "Note", 6, "text", True),
]

# Counts/bounds from reference-fixture-profile and independent control tables.
# The projected CRS bounds are NOT transformed by the system under test.
READY = [
    ("reference_points_4326", 4326, "Point", 4000, (106.6, 10.7, 106.699, 10.739)),
    ("reference_lines_4326", 4326, "LineString", 3000, (106.6, 10.7, 106.6996, 10.7292)),
    ("reference_polygons_4326", 4326, "Polygon", 3000, (106.6, 10.7, 106.6996, 10.7294)),
    (
        "reference_points_3857",
        3857,
        "Point",
        3,
        (11866657.718562961, 1198103.040560261, 11928662.674934816, 2357927.646019978),
    ),
    (
        "reference_points_4756",
        4756,
        "Point",
        5,
        (106.883111111111, 20.8355, 108.059805555556, 21.414472222222),
    ),
    (
        "reference_points_4326_quang_ninh",
        4326,
        "Point",
        5,
        (106.885, 20.8345, 108.061694444444, 21.413472222222),
    ),
    (
        "reference_points_4756_hvs",
        4756,
        "Point",
        4,
        (107.154322222222, 20.711691666667, 107.167861111111, 20.722058333333),
    ),
    (
        "reference_points_4326_hvs",
        4326,
        "Point",
        4,
        (107.156197222222, 20.710688888889, 107.169736111111, 20.721055555556),
    ),
    ("reference_points_5899", 5899, "Point", 4, (437957.55, 2291039.83, 439365.92, 2292185.83)),
    ("reference_points_4326_webmerc_out_of_area", 4326, "Point", 1, (0.0, 86.0, 0.0, 86.0)),
    ("reference_empty_4326", 4326, "Point", 0, None),
]

# key, reason, declared/stored CRS, inspected family/dimensions, raw geometry states
NEGATIVE = [
    ("reference_unknown_crs", "MISSING_CRS", None, None, "Point", "XY", ("present",)),
    (
        "reference_conflicting_metadata",
        "GEOMETRY_FAMILY_MISMATCH",
        4326,
        4326,
        "LineString",
        "XY",
        ("present",),
    ),
    (
        "reference_unsupported_dimensions",
        "UNSUPPORTED_DIMENSIONS",
        4326,
        4326,
        "Point",
        "XYZ",
        ("unsupported",),
    ),
    (
        "reference_unsupported_dimensions_m",
        "UNSUPPORTED_DIMENSIONS",
        4326,
        4326,
        "Point",
        "XYM",
        ("unsupported",),
    ),
    (
        "reference_mixed_geometry",
        "UNSUPPORTED_GEOMETRY",
        4326,
        4326,
        "mixed",
        "XY",
        ("present", "present"),
    ),
    (
        "reference_unsupported_family",
        "UNSUPPORTED_GEOMETRY",
        4326,
        4326,
        "unsupported",
        "XY",
        ("unsupported",),
    ),
    ("reference_null_geometry", "NULL_GEOMETRY", 4326, None, "unknown", "unknown", ("absent",)),
    ("reference_empty_geometry", "EMPTY_GEOMETRY", 4326, 4326, "Point", "XY", ("empty",)),
    ("reference_invalid_geometry", "INVALID_GEOMETRY", 4326, 4326, "Polygon", "XY", ("invalid",)),
    ("reference_axis_conflict", "AXIS_CONFLICT", 4326, 4326, "Point", "XY", ("invalid",)),
    (
        "reference_out_of_domain",
        "COORDINATE_OUT_OF_DOMAIN",
        4326,
        4326,
        "Point",
        "XY",
        ("invalid",),
    ),
    ("reference_definition_only_crs", "UNSUPPORTED_CRS", 3405, 3405, "Point", "XY", ("present",)),
    (
        "reference_wrapping_extent",
        "EXTENT_WRAP_UNSUPPORTED",
        4326,
        4326,
        "LineString",
        "XY",
        ("present",),
    ),
    ("reference_correctable_crs", "CRS_MISMATCH", 3857, 4326, "Point", "XY", ("present",)),
]


def _client(user: UUID, *, raise_server_exceptions: bool = True) -> TestClient:
    session_id = uuid4()
    token, digest = issue_session_token(session_id)
    with get_admin_engine().begin() as connection:
        link = connection.execute(
            text("SELECT id FROM identity.identity_links WHERE user_id=:user"), {"user": user}
        ).scalar_one()
        connection.execute(
            text("""
                INSERT INTO identity.web_sessions (
                    id,user_id,identity_link_id,secret_hash,issued_at,expires_at
                ) VALUES (:id,:user,:link,:digest,now(),now()+interval '1 hour')
            """),
            {"id": session_id, "user": user, "link": link, "digest": digest},
        )
    client = TestClient(create_app(), raise_server_exceptions=raise_server_exceptions)
    client.cookies.set("ovg_session", token)
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    client.headers["X-OpenVietGIS-CSRF"] = csrf.json()["token"]
    return client


def _path(world: AccessWorld, project: UUID | None = None) -> str:
    return (
        f"/api/v1/organizations/{world.organization_id}/projects/"
        f"{project or world.project_id}/spatial/sources"
    )


def _register(client: TestClient, path: str, key: str, name: str = " Reference "):
    response = client.post(path, json={"reference_key": key, "name": name})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["resource_type"] == "data_source"
    assert result["prior_revision"] is None
    assert result["new_revision"]["catalog_revision"] == 1
    assert result["lifecycle"] == "active"
    UUID(result["resource_id"])
    UUID(result["change_id"])
    return result


def _get(client: TestClient, path: str, source_id: str):
    response = client.get(f"{path}/{source_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _crs(profile, code: int | None) -> None:
    if code is None:
        assert profile is None
        return
    assert profile["authority"] == "EPSG" and profile["code"] == code
    assert profile["coordinate_order"] == "xy"
    if code in (4326, 4756):
        assert profile["native_axes"] == ["latitude", "longitude"]
        assert (profile["x_axis"], profile["y_axis"], profile["unit"]) == (
            "longitude",
            "latitude",
            "degree",
        )
    else:
        assert profile["native_axes"] == ["easting", "northing"]
        assert (profile["x_axis"], profile["y_axis"], profile["unit"]) == (
            "easting",
            "northing",
            "metre",
        )
    assert profile["disposition"] == ("definition_only" if code == 3405 else "readable")


def _metadata(world: AccessWorld, source, mutation, key: str, family: str, dimensions: str):
    assert source["id"] == mutation["resource_id"]
    assert source["organization_id"] == mutation["organization_id"] == str(world.organization_id)
    assert source["project_id"] == mutation["project_id"] == str(world.project_id)
    assert source["name"] == "Reference"
    assert source["kind"] == "reference_fixture"
    assert source["lifecycle"] == "active" and source["retired_at"] is None
    provenance = source["provenance"]
    assert provenance["reference_key"] == key
    assert provenance["fixture_version"] == "r003-reference-v1"
    assert provenance["source_asset_id"] is None
    for token in ("manifest_digest",):
        assert re.fullmatch("[0-9a-f]{64}", provenance[token])
        assert provenance[token] != "0" * 64
    for token in ("content_revision", "schema_revision"):
        assert re.fullmatch("[0-9a-f]{64}", source[token])
        assert source[token] == mutation["new_revision"][token]
        assert source[token] != "0" * 64
    assert source["catalog_revision"] == 1
    schema = source["schema"]
    assert schema["state"] == "known"
    assert schema["schema_revision"] == source["schema_revision"]
    assert schema["geometry_family"] == family
    assert schema["dimensions"] == dimensions
    assert [
        (f["field_id"], f["name"], f["ordinal"], f["type"], f["nullable"]) for f in schema["fields"]
    ] == FIELDS
    with get_admin_engine().begin() as connection:
        evidence = connection.execute(
            text("""
                SELECT c.operation,c.actor_id,c.prior_revision,c.new_revision,a.actor_id
                  FROM spatial.catalog_changes c
                  JOIN audit.audit_events a ON a.id=c.audit_event_id
                 WHERE c.id=:change AND c.organization_id=:org AND c.project_id=:project
                   AND c.resource_id=:source
            """),
            {
                "change": mutation["change_id"],
                "org": world.organization_id,
                "project": world.project_id,
                "source": source["id"],
            },
        ).one()
    assert tuple(evidence) == (
        "register_source",
        world.owner_user_id,
        None,
        mutation["new_revision"],
        world.owner_user_id,
    )


def _rows(source_id: str):
    with get_admin_engine().begin() as connection:
        return (
            connection.execute(
                text("""
                SELECT feature_id,geometry_state,ST_SRID(geometry) AS srid,
                       ST_Zmflag(geometry) AS zm,ST_GeometryType(geometry) AS family,
                       ST_IsEmpty(geometry) AS empty,ST_IsValid(geometry) AS valid,
                       ST_AsEWKB(geometry) AS ewkb,attributes,content_revision,schema_revision
                  FROM spatial.reference_features WHERE source_id=:id ORDER BY feature_id
            """),
                {"id": source_id},
            )
            .mappings()
            .all()
        )


@pytest.mark.parametrize(
    ("key", "code", "family", "count", "bounds"), READY, ids=[case[0] for case in READY]
)
def test_ready_native_metadata(migrated_database: None, key, code, family, count, bounds) -> None:
    world = seed_access_world()
    with get_engine().connect() as connection:
        role = connection.execute(
            text("""
            SELECT current_user,r.rolsuper,r.rolbypassrls
              FROM pg_roles r WHERE r.rolname=current_user
        """)
        ).one()
        assert tuple(role) == ("openvietgis_runtime", False, False)
    with _client(world.owner_user_id) as client:
        path = _path(world)
        created = _register(client, path, key)
        source = _get(client, path, created["resource_id"])
        assert client.get(path).json()["items"] == [source]
    _metadata(world, source, created, key, family, "XY")
    assert source["validation_state"] == created["validation_state"] == "ready"
    assert source["validation_reason"] is created["validation_reason"] is None
    _crs(source["source_crs"], code)
    _crs(source["stored_crs"], code)
    assert source["feature_count_state"] == "known" and source["feature_count"] == count
    rows = _rows(source["id"])
    assert len(rows) == count
    assert all(
        row["srid"] == code
        and row["zm"] == 0
        and row["valid"]
        and not row["empty"]
        and row["geometry_state"] == "present"
        and row["family"] == f"ST_{family}"
        and row["schema_revision"] == source["schema_revision"]
        and row["content_revision"] == source["content_revision"]
        for row in rows
    )
    if bounds is None:
        assert source["extent_state"] == "empty" and source["extent"] is None
        return
    extent = source["extent"]
    assert source["extent_state"] == "available"
    extent_ref = extent["coordinate_reference"]
    assert extent_ref == {
        name: source["stored_crs"][name]
        for name in ("authority", "code", "coordinate_order", "x_axis", "y_axis", "unit")
    }
    actual = tuple(extent[name] for name in ("min_x", "min_y", "max_x", "max_y"))
    assert actual == pytest.approx(bounds, rel=0, abs=1e-7)
    with get_admin_engine().begin() as connection:
        sql_bounds = connection.execute(
            text("""
            SELECT ST_XMin(box),ST_YMin(box),ST_XMax(box),ST_YMax(box)
            FROM (SELECT ST_Extent(geometry) AS box FROM spatial.reference_features
                  WHERE source_id=:id) AS bounds
        """),
            {"id": source["id"]},
        ).one()
    assert tuple(sql_bounds) == pytest.approx(bounds, rel=0, abs=1e-7)
    if key == "reference_points_4326":
        assert rows[0]["attributes"] == {
            "fld_feature_code": "point-000001",
            "fld_name": "Point 000001",
            "fld_rank": 1,
            "fld_measure": "0",
            "fld_active": False,
            "fld_observed_at": "2025-01-01T00:00:00Z",
            "fld_note": "",
        }
        assert rows[4]["attributes"]["fld_note"] is None
        assert rows[6]["attributes"]["fld_measure"] is None
        assert rows[999]["attributes"]["fld_rank"] == 0


@pytest.mark.parametrize(
    ("key", "reason", "declared", "stored", "family", "dimensions", "states"),
    NEGATIVE,
    ids=[case[0] for case in NEGATIVE],
)
def test_nonready_fixture_preserves_truthful_metadata_and_native_geometry(
    migrated_database: None, key, reason, declared, stored, family, dimensions, states
) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        created = _register(client, _path(world), key)
        source = _get(client, _path(world), created["resource_id"])
    _metadata(world, source, created, key, family, dimensions)
    assert source["validation_state"] in ("invalid", "not_ready")
    assert created["validation_state"] == source["validation_state"]
    assert created["validation_reason"] == source["validation_reason"]
    assert source["validation_reason"]["code"] == reason
    assert source["extent_state"] == "unavailable" and source["extent"] is None
    assert source["feature_count_state"] == "known" and source["feature_count"] == len(states)
    _crs(source["source_crs"], declared)
    _crs(source["stored_crs"], stored)
    rows = _rows(source["id"])
    assert tuple(row["geometry_state"] for row in rows) == states
    assert all(row["srid"] == (stored or 0) if row["ewkb"] else row["srid"] is None for row in rows)
    if dimensions in ("XYZ", "XYM"):
        assert rows[0]["zm"] == (2 if dimensions == "XYZ" else 1)
    if reason == "NULL_GEOMETRY":
        assert rows[0]["ewkb"] is None
    if reason == "EMPTY_GEOMETRY":
        assert rows[0]["empty"] is True
    if reason == "INVALID_GEOMETRY":
        assert rows[0]["valid"] is False
    if key == "reference_unsupported_family":
        assert rows[0]["family"] == "ST_MultiPoint"
    if key == "reference_mixed_geometry":
        assert {row["family"] for row in rows} == {"ST_Point", "ST_LineString"}
    assert all(
        row["content_revision"] == source["content_revision"]
        and row["schema_revision"] == source["schema_revision"]
        for row in rows
    )
    # Wrong axes or impossible native coordinates must stay raw; do not swap,
    # wrap, clip, assign a guessed SRID or otherwise "repair" the manifest.
    if key in ("reference_axis_conflict", "reference_out_of_domain"):
        with get_admin_engine().begin() as connection:
            point = connection.execute(
                text("""
                SELECT ST_X(geometry),ST_Y(geometry) FROM spatial.reference_features
                WHERE source_id=:source
            """),
                {"source": source["id"]},
            ).one()
        expected = (
            (20.710688888889, 107.160886111111)
            if (key == "reference_axis_conflict")
            else (106.6, 91.0)
        )
        assert tuple(point) == pytest.approx(expected, rel=0, abs=1e-10)


def _error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["code"] == code


def _counts(world: AccessWorld):
    with get_admin_engine().begin() as connection:
        result = connection.execute(
            text("""
            SELECT (SELECT count(*) FROM spatial.data_sources WHERE project_id=:project),
                   (SELECT count(*) FROM spatial.source_fields WHERE project_id=:project),
                   (SELECT count(*) FROM spatial.reference_features WHERE project_id=:project),
                   (SELECT count(*) FROM spatial.catalog_changes WHERE project_id=:project),
                   (SELECT count(*) FROM audit.audit_events WHERE organization_id=:org
                       AND resource_type='data_source')
        """),
            {"project": world.project_id, "org": world.organization_id},
        ).one()
    return tuple(result)


def test_binding_rename_retire_and_rejections_leave_only_material_evidence(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    path = _path(world)
    with _client(world.owner_user_id) as client:
        _error(
            client.post(path, json={"reference_key": "unknown_fixture", "name": "X"}),
            422,
            "UNKNOWN_REFERENCE_KEY",
        )
        assert _counts(world) == (0, 0, 0, 0, 0)
        first = _register(client, path, "reference_points_5899")
        source_id = first["resource_id"]
        detail_path = f"{path}/{source_id}"
        original = _rows(source_id)
        _error(
            client.post(path, json={"reference_key": "reference_points_5899", "name": "Other"}),
            409,
            "SOURCE_ALREADY_REGISTERED",
        )
        _error(
            client.patch(detail_path, json={"expected_revision": 1, "name": " Reference "}),
            422,
            "NO_CHANGES",
        )
        renamed = client.patch(detail_path, json={"expected_revision": 1, "name": "New name"})
        assert renamed.status_code == 200, renamed.text
        revision = renamed.json()["new_revision"]
        assert revision == {**first["new_revision"], "catalog_revision": 2}
        assert _get(client, path, source_id)["name"] == "New name"
        _error(
            client.patch(detail_path, json={"expected_revision": 1, "name": "New name"}),
            409,
            "STALE_CATALOG_REVISION",
        )
        assert _counts(world) == (1, 7, 4, 2, 2)
        retired = client.post(f"{detail_path}/retire", json={"expected_revision": 2})
        assert retired.status_code == 200, retired.text
        assert retired.json()["lifecycle"] == "retired"
        assert retired.json()["new_revision"] == {**revision, "catalog_revision": 3}
        assert client.get(detail_path).status_code == 404
        assert client.get(path).json()["items"] == []
        _error(
            client.post(path, json={"reference_key": "reference_points_5899", "name": "Again"}),
            409,
            "SOURCE_ALREADY_REGISTERED",
        )
    assert _counts(world) == (1, 7, 4, 3, 3)
    assert _rows(source_id) == original


def test_source_retirement_rejects_active_layer_without_side_effect(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    path = _path(world)
    with _client(world.owner_user_id) as client:
        result = _register(client, path, "reference_empty_4326")
        source_id = result["resource_id"]
        prior = _get(client, path, source_id)
        # US2 layer creation is intentionally not needed for this US1 guard test.
        with get_admin_engine().begin() as connection:
            connection.execute(
                text("""
                INSERT INTO spatial.layers (
                    id,organization_id,project_id,source_id,name,lifecycle,
                    layer_revision,created_at,updated_at
                ) VALUES (:id,:org,:project,:source,'Dependency','active',1,now(),now())
            """),
                {
                    "id": uuid4(),
                    "org": world.organization_id,
                    "project": world.project_id,
                    "source": source_id,
                },
            )
        _error(
            client.post(f"{path}/{source_id}/retire", json={"expected_revision": 1}),
            409,
            "ACTIVE_LAYER_DEPENDENCIES",
        )
        assert _get(client, path, source_id) == prior
    assert _counts(world) == (1, 7, 0, 1, 1)


def test_correction_requires_independent_evidence_and_never_rewrites_geometry(
    migrated_database: None,
) -> None:
    world = seed_access_world()
    path = _path(world)
    with _client(world.owner_user_id) as client:
        first = _register(client, path, "reference_correctable_crs")
        source_id = first["resource_id"]
        prior = _get(client, path, source_id)
        before = _rows(source_id)
        assert prior["validation_reason"]["code"] == "CRS_MISMATCH"
        detail = f"{path}/{source_id}"
        _error(
            client.patch(
                detail,
                json={
                    "expected_revision": 1,
                    "declared_crs": {"authority": "EPSG", "code": 4756, "coordinate_order": "xy"},
                },
            ),
            422,
            "CRS_CORRECTION_UNVERIFIED",
        )
        assert _get(client, path, source_id) == prior and _rows(source_id) == before
        assert _counts(world) == (1, 7, 1, 1, 1)
        corrected = client.patch(
            detail,
            json={
                "expected_revision": 1,
                "declared_crs": {"authority": "EPSG", "code": 4326, "coordinate_order": "xy"},
            },
        )
        assert corrected.status_code == 200, corrected.text
        result = corrected.json()
        assert result["prior_revision"] == first["new_revision"]
        assert result["new_revision"]["catalog_revision"] == 2
        assert result["new_revision"]["schema_revision"] == first["new_revision"]["schema_revision"]
        assert (
            result["new_revision"]["content_revision"] != first["new_revision"]["content_revision"]
        )
        current = _get(client, path, source_id)
        assert current["validation_state"] == "ready" and current["validation_reason"] is None
        assert current["provenance"] == prior["provenance"]
        _crs(current["source_crs"], 4326)
        _crs(current["stored_crs"], 4326)
        assert current["extent_state"] == "available"
        assert tuple(current["extent"][name] for name in ("min_x", "min_y", "max_x", "max_y")) == (
            pytest.approx(
                (107.160886111111, 20.710688888889, 107.160886111111, 20.710688888889),
                rel=0,
                abs=1e-10,
            )
        )
        after = _rows(source_id)
        assert after[0]["content_revision"] == result["new_revision"]["content_revision"]
        assert after[0]["ewkb"] == before[0]["ewkb"]
        assert after[0]["attributes"] == before[0]["attributes"]
        axis = _register(client, path, "reference_axis_conflict")
        _error(
            client.patch(
                f"{path}/{axis['resource_id']}",
                json={
                    "expected_revision": 1,
                    "declared_crs": {"authority": "EPSG", "code": 4326, "coordinate_order": "xy"},
                },
            ),
            422,
            "CRS_CORRECTION_UNVERIFIED",
        )
    assert _counts(world) == (2, 14, 2, 3, 3)


def test_registration_rolls_back_all_rows_and_audit_when_evidence_fails(
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = seed_access_world()
    original = SqlSpatialRepository.append_change

    def fail_after_append(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("synthetic rollback after catalog and audit evidence")

    with _client(world.owner_user_id, raise_server_exceptions=False) as client:
        with monkeypatch.context() as patch:
            patch.setattr(SqlSpatialRepository, "append_change", fail_after_append)
            response = client.post(
                _path(world),
                json={
                    "reference_key": "reference_points_5899",
                    "name": "Reference",
                },
            )
            assert response.status_code == 500, response.text
        assert _counts(world) == (0, 0, 0, 0, 0)
        assert client.get(_path(world)).json()["items"] == []
        _register(client, _path(world), "reference_points_5899")
    assert _counts(world) == (1, 7, 4, 1, 1)


def test_registration_scope_independent_binding_and_keyset_listing(migrated_database: None) -> None:
    world = seed_access_world()
    sibling = uuid4()
    with get_admin_engine().begin() as connection:
        connection.execute(
            text("""
            INSERT INTO workspace.projects (
                id,organization_id,workspace_id,name,slug,status,created_by_actor_type,
                created_by_actor_id,created_at,updated_at
            ) VALUES (:id,:org,:workspace,'Sibling',:slug,'active','human',:actor,now(),now())
        """),
            {
                "id": sibling,
                "org": world.organization_id,
                "workspace": world.workspace_a_id,
                "slug": f"sibling-{sibling.hex}",
                "actor": world.owner_user_id,
            },
        )
    other = seed_access_world()
    with _client(world.owner_user_id) as client:
        one = _register(client, _path(world), "reference_points_5899")
        two = _register(client, _path(world, sibling), "reference_points_5899")
        three = _register(client, _path(world), "reference_empty_4326")
        assert one["resource_id"] != two["resource_id"]
        assert one["new_revision"] == two["new_revision"]
        a = _get(client, _path(world), one["resource_id"])
        b = _get(client, _path(world, sibling), two["resource_id"])
        assert a["provenance"] == b["provenance"]
        assert client.get(f"{_path(world, sibling)}/{one['resource_id']}").status_code == 404
        assert client.get(f"{_path(world)}/{two['resource_id']}").status_code == 404
        assert client.get(_path(other)).status_code == 404
        ordered = sorted([one["resource_id"], three["resource_id"]])
        first = client.get(_path(world), params={"limit": 1}).json()
        assert [item["id"] for item in first["items"]] == ordered[:1]
        assert first["next_after_id"] == ordered[0]
        last = client.get(
            _path(world),
            params={
                "limit": 1,
                "after_id": first["next_after_id"],
            },
        ).json()
        assert [item["id"] for item in last["items"]] == ordered[1:]
        assert last["next_after_id"] is None
    with _client(world.member_user_id) as member:
        assert member.get(_path(world)).status_code == 403
        assert (
            member.post(
                _path(world),
                json={
                    "reference_key": "reference_points_4326",
                    "name": "Denied",
                },
            ).status_code
            == 403
        )
    assert _counts(world)[:4] == (2, 14, 4, 2)
