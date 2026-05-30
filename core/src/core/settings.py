from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core settings."""

    # Server settings
    core_server_host: str
    core_server_port: int
    database_url: str
    core_jwt_algorithm: str
    core_jwt_type: str
    core_jwt_secret_key: str
    core_jwt_expiration_timedelta_minutes: int
    webapp_url: str
    cookie_domain: str

    # Development mode (controls cookie security settings)
    dev_mode: bool = False

    @property
    def cookie_secure(self) -> bool:
        """Return True for HTTPS-only cookies in production."""
        return not self.dev_mode

    @property
    def cookie_samesite(self) -> Literal["lax", "strict", "none"] | None:
        """Return 'none' for cross-origin in production, 'lax' for dev."""
        return "lax" if self.dev_mode else "none"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Get settings cached."""
    return Settings()
