"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Bitrix Sync Service"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Database
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection string (asyncpg)",
    )
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Supabase Auth
    supabase_url: str = Field(..., description="Supabase API URL")
    supabase_key: str = Field(..., description="Supabase anon key")
    supabase_jwt_secret: str = Field(..., description="JWT secret for token validation")

    # Bitrix24
    bitrix_webhook_url: str = Field(..., description="Bitrix24 webhook URL")

    # Sync Settings
    sync_batch_size: int = 50
    sync_default_interval_minutes: int = 30

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    @property
    def async_database_url(self) -> str:
        """Return async database URL for SQLAlchemy."""
        return str(self.database_url)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
