"""
Application configuration using Pydantic Settings

Settings are loaded from environment variables (or .env file)
This configuration is:
1. Validated at startup (fail fast if misconfigured)
2. Type-safe throughout the application
3. Documented via type hints
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Environment variables are matched case-insensitively.
    Example: REDIS_URL env var redis_url_attribute
    """

    # Application Mode
    stash_mode: str = "local" # local, dev, production

    # Redis configuration
    redis_url: str = "redis://localhost:6379"

    # TTL limits (in seconds)
    default_ttl_seconds: int = 3600     # 1 hour
    min_ttl_seconds: int = 1            # 1 second
    max_ttl_seconds: int = 86400        # 1 day

    # Payload limits (in bytes)
    max_payload_bytes: int = 1_048_576  # 1 MB

    # Rate Limits
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60

    # Logging
    log_level: str = "INFO"
    log_format: str = "json" # json or console

    # Tell Pydantic where to find the .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    class Settings(BaseSettings):
    # ... existing fields ...
    
        # User database (SQLite for local, PostgreSQL URL for production)
        users_db_path: str = "users.db"

# Cache the settings instance so we don't re-read .env on every request
@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Using @lru_cache ensures we only parse environment variables once.
    """
    return Settings()