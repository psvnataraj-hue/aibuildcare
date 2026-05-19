from app.services import media_intake
from app.integrations import r2_client


def test_extract_no_media():
    assert media_intake.extract_twilio_media({"NumMedia": "0"}) == ([], [])
    assert media_intake.extract_twilio_media({}) == ([], [])


def test_extract_image_uploaded_to_r2(monkeypatch):
    monkeypatch.setattr(
        media_intake, "_download", lambda url: (b"\xff\xd8jpg", "image/jpeg")
    )
    monkeypatch.setattr(
        r2_client, "upload_bytes",
        lambda data, ct, ext="": "https://cdn.example/x.jpg",
    )
    imgs, audio = media_intake.extract_twilio_media(
        {"NumMedia": "1", "MediaUrl0": "https://api.twilio.com/m0",
         "MediaContentType0": "image/jpeg"}
    )
    assert imgs == ["https://cdn.example/x.jpg"]
    assert audio == []


def test_extract_audio_returned_for_transcription(monkeypatch):
    monkeypatch.setattr(
        media_intake, "_download", lambda url: (b"OggS", "audio/ogg")
    )
    imgs, audio = media_intake.extract_twilio_media(
        {"NumMedia": "1", "MediaUrl0": "https://api.twilio.com/a0",
         "MediaContentType0": "audio/ogg"}
    )
    assert imgs == []
    assert len(audio) == 1 and audio[0][1] == "audio/ogg"


def test_r2_not_configured_returns_none(monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_R2_ENDPOINT_URL", "")
    from app.config import get_settings

    get_settings.cache_clear()
    assert r2_client.is_configured() is False
    assert r2_client.upload_bytes(b"x", "image/png", ".png") is None
    get_settings.cache_clear()


def test_whatsapp_webhook_with_image(client, auth_header, monkeypatch):
    monkeypatch.setattr(
        media_intake, "_download", lambda url: (b"img", "image/png")
    )
    monkeypatch.setattr(
        r2_client, "upload_bytes",
        lambda data, ct, ext="": "https://cdn.example/p.png",
    )
    r = client.post(
        "/webhooks/twilio/whatsapp",
        data={"From": "whatsapp:+919833129064",
              "Body": "5B AC broken, see photo",
              "NumMedia": "1",
              "MediaUrl0": "https://api.twilio.com/m0",
              "MediaContentType0": "image/png"},
    )
    assert r.status_code == 200
    cid = client.get(
        "/api/v1/complaints?q=" + r.json()["ticket"], headers=auth_header
    ).json()[0]["id"]
    detail = client.get(
        f"/api/v1/complaints/{cid}", headers=auth_header
    ).json()
    assert detail["media_urls"] == "https://cdn.example/p.png"
