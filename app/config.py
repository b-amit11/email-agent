from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings for the app, read from the .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AI model
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"

    # Supabase database
    supabase_url: str = ""
    supabase_key: str = ""

    # Gmail API
    gmail_credentials_path: str = "credentials/credentials.json"
    gmail_token_path: str = "credentials/token.json"


@lru_cache
def get_settings() -> Settings:
    """Load the settings once and reuse them everywhere."""
    return Settings()
