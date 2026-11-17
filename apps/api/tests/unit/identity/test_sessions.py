from uuid import uuid4

import pytest

from openvietgis_api.security.sessions import (
    issue_session_token,
    parse_session_token,
    verify_session_token,
)


def test_session_token_round_trip_and_digest_verification() -> None:
    session_id = uuid4()
    token, digest = issue_session_token(session_id)

    parsed = verify_session_token(token, digest)

    assert parsed.session_id == session_id
    assert parsed.secret not in repr(digest)


def test_session_token_rejects_tampering() -> None:
    session_id = uuid4()
    token, digest = issue_session_token(session_id)

    with pytest.raises(ValueError):
        verify_session_token(token + "x", digest)

    with pytest.raises(ValueError):
        parse_session_token("not-a-session")
