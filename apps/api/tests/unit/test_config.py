import pytest
from pydantic import ValidationError

from openvietgis_api.config import Settings


def test_settings_require_environment_and_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENVIETGIS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("OPENVIETGIS_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://example/example",
            _env_file=None,
        )


def test_settings_reject_empty_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="development", database_url="", _env_file=None)
