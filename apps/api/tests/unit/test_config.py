import pytest
from pydantic import ValidationError

from openvietgis_api.config import Settings


@pytest.fixture(autouse=True)
def isolate_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENVIETGIS_OIDC_PROVIDERS", raising=False)


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


def _proposed_production_kwargs() -> dict:
    return {
        "environment": "production",
        "database_url": "postgresql+psycopg://openvietgis_runtime:synthetic@postgres:5432/sample",
        "runtime_database_url": (
            "postgresql+psycopg://openvietgis_runtime:synthetic@postgres:5432/sample"
        ),
        "migration_database_url": None,
        "session_cookie_secure": True,
        "web_base_url": "https://example.invalid",
        "api_public_base_url": "https://example.invalid",
        "oidc_providers": {
            "fixture": {
                "issuer": "https://identity.example.invalid/realms/synthetic",
                "client_id": "fixture",
                "display_name": "Synthetic",
            }
        },
        "application_session_secret": "synthetic-example-session-only-" * 2,
        "csrf_secret": "synthetic-example-csrf-only-" * 2,
        "bootstrap_secret": "synthetic-example-bootstrap-only-" * 2,
    }


def test_proposed_production_api_has_no_migration_authority() -> None:
    settings = Settings(**_proposed_production_kwargs(), _env_file=None)
    assert settings.runtime_db_url == settings.database_url
    with pytest.raises(RuntimeError, match="explicit owner"):
        _ = settings.migration_db_url


def test_proposed_production_migration_is_distinct_and_same_database() -> None:
    values = _proposed_production_kwargs()
    owner = "postgresql+psycopg://owner:synthetic@postgres:5432/sample"
    values["migration_database_url"] = owner
    settings = Settings(**values, _env_file=None)
    assert settings.migration_db_url == owner
    assert settings.runtime_db_url == settings.database_url
    values["migration_database_url"] = owner.replace("/sample", "/unrelated")
    with pytest.raises(ValidationError, match="same DB"):
        Settings(**values, _env_file=None)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("session_cookie_secure", False, "secure"),
        ("web_base_url", "http://example.invalid", "HTTPS"),
        ("api_public_base_url", "https://user:secret@example.invalid", "HTTPS"),
        ("application_session_secret", "short", "distinct"),
        ("oidc_providers", {}, "identity provider"),
        (
            "oidc_providers",
            {
                "bad": {
                    "issuer": "http://example.invalid",
                    "client_id": "fixture",
                    "display_name": "Synthetic",
                }
            },
            "HTTPS",
        ),
        (
            "database_url",
            "postgresql+psycopg://owner:synthetic@postgres:5432/sample",
            "runtime URL",
        ),
        ("runtime_database_url", None, "runtime URL"),
    ],
)
def test_proposed_production_rejects_unsafe_config(field, value, message) -> None:
    values = _proposed_production_kwargs()
    values[field] = value
    with pytest.raises(ValidationError, match=message):
        Settings(**values, _env_file=None)


def test_proposed_production_rejects_owner_as_runtime() -> None:
    values = _proposed_production_kwargs()
    owner = "postgresql+psycopg://owner:synthetic@postgres:5432/sample"
    values["database_url"] = values["runtime_database_url"] = owner
    with pytest.raises(ValidationError, match="restricted role") as error:
        Settings(**values, _env_file=None)
    assert owner not in str(error.value)
