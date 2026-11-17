from __future__ import annotations

import base64
import hashlib
import hmac


def make_csrf_token(session_token: str, csrf_secret: str) -> str:
    digest = hmac.new(
        csrf_secret.encode("utf-8"),
        session_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_csrf_token(session_token: str, csrf_secret: str, candidate: str) -> bool:
    expected = make_csrf_token(session_token, csrf_secret)
    return hmac.compare_digest(expected, candidate)
