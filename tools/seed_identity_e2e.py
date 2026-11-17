from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from tools.reset_dev import assert_safe_target


def main() -> int:
    from openvietgis_api.config import get_settings

    settings = get_settings()
    assert_safe_target(settings.environment, settings.migration_db_url)

    engine = create_engine(settings.migration_db_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE platform.installation_state
                    SET initialized_at = COALESCE(initialized_at, :now),
                        updated_at = :now
                    WHERE singleton_key = 'installation'
                    """
                ),
                {"now": datetime.now(UTC)},
            )
    finally:
        engine.dispose()

    print("P1 E2E installation marker initialized (development/test only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
