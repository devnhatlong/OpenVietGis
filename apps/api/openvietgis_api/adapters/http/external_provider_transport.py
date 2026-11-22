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

from openvietgis_api.domains.external_sources.provider import ProviderUnavailable, RangeResponse

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
        "application/vnd.ogc.wmts_xml",
    },
    "png": {"image/png"},
    "json": {"application/json", "application/geo+json"},
    "tiff": {"image/tiff", "image/geotiff", "application/geotiff"},
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


def _strong_etag(value: str | None) -> bool:
    # Strict ASCII strong validator; never echo a weak or malformed value.
    return value is not None and re.fullmatch(r'"[\x21\x23-\x7e]{1,128}"', value) is not None


def _fetch_response(
    url: str,
    expected: str,
    limit: int,
    *,
    first: int | None = None,
    last: int | None = None,
    etag: str | None = None,
    total: int | None = None,
    timeout: float = _REQUEST_SECONDS,
) -> tuple[bytes, int | None, str | None]:
    """Bounded HTTPS bytes and (for advanced COG) immutable range metadata."""
    advanced = first is not None
    if first is not None and (
        last is None
        or expected != "tiff"
        or not 0 <= first <= last < 2**31
        or last - first + 1 != limit
        or ((etag is None) != (total is None))
        or (etag is not None and not _strong_etag(etag))
        or (total is not None and not first < total <= 2**31)
    ):
        raise ProviderUnavailable()
    if not 0 < timeout <= _REQUEST_SECONDS:
        raise ProviderUnavailable()
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.netloc not in (parsed.hostname, f"{parsed.hostname}:443")
            or parsed.fragment
            or (advanced and parsed.query)
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
        deadline = time.monotonic() + timeout
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
        headers = {
            "Host": parsed.hostname,
            "Accept": ", ".join(sorted(_MEDIA_TYPES[expected])),
            "Accept-Encoding": "identity",
            "Connection": "close",
            "User-Agent": "OpenVietGIS-restricted-provider/1",
        }
        if expected == "tiff":
            headers["Range"] = f"bytes={first}-{last}" if advanced else f"bytes=0-{limit - 1}"
            if advanced and etag is not None:
                headers["If-Match"] = etag
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        # Never follow even same-origin redirects.
        if response.status != (206 if expected == "tiff" else 200) or response.getheader(
            "Location"
        ):
            raise ProviderUnavailable()
        if response.getheader("Content-Encoding", "identity").lower().strip() != "identity":
            raise ProviderUnavailable()
        media_type = response.getheader("Content-Type", "").partition(";")[0].strip().lower()
        if media_type not in _MEDIA_TYPES[expected]:
            raise ProviderUnavailable()
        declared = response.getheader("Content-Length")
        if declared is not None and (not declared.isdecimal() or int(declared) > limit):
            raise ProviderUnavailable()
        response_total: int | None = None
        response_etag: str | None = None
        if expected == "tiff":
            content_range = response.getheader("Content-Range", "")
            match = re.fullmatch(r"bytes ([0-9]{1,10})-([0-9]{1,10})/([0-9]{1,10})", content_range)
            if match is None or declared is None:
                raise ProviderUnavailable()
            actual_first, actual_last, response_total = map(int, match.groups())
            if advanced:
                # Every subsequent range is pinned with a strong If-Match
                # validator and exact original object size. No ignored or
                # clipped range, multipart fallback, or version mixing.
                assert first is not None and last is not None
                response_etag = response.getheader("ETag")
                if (
                    not _strong_etag(response_etag)
                    or (etag is not None and response_etag != etag)
                    or (total is not None and response_total != total)
                    or not actual_first == first < response_total <= 2**31
                    or actual_last != min(last, response_total - 1)
                    or int(declared) != actual_last - actual_first + 1
                ):
                    raise ProviderUnavailable()
            elif not (
                actual_first == 0
                and 0 < response_total <= limit
                and actual_last == response_total - 1
                and int(declared) == response_total
            ):
                raise ProviderUnavailable()
        elif response.getheader("Content-Range") is not None:
            raise ProviderUnavailable()
        payload = response.read(limit + 1)
        _remaining(deadline)
        if not payload or len(payload) > limit:
            raise ProviderUnavailable()
        if declared is not None and len(payload) != int(declared):
            raise ProviderUnavailable()
        return payload, response_total, response_etag
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


def fetch_provider_bytes(url: str, expected: str, limit: int) -> bytes:
    """GET only, bounded absolute deadline, image/XML/JSON media type checks."""
    payload, _, _ = _fetch_response(url, expected, limit)
    return payload


def fetch_provider_range(
    url: str, first: int, last: int, etag: str | None, total: int | None, timeout: float
) -> RangeResponse:
    """Read only one precise COG range of an immutable object."""
    payload, size, validator = _fetch_response(
        url,
        "tiff",
        last - first + 1,
        first=first,
        last=last,
        etag=etag,
        total=total,
        timeout=timeout,
    )
    assert size is not None and validator is not None
    return RangeResponse(payload, size, validator)
