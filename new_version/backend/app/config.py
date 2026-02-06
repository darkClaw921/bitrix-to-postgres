"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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

    # Database — supports both PostgreSQL and MySQL
    # PostgreSQL: postgresql+asyncpg://user:pass@host:5432/db
    # MySQL: mysql+aiomysql://user:pass@host:3306/db
    database_url: str = Field(
        ...,
        description="Database connection string (PostgreSQL or MySQL)",
    )
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Bitrix24
    bitrix_webhook_url: str = Field(..., description="Bitrix24 webhook URL")

    # Sync Settings
    sync_batch_size: int = 50
    sync_default_interval_minutes: int = 30

    # AI / OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Charts
    chart_query_timeout_seconds: int = 5
    chart_max_rows: int = 10000

    # Dashboards
    dashboard_secret_key: str = "change-me-in-production"
    dashboard_token_expiry_minutes: int = 30

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    @property
    def db_dialect(self) -> str:
        """Detect database dialect from URL."""
        url = self.database_url.lower()
        if url.startswith("mysql"):
            return "mysql"
        return "postgresql"

    @property
    def async_database_url(self) -> str:
        """Return async database URL for SQLAlchemy.

        Auto-adds async driver prefix if missing:
          postgresql:// → postgresql+asyncpg://
          mysql://      → mysql+aiomysql://
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("mysql://"):
            return url.replace("mysql://", "mysql+aiomysql://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
