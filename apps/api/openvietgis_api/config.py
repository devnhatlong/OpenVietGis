from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
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

    environment: Literal["development", "test", "production"]
    database_url: str = Field(min_length=1)
    migration_database_url: str | None = None
    runtime_database_url: str | None = None

    web_base_url: str = "http://127.0.0.1:5173"
    api_public_base_url: str = "http://127.0.0.1:8000"
    session_cookie_name: str = "ovg_session"
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=28_800, ge=300, le=604_800)
    artifact_store_dir: str = "/tmp/openvietgis-artifacts"

    application_session_secret: SecretStr
    csrf_secret: SecretStr
    bootstrap_secret: SecretStr
    oidc_providers: dict[str, OidcProviderSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_production_profile(self) -> Settings:
        if self.environment != "production":
            return self
        if not self.migration_database_url or not self.runtime_database_url:
            raise ValueError(
                "production requires explicit migration_database_url and runtime_database_url"
            )
        if self.migration_database_url == self.runtime_database_url:
            raise ValueError(
                "production runtime and migration database credentials must be distinct"
            )
        if not self.session_cookie_secure:
            raise ValueError("production requires secure session cookies")
        return self

    @property
    def migration_db_url(self) -> str:
        return self.migration_database_url or self.database_url

    @property
    def runtime_db_url(self) -> str:
        if not self.runtime_database_url:
            raise RuntimeError("An explicit non-privileged runtime database URL is required")
        if self.runtime_database_url == self.migration_db_url:
            raise RuntimeError("Runtime and migration database credentials must be distinct")
        return self.runtime_database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
