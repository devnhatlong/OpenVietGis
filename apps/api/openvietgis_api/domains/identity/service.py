from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import NoReturn
from uuid import UUID, uuid4

from openvietgis_api.domains.audit.domain import AuditEvent, AuditOutcome
from openvietgis_api.domains.audit.ports import AuditRepository
from openvietgis_api.domains.identity.domain import (
    IdentityLink,
    UnlinkIdentityResult,
    User,
    UserStatus,
    WebSession,
)
from openvietgis_api.domains.identity.ports import IdentityRepository
from openvietgis_api.domains.tenancy.domain import ActorType
from openvietgis_api.security.sessions import issue_session_token


@dataclass(frozen=True, slots=True)
class ExternalIdentityClaims:
    issuer: str
    subject: str
    display_name: str
    email: str | None
    email_verified: bool


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    identity_link: IdentityLink
    session_token: str
    web_session: WebSession


class IdentityConflictError(ValueError):
    pass


class IdentityLinkConflictError(IdentityConflictError):
    """A confirmed linking denial already recorded in the current transaction."""


class CannotUnlinkLastIdentityError(ValueError):
    pass


class IdentityService:
    def __init__(
        self,
        repository: IdentityRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self._repository = repository
        self._audit_repository = audit_repository

    def login(
        self,
        claims: ExternalIdentityClaims,
        *,
        session_ttl_seconds: int,
        now: datetime | None = None,
    ) -> LoginResult:
        now = now or datetime.now(UTC)
        existing = self._repository.find_by_external_identity(
            issuer=claims.issuer,
            subject=claims.subject,
        )
        if existing is None:
            user = User(
                id=uuid4(),
                display_name=claims.display_name,
                email_snapshot=claims.email,
                status=UserStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            link = IdentityLink(
                id=uuid4(),
                user_id=user.id,
                issuer=claims.issuer,
                subject=claims.subject,
                email_snapshot=claims.email,
                email_verified=claims.email_verified,
                display_name_snapshot=claims.display_name,
                created_at=now,
                last_login_at=now,
            )
            self._repository.create_user_with_identity(user, link)
        else:
            user, link = existing
            if user.status != UserStatus.ACTIVE:
                raise IdentityConflictError("user is disabled")
            # Invitation targeting uses this authenticated link's current verified
            # provider claims, not the snapshot from its first-ever authentication.
            link = replace(
                link,
                email_snapshot=claims.email,
                email_verified=claims.email_verified,
                display_name_snapshot=claims.display_name,
                last_login_at=now,
            )
            self._repository.refresh_identity_login(link)

        session_id = uuid4()
        raw_token, secret_hash = issue_session_token(session_id)
        web_session = WebSession(
            id=session_id,
            user_id=user.id,
            identity_link_id=link.id,
            secret_hash=secret_hash,
            issued_at=now,
            expires_at=now + timedelta(seconds=session_ttl_seconds),
            last_seen_at=None,
            revoked_at=None,
        )
        self._repository.create_web_session(web_session)
        return LoginResult(
            user=user,
            identity_link=link,
            session_token=raw_token,
            web_session=web_session,
        )

    def link_identity(
        self,
        *,
        user_id: UUID,
        claims: ExternalIdentityClaims,
        now: datetime | None = None,
    ) -> IdentityLink:
        now = now or datetime.now(UTC)
        user = self._repository.get_user(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise IdentityConflictError("user not found")
        existing = self._repository.find_by_external_identity(
            issuer=claims.issuer,
            subject=claims.subject,
        )
        if existing is not None:
            existing_user, existing_link = existing
            if existing_user.id != user_id:
                self._deny_link_conflict(user, now)
            return existing_link

        link = IdentityLink(
            id=uuid4(),
            user_id=user_id,
            issuer=claims.issuer,
            subject=claims.subject,
            email_snapshot=claims.email,
            email_verified=claims.email_verified,
            display_name_snapshot=claims.display_name,
            created_at=now,
            last_login_at=now,
        )
        if not self._repository.try_add_identity_link(link):
            # The uniqueness constraint detected a concurrent claimant. A separate
            # statement re-resolves the winner at READ COMMITTED without aborting
            # this transaction. Same-user retries are harmless; all other outcomes
            # are denied without transferring or exposing an existing identity.
            existing = self._repository.find_by_external_identity(
                issuer=claims.issuer,
                subject=claims.subject,
            )
            if existing is not None and existing[0].id == user_id:
                return existing[1]
            self._deny_link_conflict(user, now)
        self._audit_repository.append(
            AuditEvent(
                id=uuid4(),
                organization_id=None,
                actor_type=ActorType.HUMAN,
                actor_id=user_id,
                actor_display_snapshot=user.display_name,
                action="identity.link",
                resource_type="identity_link",
                resource_id=link.id,
                outcome=AuditOutcome.SUCCESS,
                metadata={"issuer": claims.issuer},
                created_at=now,
            )
        )
        return link

    def _deny_link_conflict(self, user: User, now: datetime) -> NoReturn:
        # Do not record the other user, foreign link ID, issuer/subject, email,
        # or credentials. The initiating actor and fixed reason are sufficient.
        self._audit_repository.append(
            AuditEvent(
                id=uuid4(),
                organization_id=None,
                actor_type=ActorType.HUMAN,
                actor_id=user.id,
                actor_display_snapshot=user.display_name,
                action="identity.link",
                resource_type="identity_link",
                resource_id=None,
                outcome=AuditOutcome.DENIED,
                metadata={"reason": "identity_conflict"},
                created_at=now,
            )
        )
        raise IdentityLinkConflictError("external identity cannot be linked")

    def unlink_identity(
        self,
        *,
        user_id: UUID,
        identity_link_id: UUID,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(UTC)
        user = self._repository.get_user(user_id)
        if user is None:
            raise IdentityConflictError("user not found")
        result = self._repository.unlink_identity(
            user_id=user_id,
            identity_link_id=identity_link_id,
        )
        if result == UnlinkIdentityResult.LAST_IDENTITY:
            raise CannotUnlinkLastIdentityError("cannot unlink the last usable identity")
        if result != UnlinkIdentityResult.UNLINKED:
            raise IdentityConflictError("identity link not found")
        self._audit_repository.append(
            AuditEvent(
                id=uuid4(),
                organization_id=None,
                actor_type=ActorType.HUMAN,
                actor_id=user_id,
                actor_display_snapshot=user.display_name,
                action="identity.unlink",
                resource_type="identity_link",
                resource_id=identity_link_id,
                outcome=AuditOutcome.SUCCESS,
                metadata={},
                created_at=now,
            )
        )
