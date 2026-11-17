from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from openvietgis_api.application.foundation_service import FoundationRecordNotFoundError
from openvietgis_api.domains.authorization.service import (
    AuthorizationDeniedError,
    TenantResourceNotFoundError,
)
from openvietgis_api.domains.tenancy.service import (
    CrossOrganizationWorkspaceError,
    InvalidLifecycleTransitionError,
    ProjectNotFoundError,
    WorkspaceHasActiveProjectsError,
    WorkspaceNotFoundError,
)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FoundationRecordNotFoundError)
    async def foundation_not_found_handler(
        _: Request,
        exc: FoundationRecordNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(AuthorizationDeniedError)
    async def authorization_denied_handler(
        _: Request,
        exc: AuthorizationDeniedError,
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(TenantResourceNotFoundError)
    @app.exception_handler(WorkspaceNotFoundError)
    @app.exception_handler(ProjectNotFoundError)
    async def tenant_not_found_handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CrossOrganizationWorkspaceError)
    @app.exception_handler(InvalidLifecycleTransitionError)
    @app.exception_handler(WorkspaceHasActiveProjectsError)
    async def tenancy_validation_handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
