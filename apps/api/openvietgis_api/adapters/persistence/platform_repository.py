from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from openvietgis_api.domains.bootstrap.domain import InstallationState


class SqlPlatformRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_installation_state(self, *, for_update: bool = False) -> InstallationState:
        suffix = " FOR UPDATE" if for_update else ""
        row = (
            self._session.execute(
                text(
                    """
                    SELECT singleton_key, initialized_at, initial_organization_id,
                           initialized_by_user_id, updated_at
                    FROM platform.installation_state
                    WHERE singleton_key = 'installation'
                    """
                    + suffix
                )
            )
            .mappings()
            .one()
        )
        return InstallationState(
            singleton_key=row["singleton_key"],
            initialized_at=row["initialized_at"],
            initial_organization_id=row["initial_organization_id"],
            initialized_by_user_id=row["initialized_by_user_id"],
            updated_at=row["updated_at"],
        )

    def is_initialized(self) -> bool:
        return self.get_installation_state().initialized_at is not None
