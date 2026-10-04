from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):

    app_name: str = "Legal Metrology AI"
    app_version: str = "1.0.0"
    environment: str = "development"

    # Explicit list of allowed CORS origins.
    # In development, local development origins are permitted.
    # In production, explicit production domains must be configured.
    # Wildcard unrestricted CORS is strictly prohibited.
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    gemini_api_key: str = ""

    supabase_url: str = ""

    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "inspection-images"
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"

    telegram_bot_token: str = ""
    telegram_bot_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()