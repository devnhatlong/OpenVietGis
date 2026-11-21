"""Controlled provider bytes and actual HTTP request parsing, with no network."""

from __future__ import annotations

import base64
import io
import json
import socket
import ssl
import time
from dataclasses import asdict, replace
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from PIL import Image

from openvietgis_api.adapters.http import external_provider_transport as transport
from openvietgis_api.adapters.http.external_sources import _safe_display_endpoint
from openvietgis_api.domains.external_sources.domain import (
    AllowlistedHostRecord,
    ExternalConnectionRecord,
    ExternalProtocol,
    default_external_capabilities,
)
from openvietgis_api.domains.external_sources.provider import (
    PROFILE_ENV,
    ProviderProfile,
    ProviderUnavailable,
    approved_profile,
    load_profiles,
    provider_preview,
)
from openvietgis_api.domains.platform_errors import PlatformForbiddenError

HOST = "provider.example.org"
PINNED_IP = "93.184.216.34"  # never contacted; synthetic DNS answer
RIGHTS = "CC-BY-4.0"
ATTRIBUTION = "Controlled fixture"
LAYER = "fixtures:parcels"
BBOX = (105.5, 20.5, 106.5, 21.5)
PROFILE = ProviderProfile(
    f"https://{HOST}/wms", ExternalProtocol.WMS, LAYER, 4326, BBOX, ATTRIBUTION, RIGHTS
)
WFS = replace(PROFILE, endpoint=f"https://{HOST}/wfs", protocol=ExternalProtocol.WFS_OGC_FEATURES)

WMS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<WMT_MS_Capabilities version="1.1.1">
 <Capability><Request><GetMap><Format>image/png</Format></GetMap></Request>
 <Layer><SRS>EPSG:4326</SRS>
 <BoundingBox SRS="EPSG:4326" minx="105" miny="20" maxx="107" maxy="22"/>
 <Layer><Name>fixtures:parcels</Name></Layer>
 </Layer></Capability></WMT_MS_Capabilities>"""
WFS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<WFS_Capabilities version="1.0.0" xmlns="http://www.opengis.net/wfs">
 <Capability><Request><GetFeature><ResultFormat><JSON/></ResultFormat></GetFeature>
 </Request></Capability>
 <FeatureTypeList><Operations><Query/></Operations><FeatureType>
 <Name>fixtures:parcels</Name><SRS>EPSG:4326</SRS>
 <LatLongBoundingBox minx="105" miny="20" maxx="107" maxy="22"/>
 </FeatureType></FeatureTypeList></WFS_Capabilities>"""
FEATURES = {
    "type": "FeatureCollection",
    "numberReturned": 1,
    "features": [
        {
            "type": "Feature",
            "id": "p1",
            "geometry": {"type": "Point", "coordinates": [106.25, 21.125]},
            "properties": {"plot": "synthetic only", "size": 123},
        }
    ],
}


def png(size: tuple[int, int] = (256, 256)) -> bytes:
    out = io.BytesIO()
    img = Image.new("RGBA", size, (11, 22, 233, 255))
    img.putpixel((12, 34), (99, 89, 79, 255))
    img.save(out, format="PNG")
    return out.getvalue()


class FixtureSocket:
    """HTTPConnection genuinely parses a synthetic raw provider response."""

    def __init__(self, factory: FixtureProvider):
        self.factory = factory
        self.sent = bytearray()
        self.peer = PINNED_IP

    def settimeout(self, _: float) -> None:
        pass

    def connect(self, address: tuple[str, int]) -> None:
        assert address == (PINNED_IP, 443)
        self.factory.addresses.append(address)

    def getpeername(self) -> tuple[str, int]:
        return self.peer, 443

    def sendall(self, value: bytes) -> None:
        self.sent.extend(value)

    def makefile(self, *_args: object, **_kwargs: object) -> io.BytesIO:
        request = bytes(self.sent).decode("ascii")
        first, *headers = request.split("\r\n")
        method, path, _ = first.split()
        assert method == "GET"
        assert f"Host: {HOST}" in headers
        assert "Accept-Encoding: identity" in headers
        assert not any(line.startswith(("Authorization:", "Cookie:")) for line in headers)
        self.factory.requests.append(path)
        status, media, data, extra = self.factory.response(path)
        return io.BytesIO(
            f"HTTP/1.1 {status}\r\nContent-Type: {media}\r\n"
            f"Content-Length: {len(data)}\r\nConnection: close\r\n{extra}\r\n".encode("ascii")
            + data
        )

    def shutdown(self, _: int) -> None:
        pass

    def close(self) -> None:
        pass


class FixtureProvider:
    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self.addresses: list[tuple[str, int]] = []
        self.requests: list[str] = []
        self.sni: list[str] = []
        self.dns = [PINNED_IP]
        self.peer = PINNED_IP
        self.status = "200 OK"
        self.extra = ""
        self.wms_xml = WMS_XML
        self.wfs_xml = WFS_XML
        self.image = png()
        self.features = json.dumps(FEATURES).encode()
        self.media_override = ""
        monkeypatch.setattr(transport.socket, "getaddrinfo", self.resolve)
        monkeypatch.setattr(transport.socket, "socket", self.socket)
        monkeypatch.setattr(transport.ssl, "create_default_context", lambda: self)

    def resolve(self, host: str, port: int, *_args: object):
        assert host == HOST and port == 443
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))
            for ip in self.dns
        ]

    def socket(self, *_args: object) -> FixtureSocket:
        value = FixtureSocket(self)
        value.peer = self.peer
        return value

    def wrap_socket(self, sock: FixtureSocket, *, server_hostname: str) -> FixtureSocket:
        assert server_hostname == HOST
        self.sni.append(server_hostname)
        return sock

    def response(self, path: str) -> tuple[str, str, bytes, str]:
        parsed = urlsplit(path)
        params = parse_qs(parsed.query, keep_blank_values=True)
        if params["REQUEST"] == ["GetCapabilities"]:
            data = self.wms_xml if parsed.path == "/wms" else self.wfs_xml
            media = "text/xml"
        elif params["REQUEST"] == ["GetMap"]:
            assert parsed.path == "/wms"
            assert params["LAYERS"] == [LAYER]
            assert params["SRS"] == ["EPSG:4326"]
            assert params["BBOX"] == [",".join(map(str, BBOX))]
            assert params["WIDTH"] == params["HEIGHT"] == ["256"]
            data = self.image
            media = "image/png"
        elif params["REQUEST"] == ["GetFeature"]:
            assert parsed.path == "/wfs"
            assert params["TYPENAME"] == [LAYER]
            assert params["SRSNAME"] == ["EPSG:4326"]
            assert params["BBOX"] == [",".join(map(str, BBOX))]
            assert params["MAXFEATURES"] == ["100"]
            data = self.features
            media = "application/geo+json"
        else:
            raise AssertionError("unapproved operation")
        return self.status, self.media_override or media, data, self.extra


@pytest.fixture
def fixture(monkeypatch: pytest.MonkeyPatch) -> FixtureProvider:
    return FixtureProvider(monkeypatch)


def _records(profile: ProviderProfile):
    organization_id, project_id, actor_id, allowlist_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    allowlist = AllowlistedHostRecord(
        allowlist_id, organization_id, HOST, ("https",), (443,), None, True, actor_id, now
    )
    conn = ExternalConnectionRecord(
        uuid4(),
        organization_id,
        project_id,
        allowlist_id,
        "Example",
        profile.protocol,
        profile.endpoint,
        profile.layer,
        profile.attribution,
        profile.license_text,
        (profile.crs,),
        default_external_capabilities(profile.protocol),
        True,
        1,
        "active",
        actor_id,
        now,
        now,
    )
    return conn, allowlist


def test_wms_real_preview_bytes_and_request_parameters(fixture: FixtureProvider):
    result = provider_preview(PROFILE, transport.fetch_provider_bytes)
    assert result["availability"] == "available"
    assert result["bbox"] == BBOX
    assert {cap for cap, enabled in result["capabilities"].items() if enabled} == {
        "metadata_read",
        "render",
    }
    assert len(fixture.requests) == 2
    assert fixture.sni == [HOST, HOST]
    assert fixture.addresses == [(PINNED_IP, 443), (PINNED_IP, 443)]
    with Image.open(io.BytesIO(base64.b64decode(result["image_png_base64"]))) as img:
        assert img.size == (256, 256)
        assert img.getpixel((12, 34)) == (99, 89, 79, 255)
        assert img.getpixel((100, 100)) == (11, 22, 233, 255)


def test_wfs_real_bounded_read_and_query(fixture: FixtureProvider):
    result = provider_preview(WFS, transport.fetch_provider_bytes)
    assert result["feature_collection"]["features"] == FEATURES["features"]
    assert {cap for cap, enabled in result["capabilities"].items() if enabled} == {
        "metadata_read",
        "feature_read",
        "query",
    }
    assert len(fixture.requests) == 2
    assert result["attribution"] == ATTRIBUTION
    assert result["license_text"] == RIGHTS


def test_profile_default_denial_exact_match_rights_and_revocation(monkeypatch):
    conn, allowlist = _records(PROFILE)
    monkeypatch.delenv(PROFILE_ENV, raising=False)
    with pytest.raises(PlatformForbiddenError, match="operator-approved"):
        approved_profile(conn, allowlist)
    monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(PROFILE)]))
    assert load_profiles() == (PROFILE,)
    assert approved_profile(conn, allowlist) == PROFILE
    for invalid in (
        replace(conn, license_text="other rights"),
        replace(conn, layer_identifier="other"),
        replace(conn, endpoint_url=f"https://{HOST}/other"),
        replace(conn, crs_codes=(3857,)),
        replace(conn, lifecycle="revoked"),
    ):
        with pytest.raises(PlatformForbiddenError):
            approved_profile(invalid, allowlist)
    with pytest.raises(PlatformForbiddenError):
        approved_profile(conn, replace(allowlist, enabled=False))
    with pytest.raises(PlatformForbiddenError):
        approved_profile(conn, replace(allowlist, secret_ref_name="NO_SECRET"))
    # Unknown/unsupported protocols cannot infer capabilities from registration.
    for protocol in (ExternalProtocol.COG_GEOTIFF, ExternalProtocol.WMTS_XYZ):
        with pytest.raises(PlatformForbiddenError):
            approved_profile(replace(conn, protocol=protocol), allowlist)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "192.168.3.4",
        "224.0.0.1",
        "0.0.0.0",
    ],
)
def test_dns_rebinding_mixed_public_private_reject(fixture: FixtureProvider, address: str):
    fixture.dns = [PINNED_IP, address]
    with pytest.raises(ProviderUnavailable):
        provider_preview(PROFILE, transport.fetch_provider_bytes)
    assert not fixture.addresses and not fixture.requests


def test_actual_peer_mismatch_rejects_before_tls(fixture: FixtureProvider):
    fixture.peer = "93.184.216.33"
    with pytest.raises(ProviderUnavailable):
        provider_preview(PROFILE, transport.fetch_provider_bytes)
    assert not fixture.requests and not fixture.sni


def test_tls_host_certificate_failure_no_http_request(
    fixture: FixtureProvider, monkeypatch: pytest.MonkeyPatch
):
    def invalid_certificate(*_args, **_kwargs):
        raise ssl.SSLCertVerificationError("synthetic certificate mismatch")

    monkeypatch.setattr(fixture, "wrap_socket", invalid_certificate)
    with pytest.raises(ProviderUnavailable):
        provider_preview(PROFILE, transport.fetch_provider_bytes)
    assert fixture.addresses == [(PINNED_IP, 443)]
    assert not fixture.requests


def test_invalid_operator_policy_fails_closed(monkeypatch: pytest.MonkeyPatch):
    for raw in ("{", "[" * 5000 + "]" * 5000, '{"protocol": "wms"}'):
        monkeypatch.setenv(PROFILE_ENV, raw)
        assert not load_profiles()
    raw = json.dumps([asdict(PROFILE)])
    monkeypatch.setenv(PROFILE_ENV, raw.replace('"layer":', '"layer": "n", "layer":'))
    assert not load_profiles()
    invalid = replace(PROFILE, endpoint=PROFILE.endpoint + "?")
    monkeypatch.setenv(PROFILE_ENV, json.dumps([asdict(invalid)]))
    assert not load_profiles()


def test_redirects_never_followed(fixture: FixtureProvider):
    fixture.status = "302 Found"
    fixture.extra = "Location: http://169.254.169.254/latest/meta-data\r\n"
    with pytest.raises(ProviderUnavailable):
        provider_preview(PROFILE, transport.fetch_provider_bytes)
    assert len(fixture.requests) == 1


def test_media_types_encoding_and_response_size_fail_closed(fixture: FixtureProvider):
    fixture.media_override = "text/html"
    with pytest.raises(ProviderUnavailable):
        provider_preview(PROFILE, transport.fetch_provider_bytes)
    fixture.media_override = ""
    fixture.extra = "Content-Encoding: gzip\r\n"
    with pytest.raises(ProviderUnavailable):
        provider_preview(PROFILE, transport.fetch_provider_bytes)
    fixture.extra = ""
    fixture.wms_xml = b" " * (512 * 1024 + 1)
    with pytest.raises(ProviderUnavailable):
        provider_preview(PROFILE, transport.fetch_provider_bytes)


def test_xml_injection_wrong_layer_bbox_crs_and_image_rejected(fixture: FixtureProvider):
    for data in (
        b"<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///etc/passwd'>]>" + WMS_XML,
        WMS_XML.replace(b"fixtures:parcels", b"wrong"),
        WMS_XML.replace(b"EPSG:4326", b"EPSG:3857"),
        WMS_XML.replace(b'maxx="107"', b'maxx="106"'),
    ):
        fixture.wms_xml = data
        with pytest.raises(ProviderUnavailable):
            provider_preview(PROFILE, transport.fetch_provider_bytes)
    fixture.wms_xml = WMS_XML
    for image in (png((257, 256)), b"not png", png()[:-3], png() + b"trailing"):
        fixture.image = image
        with pytest.raises(ProviderUnavailable):
            provider_preview(PROFILE, transport.fetch_provider_bytes)


def test_geojson_wrong_axis_nonfinite_properties_count_and_crs_rejected(fixture: FixtureProvider):
    payloads = [
        json.dumps(FEATURES).replace("106.25, 21.125", "21.125, 106.25"),
        json.dumps(FEATURES).replace("123", "NaN"),
        json.dumps(FEATURES).replace("123", '{"nested": "unsupported"}'),
        json.dumps(FEATURES).replace('"numberReturned": 1', '"numberReturned": 2'),
        json.dumps(FEATURES).replace('"numberReturned": 1', '"crs": "EPSG:3857"'),
        json.dumps(FEATURES).replace('"size": 123', '"size": 123, "size": 456'),
    ]
    for data in payloads:
        fixture.features = data.encode()
        with pytest.raises(ProviderUnavailable):
            provider_preview(WFS, transport.fetch_provider_bytes)
    fixture.features = json.dumps({**FEATURES, "features": FEATURES["features"] * 101}).encode()
    with pytest.raises(ProviderUnavailable):
        provider_preview(WFS, transport.fetch_provider_bytes)


def test_no_raw_query_credentials_displayed():
    assert _safe_display_endpoint(f"https://user:password@{HOST}/wms?token=SECRET") == (
        f"https://{HOST}/wms"
    )


def test_dns_resolution_has_absolute_wait_bound(monkeypatch):
    def slow(*_args):
        time.sleep(0.1)
        return []

    monkeypatch.setattr(transport.socket, "getaddrinfo", slow)
    start = time.monotonic()
    with pytest.raises(ProviderUnavailable):
        transport._public_ipv4(HOST, start + 0.01)
    assert time.monotonic() - start < 0.09
