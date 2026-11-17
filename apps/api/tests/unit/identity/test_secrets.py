from openvietgis_api.security.secrets import (
    digest_secret,
    generate_secret,
    safe_prefix,
    verify_secret,
)


def test_secret_generation_hash_and_verification() -> None:
    secret = generate_secret("svc")
    digest = digest_secret(secret)

    assert secret.startswith("svc_")
    assert len(digest) == 32
    assert verify_secret(secret, digest)
    assert not verify_secret(secret + "x", digest)
    assert safe_prefix(secret) == secret[:12]


def test_secret_prefix_validation() -> None:
    try:
        generate_secret("bad_prefix")
    except ValueError as exc:
        assert "prefix" in str(exc)
    else:
        raise AssertionError("expected invalid prefix")
