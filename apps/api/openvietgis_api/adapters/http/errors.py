from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from openvietgis_api.application.foundation_service import FoundationRecordNotFoundError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FoundationRecordNotFoundError)
    async def not_found_handler(
        _: Request, exc: FoundationRecordNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
