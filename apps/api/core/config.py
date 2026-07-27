"""Typed application settings, loaded once from the environment.

Every tunable the app reads lives here. Modules import ``settings`` rather than
touching ``os.environ``, so configuration is discoverable in one file and
mistyped env vars fail loudly at startup instead of silently at 3am.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Runtime -----------------------------------------------------------
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # --- HTTP --------------------------------------------------------------
    # Comma-separated in the env; split in `cors_origins`.
    allowed_origins: str = "http://localhost:3000"

    # --- Providers ---------------------------------------------------------
    # Optional so the app boots (and tests run) without a key; the LLM client
    # raises a clear error only when something actually tries to call it.
    anthropic_api_key: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor — tests can clear it with ``get_settings.cache_clear()``."""
    return Settings()


settings = get_settings()
