from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENVIETGIS_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test"]
    database_url: str = Field(min_length=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
