from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field("development", alias="APP_ENV")

    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")

    database_url: str = Field(..., alias="DATABASE_URL")

    cors_origins: List[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

