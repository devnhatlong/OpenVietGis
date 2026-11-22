from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.collaboration.activity_cursor import (
    ActivityCursor,
    cursor_scope,
    decode_cursor,
    encode_cursor,
)
from openvietgis_api.domains.platform_errors import PlatformValidationError


def test_activity_cursor_roundtrip_scope_expiry_and_order():
    context = AuthorizationContext(Actor("human", uuid4(), "Fixture"), uuid4(), project_id=uuid4())
    now = datetime.now(UTC)
    value = ActivityCursor(now, now - timedelta(seconds=1), 1, uuid4())
    scope = cursor_scope(context)
    token = encode_cursor(value, scope)
    assert decode_cursor(token, scope, now) == value
    for foreign in (
        replace(context, organization_id=uuid4()),
        replace(context, project_id=uuid4()),
        replace(context, actor=Actor("human", uuid4(), "Other")),
        replace(context, credential_id=uuid4()),
    ):
        with pytest.raises(PlatformValidationError, match="refresh"):
            decode_cursor(token, cursor_scope(foreign), now)
    for bad_now in (now - timedelta(seconds=1), now + timedelta(minutes=16)):
        with pytest.raises(PlatformValidationError, match="refresh"):
            decode_cursor(token, scope, bad_now)
    for bad in (replace(value, created_at=now + timedelta(seconds=1)), replace(value, stream=2)):
        with pytest.raises(PlatformValidationError):
            decode_cursor(encode_cursor(bad, scope), scope, now)


@pytest.mark.parametrize("token", ["", "?", "A", "A" * 513, "e30", "W10", "W10="])
def test_activity_cursor_invalid_encoding(token):
    with pytest.raises(PlatformValidationError) as exc:
        decode_cursor(token, "0" * 64, datetime.now(UTC))
    assert exc.value.code == "INVALID_ACTIVITY_CURSOR"
