import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.services import haiku_parser as hp


def _mock_resp(payload: dict):
    fake = MagicMock()
    fake.content = [MagicMock(text=json.dumps(payload))]
    return fake


LANGS = [
    ("english", "AC broken in 5B urgent"),
    ("hindi", "5B मे AC खराब है"),
    ("hinglish", "5B mein AC kharab hai urgent"),
    ("marathi", "5B मध्ये AC खराब आहे"),
    ("gujarati", "4C માં પાણીનો નળ તૂટી ગયો"),
    ("punjabi", "10A 'ch naal leak ho reha"),
    ("kannada", "6D ನಲ್ಲಿ ವಿದ್ಯುತ್ ಸಮಸ್ಯೆ"),
    ("tamil", "5B இல் விசிறி சேதம்"),
    ("telugu", "7E లో నీటి లీక్"),
    ("malayalam", "3B ൽ AC തകരാറിലാണ്"),
]


@pytest.mark.parametrize("lang,text", LANGS)
def test_detected_language_propagates(monkeypatch, lang, text):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    payload = {
        "unit_number": "5B",
        "category": "AC/Cooling",
        "priority": "normal",
        "detected_language": lang,
        "acknowledgement": "ok",
    }
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = _mock_resp(payload)
        p = hp.parse_complaint(text)
    assert p.detected_language == lang
    get_settings.cache_clear()


def test_image_urls_build_vision_content(monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    captured = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return _mock_resp(
            {"unit_number": "5B", "category": "AC/Cooling",
             "priority": "urgent", "detected_language": "english",
             "acknowledgement": "ok"}
        )

    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.side_effect = _create
        hp.parse_complaint("AC broken", ["https://cdn/x.jpg"])

    content = captured["messages"][0]["content"]
    assert isinstance(content, list)
    assert any(b.get("type") == "image" for b in content)
    assert any(b.get("type") == "text" for b in content)
    get_settings.cache_clear()


def test_detected_language_stored_on_complaint(client, monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = _mock_resp(
            {"unit_number": "5B", "category": "AC/Cooling",
             "priority": "urgent", "detected_language": "marathi",
             "acknowledgement": "ठीक आहे"}
        )
        r = client.post(
            "/webhooks/forms", json={"raw_text": "5B madhe AC kharab"}
        )
    tk = r.json()["ticket"]
    get_settings.cache_clear()
    # fetch back
    tok = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@aibuildcare.app", "password": "Secret!123"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    cid = client.get(
        f"/api/v1/complaints?q={tk}", headers=h
    ).json()[0]["id"]
    detail = client.get(f"/api/v1/complaints/{cid}", headers=h).json()
    assert detail["detected_language"] == "marathi"
