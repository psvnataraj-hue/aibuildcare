"""Sarvam TTS -> R2 -> WhatsApp media voice reply (offline, mocked)."""
import base64

import pytest

from app.services import tts
from app.services.notify import send_whatsapp_media


# ---- language normalisation -----------------------------------------
@pytest.mark.parametrize(
    "given,expected",
    [
        ("hindi", "hi-IN"),
        ("hinglish", "hi-IN"),   # code-mixed -> Hindi voice
        ("telugu", "te-IN"),
        ("english", "en-IN"),
        ("marathi", "mr-IN"),
        ("hi-IN", "hi-IN"),      # already BCP-47
        ("te", "te-IN"),         # Whisper ISO-2
        (None, "en-IN"),         # missing -> default
        ("klingon", "en-IN"),    # unknown -> default
    ],
)
def test_to_bcp47(given, expected):
    assert tts.to_bcp47(given) == expected


# ---- synthesize ------------------------------------------------------
def test_synthesize_none_without_key():
    # default test settings have no Sarvam key
    assert tts.synthesize("hello", "english") is None


def test_synthesize_returns_mp3(monkeypatch):
    import httpx
    from app.config import get_settings

    monkeypatch.setenv("AIBUILDCARE_SARVAM_API_KEY", "sk-tts-test")
    get_settings.cache_clear()

    raw = b"ID3-fake-mp3-bytes"
    captured = {}

    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"request_id": "r1",
                    "audios": [base64.b64encode(raw).decode()]}

    def fake_post(url, **kw):
        captured["url"] = url
        captured["hdr"] = kw.get("headers", {})
        captured["json"] = kw.get("json", {})
        return _R()

    monkeypatch.setattr(httpx, "post", fake_post)
    out = tts.synthesize("Ticket SER-1. Noted.", "hindi")
    get_settings.cache_clear()

    assert out is not None
    data, ext, ctype = out
    assert data == raw
    assert ext == "mp3" and ctype == "audio/mpeg"
    assert captured["url"] == "https://api.sarvam.ai/text-to-speech"
    assert captured["hdr"].get("api-subscription-key") == "sk-tts-test"
    assert captured["json"]["output_audio_codec"] == "mp3"
    assert captured["json"]["target_language_code"] == "hi-IN"


def test_synthesize_graceful_on_network_error(monkeypatch):
    import httpx
    from app.config import get_settings

    monkeypatch.setenv("AIBUILDCARE_SARVAM_API_KEY", "sk-tts-test")
    get_settings.cache_clear()

    def boom(url, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(httpx, "post", boom)
    assert tts.synthesize("hi", "english") is None  # never raises
    get_settings.cache_clear()


def test_synthesize_none_on_empty_text():
    assert tts.synthesize("   ", "english") is None


# ---- WhatsApp media sender ------------------------------------------
def test_send_whatsapp_media_noop_without_twilio(client):
    # client fixture clears Twilio creds -> graceful False, no raise
    assert send_whatsapp_media("+919833129064", "https://r2/x.mp3") is False


# ---- webhook integration --------------------------------------------
def test_whatsapp_webhook_sends_voice_reply(client, monkeypatch):
    from app.routers import webhooks as wh

    sent = {}
    monkeypatch.setattr(
        wh.tts, "synthesize",
        lambda text, lang=None: (b"mp3bytes", "mp3", "audio/mpeg"),
    )
    monkeypatch.setattr(
        wh.r2_client, "upload_bytes",
        lambda data, ctype, ext="": "https://r2.example/abc.mp3",
    )
    monkeypatch.setattr(
        wh, "send_whatsapp_media",
        lambda phone, url, body="": sent.update(phone=phone, url=url) or True,
    )

    r = client.post(
        "/webhooks/twilio/whatsapp",
        data={"From": "whatsapp:+919833129064", "Body": "5B AC kharab hai"},
    )
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")
    assert sent["phone"] == "+919833129064"
    assert sent["url"] == "https://r2.example/abc.mp3"


def test_whatsapp_webhook_text_fallback_when_tts_fails(client, monkeypatch):
    from app.routers import webhooks as wh

    calls = {"media": 0}
    monkeypatch.setattr(wh.tts, "synthesize", lambda text, lang=None: None)
    monkeypatch.setattr(
        wh, "send_whatsapp_media",
        lambda *a, **k: calls.__setitem__("media", calls["media"] + 1),
    )

    r = client.post(
        "/webhooks/twilio/whatsapp",
        data={"From": "whatsapp:+919833129064", "Body": "leak in 7E"},
    )
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")
    assert calls["media"] == 0  # TTS failed -> no media; text ack still sent


def test_whatsapp_webhook_skips_voice_when_disabled(client, monkeypatch):
    from app.config import get_settings
    from app.routers import webhooks as wh

    monkeypatch.setenv("AIBUILDCARE_WHATSAPP_VOICE_REPLY_ENABLED", "false")
    get_settings.cache_clear()

    called = {"synth": 0}
    monkeypatch.setattr(
        wh.tts, "synthesize",
        lambda *a, **k: called.__setitem__("synth", 1),
    )
    r = client.post(
        "/webhooks/twilio/whatsapp",
        data={"From": "whatsapp:+919833129064", "Body": "lift stuck"},
    )
    get_settings.cache_clear()
    assert r.status_code == 200
    assert called["synth"] == 0  # disabled -> TTS never invoked
