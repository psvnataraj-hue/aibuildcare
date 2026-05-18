from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AIBUILDCARE_",
        extra="ignore",
    )

    app_name: str = "AIBuildCare"
    environment: str = "development"

    database_url: str = "./data/complaints.db"

    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    seed_admin_email: str = "admin@aibuildcare.app"
    seed_admin_password: str = "ChangeMe!2026"

    anthropic_api_key: str = ""
    haiku_model: str = "claude-haiku-4-5"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@aibuildcare.local"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
