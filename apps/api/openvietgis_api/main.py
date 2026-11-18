from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from openvietgis_api.adapters.http import (
    audit,
    auth,
    bootstrap,
    foundation,
    grants,
    health,
    invitations,
    me,
    organizations,
    projects,
    service_principals,
    workspaces,
)
from openvietgis_api.adapters.http.errors import install_error_handlers
from openvietgis_api.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="OpenVietGIS API", version="0.2.0")
    app.state.settings = settings

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.application_session_secret.get_secret_value(),
        session_cookie="ovg_oidc_state",
        max_age=600,
        same_site="lax",
        https_only=settings.session_cookie_secure,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5178",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["content-type", "authorization", "x-openvietgis-csrf"],
    )

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(foundation.router)
    api_v1.include_router(auth.router)
    api_v1.include_router(bootstrap.router)
    api_v1.include_router(audit.router)
    api_v1.include_router(me.router)
    api_v1.include_router(organizations.router)
    api_v1.include_router(workspaces.router)
    api_v1.include_router(projects.router)
    api_v1.include_router(grants.router)
    api_v1.include_router(invitations.router)
    api_v1.include_router(service_principals.router)
    app.include_router(api_v1)
    install_error_handlers(app)
    return app


app = create_app()