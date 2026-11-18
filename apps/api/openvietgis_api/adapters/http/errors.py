from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from openvietgis_api.domains.authorization.service import (
    AuthorizationDeniedError,
    GrantNotFoundError,
    InvalidGrantError,
    InvalidServiceCredentialError,
    InvalidServicePrincipalError,
    ServiceCredentialNotFoundError,
    ServicePrincipalNotFoundError,
    TenantResourceNotFoundError,
)
from openvietgis_api.domains.tenancy.service import (
    CrossOrganizationWorkspaceError,
    InvalidInvitationError,
    InvalidLifecycleTransitionError,
    InvalidOrganizationInputError,
    InvitationNotFoundError,
    LastOwnerError,
    MembershipNotFoundError,
    OrganizationNotFoundError,
    OwnerRequiredError,
    ProjectNotFoundError,
    WorkspaceHasActiveProjectsError,
    WorkspaceNotFoundError,
)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # FastAPI's default validation body echoes raw input. Authentication/invitation
        # requests can include one-time secrets, so expose no input, loc or context.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": [], "msg": "invalid request payload", "type": "value_error"}
                ]
            },
        )

    @app.exception_handler(AuthorizationDeniedError)
    @app.exception_handler(OwnerRequiredError)
    async def authorization_denied_handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(TenantResourceNotFoundError)
    @app.exception_handler(WorkspaceNotFoundError)
    @app.exception_handler(ProjectNotFoundError)
    @app.exception_handler(OrganizationNotFoundError)
    @app.exception_handler(MembershipNotFoundError)
    @app.exception_handler(GrantNotFoundError)
    @app.exception_handler(InvitationNotFoundError)
    @app.exception_handler(ServicePrincipalNotFoundError)
    @app.exception_handler(ServiceCredentialNotFoundError)
    async def tenant_not_found_handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(CrossOrganizationWorkspaceError)
    @app.exception_handler(InvalidLifecycleTransitionError)
    @app.exception_handler(WorkspaceHasActiveProjectsError)
    @app.exception_handler(InvalidOrganizationInputError)
    @app.exception_handler(InvalidGrantError)
    @app.exception_handler(InvalidServiceCredentialError)
    @app.exception_handler(InvalidServicePrincipalError)
    @app.exception_handler(InvalidInvitationError)
    @app.exception_handler(LastOwnerError)
    async def tenancy_validation_handler(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
