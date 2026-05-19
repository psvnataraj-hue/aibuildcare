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
