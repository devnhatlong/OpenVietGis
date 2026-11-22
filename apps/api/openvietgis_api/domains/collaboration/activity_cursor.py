"""Bounded keyset activity paging. A cursor is not an authorization grant."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from openvietgis_api.domains.authorization.context import AuthorizationContext
from openvietgis_api.domains.platform_errors import PlatformValidationError

CURSOR_MAX_LENGTH = 512
CURSOR_LIFETIME = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class ActivityCursor:
    cutoff: datetime
    created_at: datetime
    stream: int
    id: UUID


def cursor_scope(context: AuthorizationContext) -> str:
    """Associate continuation with current actor, credential and tenant scope.

    This digest is not a MAC. Every page still requires live project read
    authorization and a visible matching boundary. The client can choose
    an earlier cutoff but cannot use a cursor to broaden its scope.
    """
    raw = "|".join(
        str(value)
        for value in (
            context.actor.actor_type,
            context.actor.actor_id,
            context.credential_id,
            context.organization_id,
            context.project_id,
        )
    )
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def encode_cursor(cursor: ActivityCursor, scope: str) -> str:
    encoded = json.dumps(
        [1, scope, _time(cursor.cutoff), _time(cursor.created_at), cursor.stream, str(cursor.id)],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def decode_cursor(token: str, scope: str, now: datetime) -> ActivityCursor:
    try:
        if (
            not 1 <= len(token) <= CURSOR_MAX_LENGTH
            or re.fullmatch("[A-Za-z0-9_-]+", token) is None
        ):
            raise ValueError("invalid encoding")
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        values = json.loads(raw.decode("ascii"))
        if not isinstance(values, list) or len(values) != 6:
            raise ValueError("invalid structure")
        version, supplied_scope, cutoff, created_at, stream, row_id = values
        if (
            type(version) is not int
            or version != 1
            or supplied_scope != scope
            or type(stream) is not int
            or stream not in (0, 1)
            or type(cutoff) is not str
            or type(created_at) is not str
            or type(row_id) is not str
        ):
            raise ValueError("invalid fields")
        cursor = ActivityCursor(
            datetime.fromisoformat(cutoff), datetime.fromisoformat(created_at), stream, UUID(row_id)
        )
        if (
            cursor.cutoff.tzinfo is None
            or cursor.created_at.tzinfo is None
            or cursor.cutoff > now
            or now - cursor.cutoff > CURSOR_LIFETIME
            or cursor.created_at > cursor.cutoff
            or encode_cursor(cursor, scope) != token
        ):
            raise ValueError("invalid time window or noncanonical cursor")
        return cursor
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError, binascii.Error):
        raise PlatformValidationError(
            "activity continuation unavailable; refresh the activity list",
            code="INVALID_ACTIVITY_CURSOR",
        ) from None
