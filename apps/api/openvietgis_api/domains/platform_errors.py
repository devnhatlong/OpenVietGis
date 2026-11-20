"""Shared structured domain errors for OpenVietGIS platform domains (R006+)."""

from __future__ import annotations

from typing import Any


class PlatformDomainError(Exception):
    """Structured domain error mapped cleanly to HTTP responses by adapters/http/errors.py."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "DOMAIN_ERROR",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class PlatformValidationError(PlatformDomainError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, status_code=422, details=details)


class PlatformConflictError(PlatformDomainError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "CONFLICT",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, status_code=409, details=details)


class PlatformNotFoundError(PlatformDomainError):
    def __init__(
        self,
        message: str = "resource not found",
        *,
        code: str = "NOT_FOUND",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, status_code=404, details=details)


class PlatformForbiddenError(PlatformDomainError):
    def __init__(
        self,
        message: str = "forbidden",
        *,
        code: str = "FORBIDDEN",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, status_code=403, details=details)
