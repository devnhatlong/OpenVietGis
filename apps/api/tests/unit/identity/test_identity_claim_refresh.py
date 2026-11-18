from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

from openvietgis_api.domains.identity.domain import IdentityLink, User, UserStatus
from openvietgis_api.domains.identity.service import ExternalIdentityClaims, IdentityService


def test_returning_oidc_login_refreshes_current_identity_claims() -> None:
    created = datetime.now(UTC) - timedelta(days=10)
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        display_name="User",
        email_snapshot="old@example.test",
        status=UserStatus.ACTIVE,
        created_at=created,
        updated_at=created,
    )
    original = IdentityLink(
        id=uuid4(),
        user_id=user.id,
        issuer="https://issuer.example",
        subject="stable-subject",
        email_snapshot="old@example.test",
        email_verified=True,
        display_name_snapshot="Old Display",
        created_at=created,
        last_login_at=created,
    )
    repository = Mock()
    repository.find_by_external_identity.return_value = (user, original)
    service = IdentityService(repository, Mock())
    result = service.login(
        ExternalIdentityClaims(
            issuer=original.issuer,
            subject=original.subject,
            email="changed@example.test",
            email_verified=False,
            display_name="New Display",
        ),
        session_ttl_seconds=3600,
        now=now,
    )

    assert result.identity_link.id == original.id
    assert result.identity_link.email_snapshot == "changed@example.test"
    assert result.identity_link.email_verified is False
    assert result.identity_link.display_name_snapshot == "New Display"
    assert result.identity_link.last_login_at == now
    assert result.web_session.identity_link_id == original.id
    repository.refresh_identity_login.assert_called_once_with(result.identity_link)
    repository.create_web_session.assert_called_once_with(result.web_session)
    repository.create_user_with_identity.assert_not_called()
