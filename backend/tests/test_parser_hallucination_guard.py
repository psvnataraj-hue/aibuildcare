"""Post-LLM hardening for haiku_parser (2026-05-21).

Real prod miss: WhatsApp "5B AC kharab hai urgent" got parsed to
unit_number=203 (hallucinated) and priority=high (downgraded from
the resident's explicit "urgent"). The rule-based parser handles
this input perfectly; the LLM freelanced. These tests lock in:

  1. Hallucination guard: if LLM unit_number is absent from source
     text AND no image was attached, prefer rule-based unit
     extraction.
  2. Priority ceiling: take max(llm_priority, rule_priority) so the
     LLM cannot downgrade words the resident explicitly used.
  3. Photo-only path: when no text but an image is attached, LLM
     unit_number is trusted (rule extractor can't see images).
  4. LLM unit matches text: no override; LLM value preserved.
"""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault(
    "AIBUILDCARE_DATABASE_URL", "./data/_parsertest_guard.db"
)

from app.config import get_settings  # noqa: E402
from app.services import haiku_parser as hp  # noqa: E402


@pytest.fixture(autouse=True)
def _with_key(monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fake_llm_response(payload: dict) -> MagicMock:
    fake = MagicMock()
    fake.content = [MagicMock(text=json.dumps(payload))]
    return fake


# ---- Hallucination guard: unit_number ---------------------------------

def test_llm_hallucinated_unit_overridden_by_rule(monkeypatch):
    """The exact bug from 2026-05-20 prod ticket SER-2026-00001:
    LLM returned '203' for an input that clearly says '5B'."""
    fake = _fake_llm_response({
        "unit_number": "203",   # hallucinated - not in text
        "category": "AC/Cooling",
        "priority": "high",      # downgraded from urgent
        "acknowledgement": "AC complaint received.",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("5B AC kharab hai urgent")
    assert p.unit_number == "5B", (
        "rule extractor should override LLM hallucination"
    )
    assert p.priority == "urgent", (
        "priority ceiling should restore resident's stated urgency"
    )


def test_llm_unit_matching_text_is_preserved(monkeypatch):
    """When LLM returns a unit that IS present in the text, trust
    the LLM (it may have normalized formatting correctly)."""
    fake = _fake_llm_response({
        "unit_number": "12A",
        "category": "Plumbing",
        "priority": "normal",
        "acknowledgement": "Plumber dispatched.",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("Flat 12A has a water leak")
    assert p.unit_number == "12A"


def test_llm_unit_with_whitespace_normalized_match(monkeypatch):
    """LLM may strip whitespace ('5 B' in text -> '5B' returned).
    The guard normalises both sides before comparing."""
    fake = _fake_llm_response({
        "unit_number": "5B",
        "category": "Plumbing",
        "priority": "normal",
        "acknowledgement": "ok",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("Unit 5 B leak")
    assert p.unit_number == "5B"  # not overridden


def test_llm_unit_from_photo_preserved_when_no_text(monkeypatch):
    """Photo-only intake (or text with no unit): the LLM may extract
    a unit number from the door plate in the image. We have no rule
    to validate this, so we trust the LLM."""
    fake = _fake_llm_response({
        "unit_number": "9D",
        "category": "Electrical",
        "priority": "normal",
        "acknowledgement": "Electrician on the way.",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint(
            "see attached photo",
            image_urls=["https://example.com/door.jpg"],
        )
    assert p.unit_number == "9D"  # trusted (image attached)


def test_llm_null_unit_falls_through_to_rule(monkeypatch):
    """If the LLM returns null but the text DOES have a unit, the
    rule extractor fills it in. Defense against LLM under-detection."""
    fake = _fake_llm_response({
        "unit_number": None,
        "category": "AC/Cooling",
        "priority": "normal",
        "acknowledgement": "ok",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("AC kharab in 7C")
    assert p.unit_number == "7C"


def test_no_rule_unit_when_text_has_none_keeps_llm_null(monkeypatch):
    """If both LLM and rule say null (and no image), final is null."""
    fake = _fake_llm_response({
        "unit_number": None,
        "category": "Other",
        "priority": "normal",
        "acknowledgement": "ok",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("hello, can someone help me")
    assert p.unit_number is None


# ---- Priority ceiling -------------------------------------------------

def test_priority_urgent_word_overrides_llm_normal(monkeypatch):
    """If the resident wrote 'urgent' and LLM returned 'normal',
    raise to urgent. Same for 'emergency', 'asap', 'turant'."""
    fake = _fake_llm_response({
        "unit_number": "5B",
        "category": "Plumbing",
        "priority": "normal",      # LLM downgrades
        "acknowledgement": "ok",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("5B emergency leak right now")
    assert p.priority == "urgent"


def test_priority_llm_urgent_kept_when_rule_normal(monkeypatch):
    """If LLM judged urgent but rule sees no urgency words (e.g.
    LLM upgraded based on photo or context), LLM wins."""
    fake = _fake_llm_response({
        "unit_number": "5B",
        "category": "Fire Safety",
        "priority": "urgent",
        "acknowledgement": "ok",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("5B small problem")  # rule: normal
    assert p.priority == "urgent"  # LLM wins (higher)


def test_priority_no_override_when_both_match(monkeypatch):
    """Sanity: equal priorities pass through unchanged."""
    fake = _fake_llm_response({
        "unit_number": "5B",
        "category": "Plumbing",
        "priority": "high",
        "acknowledgement": "ok",
    })
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("5B water issue 3 days now")  # rule -> high
    assert p.priority == "high"


# ---- Pure unit helpers (regression for _unit_in_text) -----------------

@pytest.mark.parametrize("unit,text,expected", [
    ("5B", "5B AC kharab", True),
    ("5B", "Unit 5 B leak", True),       # whitespace normalised
    ("A-101", "report from a 101", True), # dash normalised, case-insensitive
    ("203", "5B AC kharab", False),       # actual hallucination case
    ("9D", "no unit here", False),
    ("", "anything", False),
    ("5B", "", False),
])
def test_unit_in_text(unit, text, expected):
    assert hp._unit_in_text(unit, text) is expected
