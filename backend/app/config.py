from functools import lru_cache
from typing import Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field("development", alias="APP_ENV")

    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")

    database_url: str = Field(..., alias="DATABASE_URL")

    cors_origins_raw: str = Field("*", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> List[str]:
        raw = self.cors_origins_raw
        if not raw:
            return ["*"]
        if isinstance(raw, str):
            if raw.startswith("[") and raw.endswith("]"):
                # Attempt JSON parsing for backwards compatibility
                try:
                    import json

                    data = json.loads(raw)
                    if isinstance(data, list):
                        return [str(item) for item in data if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            parts = [part.strip() for part in raw.split(",") if part.strip()]
            return parts or ["*"]
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        return ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
