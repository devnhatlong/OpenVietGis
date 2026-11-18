from datetime import UTC, datetime, timedelta
from uuid import uuid4

from openvietgis_api.domains.authorization.domain import (
    ServiceCredential,
    ServicePrincipalStatus,
    service_credential_is_usable,
)
from openvietgis_api.security.secrets import (
    digest_secret,
    generate_service_credential_secret,
    parse_service_credential_id,
    safe_prefix,
    verify_secret,
)


def _credential(*, expires_at=None, revoked_at=None) -> ServiceCredential:
    now = datetime.now(UTC)
    return ServiceCredential(
        id=uuid4(),
        organization_id=uuid4(),
        service_principal_id=uuid4(),
        name="automation",
        prefix="ovgsvc-test",
        secret_hash=b"x" * 32,
        permission_ceiling=None,
        created_at=now,
        expires_at=expires_at,
        last_used_at=None,
        revoked_at=revoked_at,
    )


def test_service_secret_encodes_nonsecret_credential_id_and_verifies_hash() -> None:
    credential_id = uuid4()
    secret = generate_service_credential_secret(credential_id)

    assert secret.startswith("ovgsvc" + credential_id.hex + "_")
    assert parse_service_credential_id(secret) == credential_id
    assert len(secret) >= 70
    assert safe_prefix(secret).startswith("ovgsvc")
    assert verify_secret(secret, digest_secret(secret))
    assert not verify_secret(secret + "tampered", digest_secret(secret))


def test_service_secret_rejects_unrecognized_or_malformed_tokens() -> None:
    for candidate in ("", "abc", "ovgsvc_", "ovgsvcnot-a-uuid_secret"):
        try:
            parse_service_credential_id(candidate)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed service credential accepted")


def test_service_credential_expiry_and_revocation_are_immediate() -> None:
    now = datetime.now(UTC)
    assert service_credential_is_usable(_credential(expires_at=now + timedelta(minutes=1)), now)
    assert not service_credential_is_usable(_credential(expires_at=now - timedelta(seconds=1)), now)
    assert not service_credential_is_usable(_credential(revoked_at=now), now)


def test_service_principal_status_is_explicit() -> None:
    assert ServicePrincipalStatus.ACTIVE.value == "active"
    assert ServicePrincipalStatus.REVOKED.value == "revoked"
