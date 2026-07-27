"""Typed application settings, loaded once from the environment.

Every tunable the app reads lives here. Modules import ``settings`` rather than
touching ``os.environ``, so configuration is discoverable in one file and
mistyped env vars fail loudly at startup instead of silently at 3am.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["anthropic", "xai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Runtime -----------------------------------------------------------
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # --- HTTP --------------------------------------------------------------
    # Comma-separated in the env; split in `cors_origins`.
    allowed_origins: str = "http://localhost:3000"

    # --- Model providers ---------------------------------------------------
    # Keys are optional so the app boots (and the test suite runs) without them.
    # A provider with no key is skipped when the fallback chain is built, and
    # having none configured fails at the call site with a clear message.
    anthropic_api_key: str | None = None
    xai_api_key: str | None = None

    #: Provider tried first.
    llm_provider: ProviderName = "anthropic"
    #: Comma-separated providers to try when the primary cannot serve at all
    #: (exhausted credit, rejected key, hard capacity). Empty disables failover.
    llm_fallback_providers: str = "xai"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def llm_provider_enum(self):
        from core.providers import Provider

        return Provider(self.llm_provider)

    @property
    def llm_fallback_enums(self) -> list:
        """Parsed fallback chain, ignoring blanks and unknown names.

        An unrecognised name is skipped rather than raised on: a typo in an
        optional fallback should not take the app down while the primary
        provider is working perfectly well.
        """
        from core.providers import Provider

        result = []
        for raw in self.llm_fallback_providers.split(","):
            name = raw.strip().lower()
            if not name:
                continue
            try:
                result.append(Provider(name))
            except ValueError:
                continue
        return result


@lru_cache
def get_settings() -> Settings:
    """Cached accessor — tests can clear it with ``get_settings.cache_clear()``."""
    return Settings()


settings = get_settings()
