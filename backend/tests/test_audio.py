from app.services import audio_transcriber
from app.routers.webhooks import _with_audio


def test_transcribe_graceful_when_whisper_absent():
    # openai-whisper is NOT in the test env (it's optional / heavy).
    text, lang = audio_transcriber.transcribe(b"OggS...", "ogg")
    assert text == ""
    assert lang is None


def test_with_audio_falls_back_to_placeholder():
    # No whisper -> body empty + audio present -> placeholder, never crash
    out = _with_audio("", [(b"OggS", "audio/ogg")])
    assert "voice note received" in out.lower()


def test_with_audio_keeps_text_when_present():
    out = _with_audio("5B AC kharab", [(b"OggS", "audio/ogg")])
    assert "5B AC kharab" in out


def test_whatsapp_voice_note_still_creates_ticket(client):
    import app.services.media_intake as mi

    # simulate Twilio audio media; no whisper installed -> placeholder text
    orig = mi._download
    mi._download = lambda url: (b"OggS", "audio/ogg")
    try:
        r = client.post(
            "/webhooks/twilio/whatsapp",
            data={"From": "whatsapp:+919833129064", "Body": "",
                  "NumMedia": "1", "MediaUrl0": "https://api.twilio.com/a0",
                  "MediaContentType0": "audio/ogg"},
        )
    finally:
        mi._download = orig
    assert r.status_code == 200
    assert r.json()["ticket"].startswith("SER-")


# ---- Sarvam path (mocked, offline) -----------------------------------
def test_sarvam_transcribes_when_key_set(monkeypatch):
    import httpx
    from app.config import get_settings
    from app.services import audio_transcriber as at

    monkeypatch.setenv("AIBUILDCARE_SARVAM_API_KEY", "sk-sarvam-test")
    get_settings.cache_clear()

    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "transcript": "5B mein AC kharab hai",
                "language_code": "hi-IN",
            }

    captured = {}

    def fake_post(url, **kw):
        captured["url"] = url
        captured["hdr"] = kw.get("headers", {})
        return _R()

    monkeypatch.setattr(httpx, "post", fake_post)
    text, lang = at.transcribe(b"OggS-bytes", "ogg")
    assert text == "5B mein AC kharab hai"
    assert lang == "hi-IN"
    assert captured["url"] == "https://api.sarvam.ai/speech-to-text"
    assert captured["hdr"].get("api-subscription-key") == "sk-sarvam-test"
    get_settings.cache_clear()


def test_sarvam_failure_is_graceful(monkeypatch):
    import httpx
    from app.config import get_settings
    from app.services import audio_transcriber as at

    monkeypatch.setenv("AIBUILDCARE_SARVAM_API_KEY", "sk-sarvam-test")
    get_settings.cache_clear()

    def boom(url, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(httpx, "post", boom)
    text, lang = at.transcribe(b"x", "ogg")
    assert text == "" and lang is None  # never raises
    get_settings.cache_clear()
