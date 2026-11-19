"""Actual HTTP parsing/context/encoding, with no database connection allowed."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from openvietgis_api.adapters.http.errors import install_error_handlers
from openvietgis_api.adapters.http.map_viewport import router
from openvietgis_api.adapters.http.security import (
    AuthenticatedRequest,
    authenticate_request,
    get_db_session,
)
from openvietgis_api.adapters.persistence.map_viewport import SqlMapViewportRepository
from openvietgis_api.domains.authorization.context import Actor
from openvietgis_api.domains.maps.viewport import MapReadUnavailableError
from openvietgis_api.domains.spatial.crs import get_coordinate_reference

ORG, PROJECT, LAYER, ACTOR = (uuid4() for _ in range(4))
BASE = f"/organizations/{ORG}/projects/{PROJECT}/layers/{LAYER}"


@pytest.fixture
def http(monkeypatch):
    calls = []
    app = FastAPI()
    app.include_router(router)
    install_error_handlers(app)

    @app.exception_handler(MapReadUnavailableError)
    def unavailable(request, exception):
        return JSONResponse(
            status_code=503,
            content={"code": "MAP_READ_UNAVAILABLE", "detail": "Map read unavailable; retry."},
        )

    def authentication():
        return AuthenticatedRequest(Actor("human", ACTOR, "Map contract"), None, None)

    def no_database():
        with Session() as session:
            yield session

    app.dependency_overrides[authenticate_request] = authentication
    app.dependency_overrides[get_db_session] = no_database
    reference = get_coordinate_reference(4326)
    assert reference is not None

    def viewport(self, **kwargs):
        calls.append(kwargs)
        if kwargs["content_revision"] == "c" * 64:
            raise MapReadUnavailableError("SQL SECRET MUST NOT LEAK")
        context = kwargs["context"]
        return {
            "context": {
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "layer_id": kwargs["layer_id"],
                "source_id": UUID(int=1),
                "content_revision": kwargs["content_revision"],
                "schema_revision": kwargs["schema_revision"],
                "geometry_included": True,
                "response_crs": reference.to_wire(),
                "transformation": None,
            },
            "items": [],
            "complete": True,
            "limitation": None,
        }

    def extent(self, **kwargs):
        return {"context": viewport(self, **kwargs)["context"], "state": "empty", "bounds": None}

    monkeypatch.setattr(SqlMapViewportRepository, "viewport", viewport)
    monkeypatch.setattr(SqlMapViewportRepository, "display_extent", extent)
    with TestClient(app) as client:
        yield client, calls


def params():
    return {
        "content_revision": "a" * 64,
        "schema_revision": "b" * 64,
        "west": 106.5,
        "south": 10.6,
        "east": 106.8,
        "north": 10.8,
    }


def test_scoped_context_and_explicit_empty_no_store(http):
    client, calls = http
    response = client.get(BASE + "/viewport", params=params())
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    wire = response.json()
    assert set(wire) == {"context", "items", "complete", "limitation"}
    assert wire["context"]["organization_id"] == str(ORG)
    assert wire["context"]["project_id"] == str(PROJECT)
    assert wire["context"]["layer_id"] == str(LAYER)
    assert wire["context"]["response_crs"]["code"] == 4326
    assert calls[0]["context"].actor.actor_id == ACTOR
    assert calls[0]["limit"] == 500


@pytest.mark.parametrize(
    "changes",
    [
        {"west": "nan"},
        {"north": "inf"},
        {"west": "true"},
        {"east": 106.4},
        {"south": 86},
        {"north": -86},
        {"limit": 0},
        {"limit": 1001},
        {"limit": "1.5"},
        {"content_revision": "secret-invalid-pin"},
    ],
)
def test_invalid_budget_or_bbox_never_reaches_read(http, changes):
    client, calls = http
    response = client.get(BASE + "/viewport", params={**params(), **changes})
    assert response.status_code == 422
    assert calls == []
    assert "secret-invalid-pin" not in response.text


def test_extent_empty_and_failure_cannot_claim_complete(http):
    client, _ = http
    pin = {key: value for key, value in params().items() if "revision" in key}
    response = client.get(BASE + "/display-extent", params=pin)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["state"] == "empty" and response.json()["bounds"] is None
    failed = client.get(BASE + "/viewport", params={**params(), "content_revision": "c" * 64})
    assert failed.status_code == 503
    assert failed.json()["code"] == "MAP_READ_UNAVAILABLE"
    assert "SECRET" not in failed.text and "items" not in failed.text
