import os
import json
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AIBUILDCARE_DATABASE_URL", "./data/_parsertest.db")

from app.config import get_settings  # noqa: E402
from app.services import haiku_parser as hp  # noqa: E402


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---- rule-based unit extraction -------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("5B mein AC kharab hai 3 din se urgent", "5B"),
        ("Flat 12A has a water leak", "12A"),
        ("3C ka lift band hai", "3C"),
        ("Unit 9D no power since morning", "9D"),
        ("A-101 tap broken", "A-101"),
        ("problem in 7 C please help", "7C"),
    ],
)
def test_unit_extraction(text, expected):
    assert hp.rule_based_parse(text).unit_number == expected


# ---- category classification ----------------------------------------------
@pytest.mark.parametrize(
    "text,cat",
    [
        ("AC not cooling in 5B", "AC/Cooling"),
        ("air conditioner kharab", "AC/Cooling"),
        ("water leakage from pipe", "Plumbing"),
        ("nal se paani nahi aa raha", "Plumbing"),
        ("no electricity, bijli gayab", "Electrical"),
        ("fan not working", "Electrical"),
        ("lift stuck on 4th floor", "Elevator"),
        ("garbage not collected, kachra", "Housekeeping"),
        ("security guard absent at gate", "Security"),
        ("random unclear message", "Other"),
    ],
)
def test_category(text, cat):
    assert hp.rule_based_parse(text).category == cat


# ---- priority detection ----------------------------------------------------
@pytest.mark.parametrize(
    "text,prio",
    [
        ("urgent AC repair needed", "urgent"),
        ("emergency water flooding", "urgent"),
        ("turant aao please", "urgent"),
        ("AC kharab 3 din se", "high"),
        ("issue since 5 days", "high"),
        ("minor paint touch up", "normal"),
        ("light flickering sometimes", "normal"),
    ],
)
def test_priority(text, prio):
    assert hp.rule_based_parse(text).priority == prio


def test_ack_is_human_sounding():
    p = hp.rule_based_parse("5B mein AC kharab hai 3 din se urgent")
    assert p.unit_number == "5B"
    assert p.category == "AC/Cooling"
    assert "5B" in p.acknowledgement
    assert len(p.acknowledgement) > 20


def test_parse_complaint_uses_fallback_without_key():
    p = hp.parse_complaint("12A plumbing leak urgent")
    assert p.category == "Plumbing"
    assert p.priority == "urgent"


def test_parse_complaint_uses_llm_with_key(monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    fake = MagicMock()
    fake.content = [
        MagicMock(
            text=json.dumps(
                {
                    "unit_number": "5B",
                    "category": "AC/Cooling",
                    "priority": "urgent",
                    "acknowledgement": "Cooling specialist on the way.",
                }
            )
        )
    ]
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("5B AC kharab urgent")
    assert p.unit_number == "5B"
    assert p.category == "AC/Cooling"
    assert p.priority == "urgent"


def test_llm_failure_falls_back(monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    with patch("anthropic.Anthropic", side_effect=RuntimeError("boom")):
        p = hp.parse_complaint("9D lift not working urgent")
    assert p.category == "Elevator"
    assert p.priority == "urgent"


def test_llm_invalid_category_coerced(monkeypatch):
    monkeypatch.setenv("AIBUILDCARE_ANTHROPIC_API_KEY", "sk-test")
    get_settings.cache_clear()
    fake = MagicMock()
    fake.content = [
        MagicMock(
            text=json.dumps(
                {"unit_number": None, "category": "Banana",
                 "priority": "normal", "acknowledgement": "ok"}
            )
        )
    ]
    with patch("anthropic.Anthropic") as mk:
        mk.return_value.messages.create.return_value = fake
        p = hp.parse_complaint("something")
    assert p.category == "Other"
