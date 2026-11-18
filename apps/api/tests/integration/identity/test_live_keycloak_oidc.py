"""Opt-in backend acceptance using the real loopback Keycloak authorization-code flow.

This is not browser/Playwright E2E. The provider login form and authorization code
exchange are real; only the application HTTP transport is in-process TestClient.
"""
from __future__ import annotations

import json
import logging
import os
import re
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from tools.test_database import assert_safe_test_target

from openvietgis_api.config import get_settings
from openvietgis_api.main import create_app
from openvietgis_api.security.sessions import parse_session_token, verify_session_token
from tests.fixtures.db_admin import get_admin_session_factory

pytestmark = pytest.mark.skipif(
    os.environ.get("OPENVIETGIS_LIVE_OIDC") != "1",
    reason="opt-in loopback Keycloak acceptance; set OPENVIETGIS_LIVE_OIDC=1",
)

ISSUER = "http://127.0.0.1:18080/realms/openvietgis"
PROVIDER_ORIGIN = "http://127.0.0.1:18080"
APP_ORIGIN = "http://127.0.0.1:8000"
CALLBACK_PATH = "/api/v1/auth/callback/keycloak"
CALLBACK_URL = APP_ORIGIN + CALLBACK_PATH
WEB_ORIGIN = "http://127.0.0.1:5173"
CLIENT_ID = "openvietgis-web"
FIXTURE_USERNAME = "owner-a"
REDIRECT_CODES = {301, 302, 303, 307, 308}


def _require(condition: bool, reason: str) -> None:
    # Avoid pytest assertion introspection leaking credential-bearing URLs,
    # response bodies, cookie values, codes or token exchange data.
    if not condition:
        pytest.fail(reason, pytrace=False)


def _provider_url(value: str) -> bool:
    parts = urlsplit(value)
    return (
        parts.scheme == "http"
        and parts.netloc == "127.0.0.1:18080"
        and parts.path.startswith("/realms/openvietgis/")
        and not parts.fragment
    )


def _callback_url(value: str) -> bool:
    parts = urlsplit(value)
    return (
        parts.scheme == "http"
        and parts.netloc == "127.0.0.1:8000"
        and parts.path == CALLBACK_PATH
        and not parts.fragment
    )


def _redirect(response: httpx.Response) -> str:
    _require(response.status_code in REDIRECT_CODES, "expected local provider redirect")
    location = response.headers.get("location")
    _require(bool(location), "provider redirect had no location")
    return urljoin(str(response.url), location or "")


def _fixture_password() -> str:
    fixture = (
        Path(__file__).resolve().parents[5]
        / "infra/dev/keycloak/realm-openvietgis.json"
    )
    data = json.loads(fixture.read_text(encoding="utf-8"))
    user = next(item for item in data["users"] if item["username"] == FIXTURE_USERNAME)
    password = next(item for item in user["credentials"] if item["type"] == "password")
    _require(
        data["realm"] == "openvietgis"
        and user["enabled"] is True
        and user["email"] == "owner-a@example.test"
        and password["temporary"] is False
        and isinstance(password["value"], str)
        and password["value"].startswith("openvietgis-test-"),
        "expected checked-in synthetic fixture identity",
    )
    return password["value"]


def _check_discovery(client: httpx.Client) -> None:
    response = client.get(ISSUER + "/.well-known/openid-configuration")
    _require(response.status_code == 200, "Keycloak loopback discovery is not healthy")
    metadata = response.json()
    protocol = ISSUER + "/protocol/openid-connect/"
    _require(
        metadata.get("issuer") == ISSUER
        and metadata.get("authorization_endpoint") == protocol + "auth"
        and metadata.get("token_endpoint") == protocol + "token"
        and metadata.get("jwks_uri") == protocol + "certs",
        "unexpected issuer or non-local provider endpoint",
    )


class _LoginForm(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found = False
        self.inside = False
        self.action: str | None = None
        self.method: str | None = None
        self.names: set[str] = set()
        self.hidden: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "form":
            if attributes.get("id") == "kc-form-login":
                if self.found:
                    raise ValueError("duplicate login form")
                self.found = True
                self.inside = True
                self.action = attributes.get("action")
                self.method = attributes.get("method")
            elif self.inside:
                raise ValueError("nested login form")
        elif tag == "input" and self.inside:
            name = attributes.get("name")
            if name:
                self.names.add(name)
                if attributes.get("type") == "hidden":
                    self.hidden[name] = attributes.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self.inside:
            self.inside = False


def _login_page(client: httpx.Client, url: str) -> httpx.Response:
    for _ in range(8):
        _require(_provider_url(url), "refusing unexpected provider navigation")
        response = client.get(url)
        if response.status_code == 200:
            return response
        url = _redirect(response)
    pytest.fail("provider authorization redirect limit exceeded", pytrace=False)


def _provider_callback(client: httpx.Client, authorization_url: str) -> str:
    page = _login_page(client, authorization_url)
    form = _LoginForm()
    form.feed(page.text)
    form.close()
    _require(
        form.found
        and form.action is not None
        and (form.method or "").lower() == "post"
        and {"username", "password"} <= form.names,
        "Keycloak synthetic login form was not found",
    )
    action = urljoin(str(page.url), form.action or "")
    _require(
        _provider_url(action)
        and urlsplit(action).path == "/realms/openvietgis/login-actions/authenticate",
        "refusing to send synthetic credentials to an unexpected action",
    )
    # The password is sent only to Keycloak's standard browser login action.
    # No direct password grant and no token endpoint mocking.
    response = client.post(
        action,
        data={
            **form.hidden,
            "username": FIXTURE_USERNAME,
            "password": _fixture_password(),
        },
        headers={"Origin": PROVIDER_ORIGIN, "Referer": str(page.url)},
    )
    for _ in range(8):
        _require(
            response.status_code in {301, 302, 303},
            "synthetic login did not yield a safe redirect",
        )
        location = _redirect(response)
        if _callback_url(location):
            return location
        _require(_provider_url(location), "refusing unexpected post-login navigation")
        response = client.get(location)
    pytest.fail("post-login provider redirect limit exceeded", pytrace=False)


def _login_once(app: TestClient, provider: httpx.Client) -> tuple[str, str]:
    begin = app.get(
        "/api/v1/auth/login/keycloak",
        params={"return_to": "/organizations"},
        follow_redirects=False,
    )
    _require(begin.status_code == 302, "application did not start authorization")
    authorization_url = begin.headers.get("location", "")
    _require(_provider_url(authorization_url), "unexpected authorization URL")
    authorization = parse_qs(urlsplit(authorization_url).query)
    _require(
        urlsplit(authorization_url).path
        == "/realms/openvietgis/protocol/openid-connect/auth"
        and authorization.get("response_type") == ["code"]
        and authorization.get("client_id") == [CLIENT_ID]
        and authorization.get("redirect_uri") == [CALLBACK_URL]
        and authorization.get("code_challenge_method") == ["S256"]
        and len(authorization.get("state", [])) == 1
        and len(authorization.get("nonce", [])) == 1
        and len(authorization.get("code_challenge", [])) == 1
        and bool(re.fullmatch(
            r"[A-Za-z0-9_-]{43}", authorization.get("code_challenge", [""])[0]
        )),
        "authorization code, state, nonce or PKCE contract is invalid",
    )
    callback_url = _provider_callback(provider, authorization_url)
    callback = urlsplit(callback_url)
    query = parse_qs(callback.query)
    _require(
        query.get("state") == authorization.get("state")
        and len(query.get("code", [])) == 1
        and not {"error", "access_token", "id_token", "refresh_token"} & query.keys(),
        "provider callback did not carry the expected authorization code and state",
    )

    # Do not connect to a real app server: route Keycloak's actual callback via
    # TestClient, preserving the app's original signed OIDC transaction cookie.
    result = app.get(callback.path + "?" + callback.query, follow_redirects=False)
    _require(result.status_code == 302, "real authorization code exchange failed")
    _require(
        result.headers.get("location") == WEB_ORIGIN + "/organizations"
        and not result.content,
        "callback leaked data or did not redirect to the expected app path",
    )
    cookies = SimpleCookie()
    for header in result.headers.get_list("set-cookie"):
        cookies.load(header)
    cookie_name = get_settings().session_cookie_name
    _require(
        set(cookies) <= {cookie_name, "ovg_oidc_state"} and cookie_name in cookies,
        "callback returned unexpected cookies",
    )
    _require(
        bool(cookies[cookie_name]["httponly"])
        and cookies[cookie_name]["samesite"].lower() == "lax"
        and cookies[cookie_name]["path"] == "/",
        "application session cookie flags are invalid",
    )
    token = app.cookies.get(cookie_name, "")
    _require(
        bool(re.fullmatch(r"ovgs_[0-9a-f]{32}\.s_[A-Za-z0-9_-]{43}", token))
        and set(app.cookies.keys()) == {cookie_name},
        "expected only an opaque application session cookie after OIDC callback",
    )
    me = app.get("/api/v1/me")
    _require(me.status_code == 200, "first-party session could not resolve /me")
    user = me.json()
    _require(
        set(user) == {"id", "display_name", "email_snapshot", "status"}
        and user.get("email_snapshot") == "owner-a@example.test"
        and user.get("status") == "active"
        and isinstance(user.get("id"), str),
        "current user does not match the synthetic Keycloak identity",
    )
    # The browser-facing token is our own opaque session, not a provider JWT or
    # refresh token. Prove its stored representation is only a digest.
    parsed = parse_session_token(token)
    with get_admin_session_factory()() as admin:
        row = admin.execute(
            text(
                """
                SELECT s.secret_hash, s.user_id, s.revoked_at, l.issuer,
                       l.email_snapshot, l.email_verified
                FROM identity.web_sessions s
                JOIN identity.identity_links l
                  ON l.id = s.identity_link_id AND l.user_id = s.user_id
                WHERE s.id = :id
                """
            ),
            {"id": parsed.session_id},
        ).mappings().one_or_none()
        _require(
            row is not None,
            "application session was not persisted",
        )
        if row is not None:
            verify_session_token(token, bytes(row["secret_hash"]))
            _require(
                len(bytes(row["secret_hash"])) == 32
                and str(row["user_id"]) == user["id"]
                and row["revoked_at"] is None
                and row["issuer"] == ISSUER
                and row["email_snapshot"] == "owner-a@example.test"
                and row["email_verified"] is True,
                "persisted session or stable OIDC identity is invalid",
            )

    return user["id"], token


def _logout(app: TestClient, token: str) -> None:
    csrf = app.get("/api/v1/auth/csrf")
    _require(csrf.status_code == 200, "session did not provide CSRF token")
    csrf_token = csrf.json().get("token")
    _require(isinstance(csrf_token, str) and bool(csrf_token), "missing CSRF token")
    response = app.post(
        "/api/v1/auth/logout",
        headers={"X-OpenVietGIS-CSRF": csrf_token},
    )
    cookie_name = get_settings().session_cookie_name
    _require(
        response.status_code == 204 and not app.cookies.get(cookie_name),
        "logout did not clear the first-party session",
    )
    _require(app.get("/api/v1/me").status_code == 401, "logout left /me authenticated")
    _require(
        app.get("/api/v1/me", headers={"Cookie": f"{cookie_name}={token}"}).status_code == 401,
        "revoked session cookie was still usable",
    )
    with get_admin_session_factory()() as admin:
        revoked = admin.execute(
            text("SELECT revoked_at FROM identity.web_sessions WHERE id = :id"),
            {"id": parse_session_token(token).session_id},
        ).scalar_one_or_none()
        _require(revoked is not None, "logout revocation was not durable")


def test_live_keycloak_code_pkce_login_logout_and_stable_identity(
    migrated_database: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    stage = "local-only configuration"
    try:
        settings = get_settings()
        assert_safe_test_target(settings.migration_db_url)
        assert_safe_test_target(settings.runtime_db_url)
        provider = settings.oidc_providers.get("keycloak")
        _require(
            settings.environment == "test"
            and settings.api_public_base_url == APP_ORIGIN
            and settings.web_base_url == WEB_ORIGIN
            and not settings.session_cookie_secure
            and provider is not None
            and provider.issuer == ISSUER
            and provider.client_id == CLIENT_ID
            and provider.client_secret is None,
            "live OIDC requires the dedicated test DB and checked-in loopback Keycloak profile",
        )
        # Prevent environment proxy settings from redirecting the loopback IdP calls.
        monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
        monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
        for logger in ("httpx", "httpcore", "authlib", "sqlalchemy.engine"):
            caplog.set_level(logging.CRITICAL, logger=logger)
        with TestClient(
            create_app(), base_url=APP_ORIGIN, raise_server_exceptions=False,
        ) as app:
            stage = "first real Keycloak login"
            with httpx.Client(follow_redirects=False, trust_env=False, timeout=20) as provider_http:
                _check_discovery(provider_http)
                first_id, first_token = _login_once(app, provider_http)
            stage = "first application logout"
            _logout(app, first_token)

            stage = "second real Keycloak login"
            # Fresh provider cookies force another real login form and code exchange.
            with httpx.Client(follow_redirects=False, trust_env=False, timeout=20) as provider_http:
                second_id, second_token = _login_once(app, provider_http)
            _require(
                first_id == second_id
                and parse_session_token(first_token).session_id
                != parse_session_token(second_token).session_id,
                "repeat authentication did not preserve the stable internal user",
            )
            stage = "second application logout"
            _logout(app, second_token)
    except Exception:
        # Provider URLs/HTML, authorization codes, raw tokens and exception details
        # must never escape into test output. Stage names are fixed and safe.
        pytest.fail(f"Live OIDC failed during {stage}", pytrace=False)
