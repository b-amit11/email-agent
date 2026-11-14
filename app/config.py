from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings for the app, read from the .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Ignore stray spaces around a value, such as "KEY= value".
        str_strip_whitespace=True,
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

    # Review dashboard login. Without a password nobody can log in.
    dashboard_password: str = ""
    # Set to true once the site is served over https, so the login cookie
    # is never sent over a plain connection.
    cookie_secure: bool = False

    # How often the backend checks Gmail by itself, in seconds. 0 turns it off.
    poll_interval_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """Load the settings once and reuse them everywhere."""
    return Settings()
