"""Complaint parser.

Primary path: Claude Haiku 4.5 via the anthropic SDK, returning strict JSON.
Fallback path: deterministic rule-based parser used when no API key is
configured (offline CI, cost control). The fallback is first-class - it
handles the Hinglish/typo cases the product needs, so a complaint is never
dropped on LLM failure.

Post-LLM hardening (2026-05-21):
  - Unit-number hallucination guard: if the LLM returns a unit_number
    that doesn't appear in the source text AND no photo was attached
    AND the rule extractor finds a text-anchored unit, prefer the rule
    extractor. This caught a real prod miss where "5B AC kharab hai
    urgent" got parsed to unit_number=203.
  - Priority ceiling: take max(llm_priority, rule_priority) where
    urgent > high > normal. The LLM downgrading clearly-marked
    urgency words (e.g. "urgent") is worse than over-flagging.
"""
from __future__ import annotations

import json
import logging
import re

from ..config import get_settings
from ..schemas import ParsedComplaint

log = logging.getLogger("aibuildcare.parser")

CATEGORIES = [
    # safety-critical
    "Fire Safety",
    "Security",
    "Elevator",
    "Generator/Power Backup",
    # building / common-area services
    "Electrical",
    "Plumbing",
    "AC/Cooling",
    "Water Supply",
    "Sewage/Drainage",
    "Lighting",
    "Housekeeping",
    "Garbage/Waste",
    "Pest Control",
    "Gardening",
    "Carpentry",
    "Painting",
    "Civil/Structural",
    "CCTV/Intercom",
    # amenities
    "Swimming Pool",
    "Sports/Gym/Clubhouse",
    "Children's Play Area",
    # community / non-physical
    "Parking Management",
    "Noise/Visitor",
    "Other",
]

# Language codes a society may configure for the staff-facing summary.
_LANG_NAMES = {
    "en": "English", "hi": "Hindi", "mr": "Marathi", "bn": "Bengali",
    "te": "Telugu", "gu": "Gujarati", "pa": "Punjabi", "kn": "Kannada",
    "ta": "Tamil", "ml": "Malayalam", "od": "Odia",
}


def _configured_langs() -> list[str]:
    """Validated list of summary language codes from system_config.

    A config-store failure must never degrade parsing, so any error
    falls back to the default language.
    """
    try:
        from .system_config import get_config

        raw = get_config("official_summary_languages", "hi") or "hi"
    except Exception:
        return ["hi"]
    out: list[str] = []
    for code in raw.split(","):
        code = code.strip().lower()
        if code in _LANG_NAMES and code not in out:
            out.append(code)
    return out or ["hi"]

_KEYWORDS: dict[str, list[str]] = {
    # NOTE: order matters — first match wins. Existing 6 stay first to
    # preserve test_haiku_parser expectations (kachra->Housekeeping,
    # nal/paani->Plumbing, light->Electrical, cctv->Security).
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
    # E1: expanded categories — distinctive keywords only so the rule
    # fallback still defers to the LLM when ambiguous.
    "Fire Safety": ["fire", "smoke alarm", "extinguisher", "sprinkler"],
    "Generator/Power Backup": ["generator", "dg set", "inverter",
                               "backup power"],
    "Water Supply": ["tanker", "water tanker", "borewell", "no water"],
    "Sewage/Drainage": ["sewer", "sewage", "manhole", "gutter", "nala",
                        "overflow"],
    "Lighting": ["bulb", "tubelight", "tube light", "street light",
                 "corridor light"],
    "Garbage/Waste": ["dustbin", "trash bin", "waste collection",
                      "rubbish"],
    "Pest Control": ["cockroach", "rat", "termite", "mosquito",
                     "rodent", "fumigat", "fogging", "insect"],
    "Gardening": ["garden", "gardener", "mali", "lawn", "landscap",
                  "tree", "grass"],
    "Carpentry": ["carpenter", "carpentry", "furniture", "wood",
                  "cabinet", "cupboard", "hinge"],
    "Painting": ["paint", "color", "whitewash"],
    "Civil/Structural": ["crack", "plaster", "ceiling", "slab broken",
                         "wall damage", "structural"],
    "CCTV/Intercom": ["intercom"],
    "Swimming Pool": ["pool", "swimming", "chlorine"],
    "Sports/Gym/Clubhouse": ["gym", "treadmill", "clubhouse",
                             "badminton"],
    "Children's Play Area": ["playground", "play area", "swing",
                             "slide"],
    "Parking Management": ["parking", "car park", "bike park"],
    "Noise/Visitor": ["noise", "loud", "music too", "party", "disturb"],
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
    "society. Residents may write in English, Hindi, Hinglish, Marathi, "
    "Gujarati, Punjabi, Kannada, Tamil, Telugu or Malayalam, in native "
    "script or transliteration, with typos. If photos are attached, also "
    "judge severity and safety from what you see. "
    "Return ONLY a JSON object with keys: unit_number (string or null - "
    "EXTRACT VERBATIM from the resident's message or photo; do not invent "
    "or normalize. Examples: '5B', 'A-101', '12', 'Flat 7C' -> '7C'. If "
    "the message has no unit reference, return null. Never substitute a "
    "different number), "
    f"category (one of {CATEGORIES}), priority (one of "
    '["normal","high","urgent"]; raise it if a photo shows severe/unsafe '
    "damage; if the resident writes 'urgent', 'emergency', 'asap', "
    "'turant', 'jaldi' or similar, return 'urgent' - do not downgrade "
    "their stated urgency), detected_language (one of english, hindi, "
    "hinglish, marathi, gujarati, punjabi, kannada, tamil, telugu, "
    "malayalam), acknowledgement (a short, warm, human-sounding "
    "confirmation written in the SAME language and script the resident "
    "used, with no ticket number). No prose, JSON only."
)


def _build_system(langs: list[str]) -> str:
    """Base prompt + an instruction to also emit official_summaries
    keyed by the configured language codes (for society staff who may
    not read the resident's language)."""
    names = ", ".join(f"{_LANG_NAMES[c]} ({c})" for c in langs)
    codes = ", ".join(langs)
    return (
        _SYSTEM
        + " Additionally include one more key, official_summaries: a JSON "
        f"object whose keys are EXACTLY these language codes [{codes}] and "
        "whose value for each is a clear 1-2 sentence factual summary of "
        "the complaint (unit, problem, urgency) for society staff, written "
        f"in that language regardless of the resident's language: {names}. "
        "Still return JSON only."
    )


_PRIORITY_RANK = {"normal": 0, "high": 1, "urgent": 2}


def _unit_in_text(unit: str, text: str) -> bool:
    """Loose substring match: LLM-returned units may differ in casing
    or have surrounding whitespace stripped (e.g. '5 B' -> '5B'). We
    accept either the literal form or the normalised (no-whitespace,
    no-dash) form being present in the source."""
    if not unit or not text:
        return False
    needle = re.sub(r"[\s\-]", "", unit).lower()
    haystack = re.sub(r"[\s\-]", "", text).lower()
    return needle in haystack


def _guard_unit(
    llm_unit: str | None, text: str, has_image: bool,
) -> str | None:
    """Hallucination guard: if the LLM returned a unit that doesn't
    appear in the source text AND no image was attached (units in
    photos can't be re-derived from text), prefer the rule-based
    extractor when it finds one. Returns the final unit_number."""
    if not llm_unit:
        return _extract_unit(text) if text else None
    if has_image:
        return llm_unit  # cannot validate against text alone
    if _unit_in_text(llm_unit, text):
        return llm_unit  # LLM unit is present in text - trust it
    rule_unit = _extract_unit(text)
    if rule_unit:
        log.warning(
            "parser: LLM unit_number %r not found in text; "
            "overriding with rule-extracted %r. text=%r",
            llm_unit, rule_unit, text[:120],
        )
        return rule_unit
    # No rule unit either - trust the LLM (might be a unit in an
    # unusual format we don't capture in the regex).
    return llm_unit


def _ceiling_priority(llm_priority: str, text: str) -> str:
    """Take max(llm_priority, rule_priority) so the LLM cannot
    downgrade urgency words the resident explicitly used."""
    rule_priority = _priority(text)
    lp = _PRIORITY_RANK.get(llm_priority, 0)
    rp = _PRIORITY_RANK.get(rule_priority, 0)
    if rp > lp:
        log.warning(
            "parser: LLM priority %r downgraded resident's stated "
            "urgency; raising to %r. text=%r",
            llm_priority, rule_priority, text[:120],
        )
        return rule_priority
    return llm_priority


def _llm_parse(
    text: str,
    image_urls: list[str] | None = None,
    langs: list[str] | None = None,
) -> ParsedComplaint:
    import anthropic

    langs = langs or ["hi"]
    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)

    if image_urls:
        content: list = [{"type": "text", "text": text or "(see photo)"}]
        for url in image_urls:
            content.append(
                {"type": "image", "source": {"type": "url", "url": url}}
            )
    else:
        content = text

    resp = client.messages.create(
        model=s.haiku_model,
        max_tokens=900,  # room for several short staff summaries
        system=_build_system(langs),
        messages=[{"role": "user", "content": content}],
    )
    body = resp.content[0].text.strip()
    body = re.sub(r"^```(?:json)?|```$", "", body, flags=re.MULTILINE).strip()
    data = json.loads(body)
    cat = data.get("category", "Other")
    if cat not in CATEGORIES:
        cat = "Other"
    raw_sum = data.get("official_summaries") or {}
    summaries = {
        c: str(raw_sum[c]).strip()
        for c in langs
        if isinstance(raw_sum, dict) and raw_sum.get(c)
    }
    final_unit = _guard_unit(
        data.get("unit_number") or None,
        text,
        has_image=bool(image_urls),
    )
    final_priority = _ceiling_priority(
        data.get("priority", "normal"), text,
    )
    return ParsedComplaint(
        unit_number=final_unit,
        category=cat,
        priority=final_priority,
        acknowledgement=data.get("acknowledgement", ""),
        detected_language=data.get("detected_language"),
        official_summaries=summaries,
    )


def parse_complaint(
    text: str, image_urls: list[str] | None = None
) -> ParsedComplaint:
    """Parse free text (+ optional photo URLs) into structured fields.

    Uses Haiku when a key is configured; falls back to the rule-based
    parser on any error so intake never fails.
    """
    s = get_settings()
    if not s.anthropic_api_key:
        return rule_based_parse(text)
    try:
        return _llm_parse(text, image_urls, _configured_langs())
    except Exception as exc:
        # Graceful degradation: fall back to rule-based parser so intake
        # never fails. Operator-event makes the silent fallback visible
        # in the diagnostics tile / event log.
        try:
            from . import operator_events
            operator_events.log_event(
                "external_call_failed",
                f"Anthropic parser failed, fell back to rule-based: "
                f"{type(exc).__name__}: {exc}",
                service="anthropic", severity="error",
                metadata={"exc_type": type(exc).__name__,
                          "exc_str": str(exc)[:300],
                          "fallback": "rule_based_parse"},
            )
        except Exception:
            pass  # never let logging itself break the parser
        return rule_based_parse(text)
