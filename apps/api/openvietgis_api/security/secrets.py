from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_secret(prefix: str, *, bytes_of_entropy: int = 32) -> str:
    if not prefix or "_" in prefix:
        raise ValueError("secret prefix must be non-empty and cannot contain underscore")
    return f"{prefix}_{secrets.token_urlsafe(bytes_of_entropy)}"


def digest_secret(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def verify_secret(secret: str, expected_digest: bytes) -> bool:
    return hmac.compare_digest(digest_secret(secret), expected_digest)


def safe_prefix(secret: str, *, visible_chars: int = 12) -> str:
    if visible_chars < 4:
        raise ValueError("visible_chars must be at least 4")
    return secret[:visible_chars]
