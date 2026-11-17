from openvietgis_api.security.csrf import make_csrf_token, verify_csrf_token


def test_csrf_token_is_session_bound() -> None:
    secret = "test-csrf-secret"
    token = make_csrf_token("session-a", secret)

    assert verify_csrf_token("session-a", secret, token)
    assert not verify_csrf_token("session-b", secret, token)
    assert not verify_csrf_token("session-a", "other-secret", token)
