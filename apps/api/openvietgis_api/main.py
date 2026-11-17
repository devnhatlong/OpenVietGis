from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openvietgis_api.adapters.http import foundation, health
from openvietgis_api.adapters.http.errors import install_error_handlers
from openvietgis_api.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="OpenVietGIS Foundation API", version="0.1.0")
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5178",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(foundation.router)
    app.include_router(api_v1)
    install_error_handlers(app)
    return app


app = create_app()