"""E1b'': WhatsApp self-service vendor directory intent.

If a resident texts an explicit search ("find a carpenter", "looking
for a plumber") AND the rule classifier identifies a known category,
the bot replies with the vendor directory instead of creating a
complaint. Bare problem text ("AC kharab") still becomes a ticket.
"""
from unittest.mock import MagicMock

from app.routers import webhooks as wh


def _post(client, body, **extra):
    data = {
        "From": "whatsapp:+919833129064",
        "Body": body,
    }
    data.update(extra)
    return client.post("/webhooks/twilio/whatsapp", data=data)


# ---- unit: intent detection -----------------------------------------
def test_directory_intent_matches_explicit_searches():
    for s in [
        "find a carpenter",
        "looking for an electrician",
        "connect me to a plumber",
        "hire a painter for my flat",
        "recommend me a pest control vendor",
        "vendor for AC service",
    ]:
        assert wh._is_directory_request(s), s


def test_directory_intent_does_not_trigger_on_complaints():
    for s in [
        "AC kharab in 5B urgent",
        "leak in 7B bathroom",
        "lift not working since morning",
        "garbage not collected",
    ]:
        assert not wh._is_directory_request(s), s


# ---- format ---------------------------------------------------------
def test_format_with_vendors_includes_walinks():
    msg = wh._format_directory_reply("Carpentry", [
        {"name": "Ramesh", "average_rating": 4.7,
         "phone": "+91987", "wa_link": "https://wa.me/91987"},
        {"name": "Suresh", "average_rating": None,
         "phone": "+91988", "wa_link": "https://wa.me/91988"},
    ])
    assert "Carpentry" in msg
    assert "Ramesh" in msg and "Suresh" in msg
    assert "https://wa.me/91987" in msg
    assert "⭐ 4.7" in msg


def test_format_with_no_vendors_is_graceful():
    msg = wh._format_directory_reply("Tile Polishing", [])
    assert "no vetted" in msg.lower()


# ---- webhook integration --------------------------------------------
def test_explicit_find_returns_directory_no_ticket(client, monkeypatch):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr(wh, "send_whatsapp", sent)

    r = _post(client, "find a plumber for my flat")
    assert r.status_code == 200
    body = r.json()
    assert body.get("directory") is True
    assert body.get("category") == "Plumbing"
    # text ack went out
    assert sent.called
    _phone, reply = sent.call_args[0]
    assert "Plumbing" in reply
    # NO ticket was created (no SER number in the response shape)
    assert "ticket" not in body


def test_problem_text_still_creates_complaint(client, monkeypatch):
    sent = MagicMock(return_value=True)
    monkeypatch.setattr(wh, "send_whatsapp", sent)

    r = _post(client, "AC kharab in 5B urgent")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ticket", "").startswith("SER-")
    assert body.get("directory") is None


def test_intent_without_category_falls_through_to_complaint(
    client, monkeypatch,
):
    """'find a vendor' alone has no category -> rule classifier picks
    'Other' -> intent is dropped, complaint is created normally."""
    sent = MagicMock(return_value=True)
    monkeypatch.setattr(wh, "send_whatsapp", sent)

    r = _post(client, "find a vendor please")
    body = r.json()
    assert body.get("directory") is None
    assert body.get("ticket", "").startswith("SER-")


def test_voice_note_with_directory_intent(client, monkeypatch):
    """Audio is transcribed via _with_audio; intent detection runs
    on the transcribed text."""
    import app.services.media_intake as mi

    sent = MagicMock(return_value=True)
    monkeypatch.setattr(wh, "send_whatsapp", sent)
    monkeypatch.setattr(mi, "_download",
                        lambda url: (b"OggS", "audio/ogg"))
    # Force the transcribe path to return our test sentence
    monkeypatch.setattr(
        wh.audio_transcriber, "transcribe",
        lambda data, ext: ("looking for a carpenter", "en"),
    )

    r = _post(
        client, "",
        NumMedia="1",
        MediaUrl0="https://api.twilio.com/a0",
        MediaContentType0="audio/ogg",
    )
    body = r.json()
    assert body.get("directory") is True
    assert body.get("category") == "Carpentry"
