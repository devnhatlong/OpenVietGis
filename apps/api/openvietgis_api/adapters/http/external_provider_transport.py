"""A deliberately restricted HTTPS transport for the public provider profile.

No generic proxy, redirected requests, credentials, retries, or DNS re-resolution
between policy validation and the connected socket. No environmental proxies.
"""

from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from urllib.parse import urlsplit

from openvietgis_api.domains.external_sources.provider import ProviderUnavailable

_REQUEST_SECONDS = 5.0
_DNS_WORKERS = 4
_DNS_POOL = ThreadPoolExecutor(max_workers=_DNS_WORKERS, thread_name_prefix="provider-dns")
_DNS_SLOTS = threading.BoundedSemaphore(_DNS_WORKERS)
_REQUEST_SLOTS = threading.BoundedSemaphore(8)

_MEDIA_TYPES = {
    "xml": {
        "text/xml",
        "application/xml",
        "application/vnd.ogc.wms_xml",
        "application/vnd.ogc.wfs_xml",
    },
    "png": {"image/png"},
    "json": {"application/json", "application/geo+json"},
}


def _public_ipv4(hostname: str, deadline: float) -> str:
    """Reject every non-public DNS answer, then pin one IPv4 address."""
    labels = hostname.split(".")
    if (
        len(hostname) > 253
        or len(labels) < 2
        or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
    ):
        raise ProviderUnavailable()
    if not _DNS_SLOTS.acquire(blocking=False):
        raise ProviderUnavailable()
    try:
        future = _DNS_POOL.submit(
            socket.getaddrinfo,
            hostname,
            443,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
        )
    except RuntimeError:
        _DNS_SLOTS.release()
        raise ProviderUnavailable() from None
    future.add_done_callback(lambda _: _DNS_SLOTS.release())
    try:
        records = future.result(timeout=max(0.001, deadline - time.monotonic()))
        candidates = []
        for family, _, _, _, address in records:
            ip = ipaddress.ip_address(address[0])
            if (
                not ip.is_global
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
                or ip.is_link_local
                or ip.is_loopback
                or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None)
            ):
                raise ProviderUnavailable()
            if family == socket.AF_INET and isinstance(ip, ipaddress.IPv4Address):
                candidates.append(str(ip))
        if not candidates:
            raise ProviderUnavailable()
        return sorted(set(candidates))[0]
    except (TimeoutError, OSError, ValueError) as exc:
        raise ProviderUnavailable() from exc


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProviderUnavailable()
    return remaining


def _interrupt(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def fetch_provider_bytes(url: str, expected: str, limit: int) -> bytes:
    """GET only, bounded absolute deadline, image/XML/JSON media type checks."""
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.netloc not in (parsed.hostname, f"{parsed.hostname}:443")
            or parsed.fragment
            or not parsed.path.startswith("/")
            or not 0 < limit <= 2 * 1024 * 1024
            or expected not in _MEDIA_TYPES
            or not url.isascii()
            or any(ord(c) < 32 or ord(c) == 127 for c in url)
        ):
            raise ProviderUnavailable()
    except ValueError as exc:
        raise ProviderUnavailable() from exc
    if not _REQUEST_SLOTS.acquire(blocking=False):
        raise ProviderUnavailable()
    raw: socket.socket | None = None
    connected: ssl.SSLSocket | None = None
    connection: http.client.HTTPConnection | None = None
    timer: threading.Timer | None = None
    try:
        deadline = time.monotonic() + _REQUEST_SECONDS
        address = _public_ipv4(parsed.hostname, deadline)
        # Use a numeric IPv4 socket directly; no second DNS resolution.
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        raw.settimeout(_remaining(deadline))
        raw.connect((address, 443))
        if raw.getpeername()[0] != address:
            raise ProviderUnavailable()
        raw.settimeout(_remaining(deadline))
        # Default verification checks trust chain + hostname, preserving TLS SNI.
        connected = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
        if connected.getpeername()[0] != address:
            raise ProviderUnavailable()
        connected.settimeout(_remaining(deadline))
        timer = threading.Timer(_remaining(deadline), _interrupt, args=(connected,))
        timer.daemon = True
        timer.start()
        connection = http.client.HTTPConnection(parsed.hostname, 443, timeout=_remaining(deadline))
        connection.sock = connected
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        connection.request(
            "GET",
            path,
            headers={
                "Host": parsed.hostname,
                "Accept": ", ".join(sorted(_MEDIA_TYPES[expected])),
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "OpenVietGIS-restricted-provider/1",
            },
        )
        response = connection.getresponse()
        # Never follow even same-origin redirects.
        if response.status != 200 or response.getheader("Location"):
            raise ProviderUnavailable()
        if response.getheader("Content-Encoding", "identity").lower().strip() != "identity":
            raise ProviderUnavailable()
        media_type = response.getheader("Content-Type", "").partition(";")[0].strip().lower()
        if media_type not in _MEDIA_TYPES[expected]:
            raise ProviderUnavailable()
        declared = response.getheader("Content-Length")
        if declared is not None and (not declared.isdecimal() or int(declared) > limit):
            raise ProviderUnavailable()
        payload = response.read(limit + 1)
        _remaining(deadline)
        if not payload or len(payload) > limit:
            raise ProviderUnavailable()
        if declared is not None and len(payload) != int(declared):
            raise ProviderUnavailable()
        return payload
    except (OSError, http.client.HTTPException, ValueError, OverflowError) as exc:
        raise ProviderUnavailable() from exc
    finally:
        if timer is not None:
            timer.cancel()
        if connection is not None:
            connection.close()
        if connected is not None:
            connected.close()
        if raw is not None:
            raw.close()
        _REQUEST_SLOTS.release()
