from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
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
    # Default is empty so the seed is a no-op when the operator forgot
    # to set the env var; a previous default of "ChangeMe!2026" silently
    # shipped a publicly-known credential to prod (security fix, see
    # `_check_prod_secrets` below).
    seed_admin_password: str = ""

    anthropic_api_key: str = ""
    haiku_model: str = "claude-haiku-4-5"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    # Sandbox default; prod overrides via the *_number vars below.
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    # Production WhatsApp number, e.g. +14155238886 or +91XXXXXXXXXX
    twilio_whatsapp_number: str = ""
    # SMS sender: a Twilio number OR an alphanumeric sender ID (e.g.
    # "CARIMO" for India). Falls back to the WhatsApp number if empty.
    twilio_sms_number: str = ""

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

    # Sarvam AI Speech-to-Text (preferred for Indian languages).
    # Empty -> falls back to local Whisper, then graceful no-op.
    sarvam_api_key: str = ""
    sarvam_model: str = "saarika:v2.5"

    # Sarvam Text-to-Speech (bulbul) for the WhatsApp voice-note ack.
    # Reuses sarvam_api_key. Text ack is ALWAYS sent regardless; this
    # adds an extra audio message. Empty key / failure -> silently skip.
    sarvam_tts_model: str = "bulbul:v2"
    sarvam_tts_speaker: str = "anushka"
    whatsapp_voice_reply_enabled: bool = True

    # Smart auto-assignment on complaint create (Phase 4.5). On in prod;
    # the existing test suite disables it so per-test status assertions
    # stay meaningful; the dedicated auto-assign tests opt back in.
    auto_assign_enabled: bool = True

    # E2: shared secret for /internal/jobs/tick (external cron caller
    # like cron-job.org sends X-Internal-Secret). Empty -> endpoint
    # disabled (returns 503), preventing accidental public access.
    internal_jobs_secret: str = ""

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://aibuildcare-web.onrender.com,"
        "https://aibuildcare.carimotech.in"
    )

    @model_validator(mode="after")
    def _check_prod_secrets(self) -> "Settings":
        """Refuse to start in production with insecure / missing
        secrets that have historically slipped through as silent
        defaults.

        Caught here so a Render deploy crashes loudly at startup with
        a clear error rather than silently running with a known-public
        credential. Dev / test environments are unaffected.
        """
        if self.environment == "production":
            if not self.seed_admin_password:
                raise ValueError(
                    "AIBUILDCARE_SEED_ADMIN_PASSWORD must be set in "
                    "production (cannot be empty)"
                )
            if self.seed_admin_password == "ChangeMe!2026":
                raise ValueError(
                    "AIBUILDCARE_SEED_ADMIN_PASSWORD is the leaked "
                    "default 'ChangeMe!2026'; rotate it"
                )
            if self.jwt_secret == "dev-only-change-me":
                raise ValueError(
                    "AIBUILDCARE_JWT_SECRET must be set in production "
                    "(not the dev default)"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
