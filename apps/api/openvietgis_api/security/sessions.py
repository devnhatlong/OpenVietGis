from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from openvietgis_api.security.secrets import digest_secret, generate_secret, verify_secret


@dataclass(frozen=True, slots=True)
class ParsedSessionToken:
    session_id: UUID
    secret: str


def issue_session_token(session_id: UUID) -> tuple[str, bytes]:
    secret = generate_secret("s", bytes_of_entropy=32)
    return f"ovgs_{session_id.hex}.{secret}", digest_secret(secret)


def parse_session_token(token: str) -> ParsedSessionToken:
    try:
        prefix, secret = token.split(".", maxsplit=1)
        marker, session_hex = prefix.split("_", maxsplit=1)
        if marker != "ovgs":
            raise ValueError
        return ParsedSessionToken(session_id=UUID(hex=session_hex), secret=secret)
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid OpenVietGIS session token") from exc


def verify_session_token(token: str, expected_digest: bytes) -> ParsedSessionToken:
    parsed = parse_session_token(token)
    if not verify_secret(parsed.secret, expected_digest):
        raise ValueError("invalid OpenVietGIS session token")
    return parsed
