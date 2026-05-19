from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env, resolved from this file so it loads regardless of the
# process working directory (backend/, repo root, or Render).
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
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

    # Cloudflare R2 (S3-compatible) for complaint media. Empty -> media
    # upload is skipped gracefully (ticket still created).
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "aibuildcare-assets"
    r2_public_base_url: str = ""

    # Local Whisper (openai-whisper package). No key. Lazy-loaded;
    # gracefully degrades where torch/RAM is unavailable (e.g. Render free).
    whisper_model: str = "base"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
