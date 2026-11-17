from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OidcProviderSettings(BaseModel):
    issuer: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    client_secret: SecretStr | None = None
    display_name: str = Field(min_length=1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENVIETGIS_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test"]
    database_url: str = Field(min_length=1)
    migration_database_url: str | None = None
    runtime_database_url: str | None = None

    web_base_url: str = "http://127.0.0.1:5173"
    api_public_base_url: str = "http://127.0.0.1:8000"
    session_cookie_name: str = "ovg_session"
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=28_800, ge=300, le=604_800)

    application_session_secret: SecretStr
    csrf_secret: SecretStr
    bootstrap_secret: SecretStr
    oidc_providers: dict[str, OidcProviderSettings] = Field(default_factory=dict)

    @property
    def migration_db_url(self) -> str:
        return self.migration_database_url or self.database_url

    @property
    def runtime_db_url(self) -> str:
        return self.runtime_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]