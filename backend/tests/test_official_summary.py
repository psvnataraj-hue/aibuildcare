"""Staff-facing official_summaries: config, parser, storage, decode."""
import json

from app.schemas import ParsedComplaint


# ---- config -----------------------------------------------------------
def test_default_summary_language_is_hindi(client):
    from app.services import system_config

    # not seeded into the migration -> resolved from DEFAULTS
    assert system_config.get_config("official_summary_languages") == "hi"


def test_configured_langs_parses_and_validates(client):
    from app.services import system_config
    from app.services.haiku_parser import _configured_langs

    system_config.set_config("official_summary_languages", "en, hi ,mr,xx")
    assert _configured_langs() == ["en", "hi", "mr"]  # xx dropped

    system_config.set_config("official_summary_languages", "")
    assert _configured_langs() == ["hi"]  # empty -> default


def test_build_system_lists_requested_languages():
    from app.services.haiku_parser import _build_system

    s = _build_system(["en", "hi"])
    assert "official_summaries" in s
    assert "English (en)" in s and "Hindi (hi)" in s


# ---- LLM parse path (mocked) -----------------------------------------
def test_llm_parse_extracts_and_filters_summaries(client, monkeypatch):
    import anthropic
    import app.services.haiku_parser as hp
    from app.config import get_settings

    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()

    payload = {
        "unit_number": "7A", "category": "Elevator", "priority": "urgent",
        "detected_language": "telugu", "acknowledgement": "ok",
        "official_summaries": {
            "hi": "यूनिट 7A: लिफ्ट खराब",
            "en": "Unit 7A: lift not working, urgent",
            "xx": "junk should be dropped",
        },
    }

    class _Msgs:
        def create(self, **kw):
            txt = json.dumps(payload)
            return type(
                "R", (), {"content": [type("C", (), {"text": txt})()]}
            )()

    class _Client:
        def __init__(self, *a, **k):
            self.messages = _Msgs()

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: _Client())
    p = hp._llm_parse("lift broken 7A", None, ["hi", "en"])
    get_settings.cache_clear()

    assert p.category == "Elevator"
    assert set(p.official_summaries) == {"hi", "en"}  # xx filtered out
    assert p.official_summaries["en"] == "Unit 7A: lift not working, urgent"


# ---- storage + JSON decode round-trip --------------------------------
def test_summaries_stored_and_returned_as_dict(client, auth_header,
                                                monkeypatch):
    from app.services import complaint_service as svc

    monkeypatch.setattr(
        svc, "parse_complaint",
        lambda *a, **k: ParsedComplaint(
            unit_number="7A", category="Elevator", priority="urgent",
            acknowledgement="noted",
            official_summaries={"hi": "लिफ्ट",
                                "en": "lift broken"},
        ),
    )
    c = svc.create_complaint("lift broken 7A", channel="form")
    # create path returns a decoded dict, not a JSON string
    assert c["official_summaries"] == {"hi": "लिफ्ट",
                                       "en": "lift broken"}

    # GET + LIST endpoints also return it decoded
    detail = client.get(
        f"/api/v1/complaints/{c['id']}", headers=auth_header
    ).json()
    assert detail["official_summaries"]["en"] == "lift broken"
    listed = client.get("/api/v1/complaints", headers=auth_header).json()
    assert listed[0]["official_summaries"]["hi"] == "लिफ्ट"


def test_rule_fallback_yields_empty_summaries(client, auth_header):
    # no anthropic key in tests -> rule parser -> empty dict, never a
    # raw JSON string, never a crash
    from app.services import complaint_service as svc

    c = svc.create_complaint("12A water leak", channel="form")
    assert c["official_summaries"] == {}
    detail = client.get(
        f"/api/v1/complaints/{c['id']}", headers=auth_header
    ).json()
    assert detail["official_summaries"] == {}
