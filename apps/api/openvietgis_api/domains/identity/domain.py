from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class UnlinkIdentityResult(StrEnum):
    UNLINKED = "unlinked"
    LAST_IDENTITY = "last_identity"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    display_name: str
    email_snapshot: str | None
    status: UserStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IdentityLink:
    id: UUID
    user_id: UUID
    issuer: str
    subject: str
    email_snapshot: str | None
    email_verified: bool
    display_name_snapshot: str | None
    created_at: datetime
    last_login_at: datetime | None


@dataclass(frozen=True, slots=True)
class WebSession:
    id: UUID
    user_id: UUID
    identity_link_id: UUID
    secret_hash: bytes
    issued_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None
