import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("AIBUILDCARE_DATABASE_URL", str(db_file))
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AIBUILDCARE_TWILIO_ACCOUNT_SID", "")
    monkeypatch.setenv("AIBUILDCARE_TWILIO_AUTH_TOKEN", "")
    monkeypatch.setenv("AIBUILDCARE_SENDGRID_API_KEY", "")
    monkeypatch.setenv("AIBUILDCARE_SEED_ADMIN_EMAIL", "admin@aibuildcare.app")
    monkeypatch.setenv("AIBUILDCARE_SEED_ADMIN_PASSWORD", "Secret!123")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


@pytest.fixture()
def auth_header(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@aibuildcare.app", "password": "Secret!123"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
