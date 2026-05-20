"""Production-environment refuses to start with insecure / missing
secrets that previously slipped through as silent defaults.

Catches:
  - empty AIBUILDCARE_SEED_ADMIN_PASSWORD (silent no-op admin seed)
  - the leaked-default password "ChangeMe!2026"
  - the dev-only JWT secret

Dev / test environment is unaffected (the conftest fixture defaults
``environment`` to its baked-in "development" value).
"""
import pytest

from app.config import Settings


def _make(**env):
    """Build a Settings instance without reading the .env file (we want
    deterministic values, not whatever the dev box happens to have)."""
    base = {
        "environment": "production",
        "seed_admin_password": "real-strong-pwd-9k4f",
        "jwt_secret": "real-strong-jwt-2x7m",
        "database_url": "sqlite:///:memory:",
    }
    base.update(env)
    # _env_file=None tells pydantic-settings to skip .env loading
    return Settings(_env_file=None, **base)


def test_production_with_real_secrets_starts_fine():
    s = _make()
    assert s.environment == "production"
    assert s.seed_admin_password == "real-strong-pwd-9k4f"


def test_production_with_empty_password_refuses_to_start():
    with pytest.raises(Exception) as exc:
        _make(seed_admin_password="")
    assert "SEED_ADMIN_PASSWORD" in str(exc.value)


def test_production_with_leaked_default_password_refuses_to_start():
    """The 'ChangeMe!2026' default shipped to prod once; never again."""
    with pytest.raises(Exception) as exc:
        _make(seed_admin_password="ChangeMe!2026")
    assert "ChangeMe" in str(exc.value) or "leaked" in str(exc.value)


def test_production_with_dev_jwt_secret_refuses_to_start():
    with pytest.raises(Exception) as exc:
        _make(jwt_secret="dev-only-change-me")
    assert "JWT_SECRET" in str(exc.value)


def test_development_with_empty_password_starts_fine():
    """Defaults are fine in dev — the validator only fires in prod."""
    s = _make(environment="development", seed_admin_password="")
    assert s.seed_admin_password == ""


def test_development_with_dev_jwt_secret_starts_fine():
    s = _make(environment="development", jwt_secret="dev-only-change-me")
    assert s.jwt_secret == "dev-only-change-me"
