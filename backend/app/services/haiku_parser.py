"""Complaint parser.

Primary path: Claude Haiku 4.5 via the anthropic SDK, returning strict JSON.
Fallback path: deterministic rule-based parser used when no API key is
configured (offline CI, cost control). The fallback is first-class - it
handles the Hinglish/typo cases the product needs, so a complaint is never
dropped on LLM failure.
"""
from __future__ import annotations

import json
import re

from ..config import get_settings
from ..schemas import ParsedComplaint

CATEGORIES = [
    "AC/Cooling",
    "Plumbing",
    "Electrical",
    "Elevator",
    "Housekeeping",
    "Security",
    "Other",
]

_KEYWORDS: dict[str, list[str]] = {
    "AC/Cooling": ["ac", "a/c", "air condition", "cooling", "thanda",
                   "fridge", "cooler"],
    "Plumbing": ["water", "leak", "tap", "pipe", "nal", "plumb",
                 "drain", "toilet", "flush", "seepage", "paani"],
    "Electrical": ["light", "power", "current", "bijli", "switch",
                   "fan", "electric", "wiring", "short circuit", "mcb"],
    "Elevator": ["lift", "elevator"],
    "Housekeeping": ["clean", "garbage", "kachra", "kachara", "dust",
                     "sweep", "housekeep", "pest"],
    "Security": ["guard", "security", "gate", "watchman", "theft",
                 "intruder", "cctv"],
}

_URGENT = ["urgent", "emergency", "asap", "turant", "jaldi", "immediately",
           "critical", "danger", "fire", "smoke"]

_UNIT_RE = re.compile(
    r"\b([A-Z]{0,2}-?\d{1,4}-?[A-Z]?|\d{1,4}\s?[A-Z])\b", re.IGNORECASE
)

_SLA = {
    "AC/Cooling": "2 hours",
    "Plumbing": "8 hours",
    "Electrical": "6 hours",
    "Elevator": "1 hour",
    "Housekeeping": "24 hours",
    "Security": "1 hour",
    "Other": "24 hours",
}


def _extract_unit(text: str) -> str | None:
    # number-then-letter: "5B", "7 C", "12-A"
    m = re.search(r"\b(\d{1,4})\s?-?([A-Z])\b", text, re.IGNORECASE)
    if m:
        return f"{m.group(1)}{m.group(2).upper()}"
    # letter-dash-number: "A-101", "B-12"
    m = re.search(r"\b([A-Z])\s?-\s?(\d{1,4})\b", text, re.IGNORECASE)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    m = re.search(r"\b(\d{1,4})\b", text)
    return m.group(1) if m else None


def _classify(text: str) -> str:
    low = text.lower()
    for cat, words in _KEYWORDS.items():
        for w in words:
            # Short alpha tokens ("ac") use word boundaries so they don't
            # match inside other words ("kachra"). Longer/phrase keywords
            # use substring so "electric" still matches "electricity".
            if w.isalpha() and len(w) <= 3:
                if re.search(rf"(?<![a-z]){w}(?![a-z])", low):
                    return cat
            elif w in low:
                return cat
    return "Other"


def _priority(text: str) -> str:
    low = text.lower()
    if any(w in low for w in _URGENT):
        return "urgent"
    m = re.search(r"(\d+)\s*(din|day|days)", low)
    if m and int(m.group(1)) >= 2:
        return "high"
    return "normal"


def rule_based_parse(text: str) -> ParsedComplaint:
    unit = _extract_unit(text)
    category = _classify(text)
    priority = _priority(text)
    where = f" in {unit}" if unit else ""
    sla = _SLA.get(category, "24 hours")
    ack = (
        f"{category} issue{where} logged - a specialist will attend "
        f"within {sla}. Thank you for reporting."
    )
    return ParsedComplaint(
        unit_number=unit,
        category=category,
        priority=priority,
        acknowledgement=ack,
    )


_SYSTEM = (
    "You are a building-complaint intake assistant for an Indian housing "
    "society. Residents write in English, Hindi, or Hinglish with typos. "
    "Return ONLY a JSON object with keys: unit_number (string or null), "
    f"category (one of {CATEGORIES}), priority (one of "
    '["normal","high","urgent"]), acknowledgement (a short, warm, '
    "human-sounding confirmation written in the SAME language and script "
    "the resident used, with no ticket number). No prose, JSON only."
)


def _llm_parse(text: str) -> ParsedComplaint:
    import anthropic

    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    resp = client.messages.create(
        model=s.haiku_model,
        max_tokens=400,
        system=_SYSTEM,
        messages=[{"role": "user", "content": text}],
    )
    body = resp.content[0].text.strip()
    body = re.sub(r"^```(?:json)?|```$", "", body, flags=re.MULTILINE).strip()
    data = json.loads(body)
    cat = data.get("category", "Other")
    if cat not in CATEGORIES:
        cat = "Other"
    return ParsedComplaint(
        unit_number=data.get("unit_number") or None,
        category=cat,
        priority=data.get("priority", "normal"),
        acknowledgement=data.get("acknowledgement", ""),
    )


def parse_complaint(text: str) -> ParsedComplaint:
    """Parse free text into structured complaint fields.

    Uses Haiku when a key is configured; falls back to the rule-based
    parser on any error so intake never fails.
    """
    s = get_settings()
    if not s.anthropic_api_key:
        return rule_based_parse(text)
    try:
        return _llm_parse(text)
    except Exception:
        return rule_based_parse(text)
