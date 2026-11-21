"""R010 External Sources domain (SSRF prevention, allowlist, read-only capabilities)."""

from __future__ import annotations

import ipaddress
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from openvietgis_api.domains.platform_errors import (
    PlatformForbiddenError,
    PlatformValidationError,
)


class ExternalProtocol(StrEnum):
    WMS = "wms"
    WMTS_XYZ = "wmts_xyz"
    COG_GEOTIFF = "cog_geotiff"
    WFS_OGC_FEATURES = "wfs_ogc_features"


@dataclass(frozen=True, slots=True)
class AllowlistedHostRecord:
    id: UUID
    organization_id: UUID
    hostname: str
    allowed_schemes: tuple[str, ...]
    allowed_ports: tuple[int, ...]
    secret_ref_name: str | None
    enabled: bool
    created_by_actor_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExternalConnectionRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    allowlist_id: UUID
    name: str
    protocol: ExternalProtocol
    endpoint_url: str
    layer_identifier: str
    attribution: str
    license_text: str
    crs_codes: tuple[int, ...]
    capabilities: dict[str, bool]
    read_only: bool
    cache_generation: int
    lifecycle: str
    created_by_actor_id: UUID
    created_at: datetime
    updated_at: datetime


_FORBIDDEN_HOST_SUFFIXES = (
    "localhost",
    ".localhost",
    ".local",
    ".internal",
    ".home.arpa",
    "metadata.google.internal",
)


def validate_safe_hostname(hostname: str) -> str:
    """Reject loopback, link-local, private IPs, cloud metadata, and local domains (SSRF guard)."""
    clean = hostname.strip().lower().rstrip(".")
    if not clean or "/" in clean or "@" in clean or ":" in clean or " " in clean:
        raise PlatformValidationError("invalid external hostname", code="INVALID_HOSTNAME")
    for suffix in _FORBIDDEN_HOST_SUFFIXES:
        if clean == suffix or clean.endswith(suffix):
            raise PlatformForbiddenError(
                f"SSRF blocked forbidden internal host {clean!r}",
                code="SSRF_BLOCKED",
            )
    try:
        ip = ipaddress.ip_address(clean)
    except ValueError:
        ip = None
    if ip is not None:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise PlatformForbiddenError(
                f"SSRF blocked non-public IP address {clean!r}",
                code="SSRF_BLOCKED",
            )
    if "." not in clean:
        raise PlatformForbiddenError(
            "SSRF blocked single-label internal hostname", code="SSRF_BLOCKED"
        )
    return clean


def validate_endpoint_against_allowlist(
    endpoint_url: str,
    allowlist: AllowlistedHostRecord,
) -> tuple[str, str, int]:
    """Ensure URL has no embedded credentials, passes SSRF checks, and matches allowlist."""
    clean = endpoint_url.strip()
    if (
        not clean
        or len(clean) > 1000
        or not clean.isascii()
        or any(ord(c) <= 32 or ord(c) == 127 for c in clean)
    ):
        raise PlatformValidationError("invalid endpoint URL", code="INVALID_URL")
    try:
        parsed = urllib.parse.urlparse(clean)
        port = parsed.port
    except ValueError as exc:
        raise PlatformValidationError("invalid endpoint URL", code="INVALID_URL") from exc
    if parsed.username is not None or parsed.password is not None:
        raise PlatformForbiddenError(
            "credentials must not be embedded in external URLs; use secret_ref_name",
            code="URL_CREDENTIALS_FORBIDDEN",
        )
    # Raw URL query strings/fragments can contain provider API tokens. Adapter
    # queries are synthesized only by trusted profiles at request time.
    if "?" in clean or "#" in clean:
        raise PlatformForbiddenError(
            "endpoint query strings and fragments are not supported",
            code="URL_PARAMETERS_FORBIDDEN",
        )
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise PlatformValidationError(
            "only http/https external endpoints are permitted", code="INVALID_SCHEME"
        )
    if not parsed.hostname:
        raise PlatformValidationError("endpoint URL requires a hostname", code="INVALID_URL")
    host = validate_safe_hostname(parsed.hostname)
    port = port if port is not None else (443 if scheme == "https" else 80)

    if not allowlist.enabled:
        raise PlatformForbiddenError("allowlisted host is disabled", code="HOST_DISABLED")
    if host != allowlist.hostname:
        raise PlatformForbiddenError(
            f"host {host!r} does not match allowlisted host {allowlist.hostname!r}",
            code="HOST_NOT_ALLOWLISTED",
        )
    if scheme not in allowlist.allowed_schemes:
        raise PlatformForbiddenError(
            f"scheme {scheme!r} is not allowlisted for {host!r}", code="SCHEME_NOT_ALLOWLISTED"
        )
    if port not in allowlist.allowed_ports:
        raise PlatformForbiddenError(
            f"port {port} is not allowlisted for {host!r}", code="PORT_NOT_ALLOWLISTED"
        )
    return parsed.geturl(), host, port


def default_external_capabilities(protocol: ExternalProtocol) -> dict[str, bool]:
    """Registration exposes local metadata only; protocol is not proof of operability."""
    return {
        "metadata_read": True,
        "render": False,
        "feature_read": False,
        "query": False,
        "style": False,
        "edit": False,
        "export": False,
        "analysis": False,
        "offline": False,
    }


def sanitize_allowlist_wire(rec: AllowlistedHostRecord) -> dict[str, Any]:
    return {
        "id": str(rec.id),
        "organization_id": str(rec.organization_id),
        "hostname": rec.hostname,
        "allowed_schemes": list(rec.allowed_schemes),
        "allowed_ports": list(rec.allowed_ports),
        "has_secret_ref": rec.secret_ref_name is not None,
        # A reference name is never necessary for the project UI; keep even
        # accidentally entered credential-like strings out of API responses.
        "secret_ref_name": None,
        "enabled": rec.enabled,
        "created_at": rec.created_at.isoformat(),
    }
