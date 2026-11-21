import pytest
from pydantic import ValidationError

from openvietgis_api.config import Settings


def _valid_settings_kwargs() -> dict[str, str]:
    return {
        "environment": "development",
        "database_url": "postgresql+psycopg://example/example",
        "application_session_secret": "session-secret",
        "csrf_secret": "csrf-secret",
        "bootstrap_secret": "bootstrap-secret",
    }


def test_settings_require_security_and_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "OPENVIETGIS_ENVIRONMENT",
        "OPENVIETGIS_DATABASE_URL",
        "OPENVIETGIS_APPLICATION_SESSION_SECRET",
        "OPENVIETGIS_CSRF_SECRET",
        "OPENVIETGIS_BOOTSTRAP_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_unknown_environment() -> None:
    values = _valid_settings_kwargs()
    values["environment"] = "staging"
    with pytest.raises(ValidationError):
        Settings(**values, _env_file=None)


def test_production_requires_distinct_databases_and_secure_cookie() -> None:
    values = _valid_settings_kwargs()
    values.update(
        environment="production",
        migration_database_url="postgresql+psycopg://admin/db",
        runtime_database_url="postgresql+psycopg://runtime/db",
        session_cookie_secure=True,
    )
    settings = Settings(**values, _env_file=None)
    assert settings.environment == "production"

    insecure = dict(values)
    insecure["session_cookie_secure"] = False
    with pytest.raises(ValidationError, match="secure session cookies"):
        Settings(**insecure, _env_file=None)

    same_database = dict(values)
    same_database["runtime_database_url"] = same_database["migration_database_url"]
    with pytest.raises(ValidationError, match="must be distinct"):
        Settings(**same_database, _env_file=None)


def test_settings_reject_empty_database_url() -> None:
    values = _valid_settings_kwargs()
    values["database_url"] = ""
    with pytest.raises(ValidationError):
        Settings(**values, _env_file=None)


def test_runtime_url_must_be_explicit_and_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENVIETGIS_RUNTIME_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENVIETGIS_MIGRATION_DATABASE_URL", raising=False)
    settings = Settings(**_valid_settings_kwargs(), _env_file=None)

    with pytest.raises(RuntimeError, match="explicit"):
        _ = settings.runtime_db_url
    assert settings.migration_db_url == settings.database_url
    settings.runtime_database_url = settings.database_url
    with pytest.raises(RuntimeError, match="distinct"):
        _ = settings.runtime_db_url
