"""Historical-complaint generator for AIBuildCare demo tenants.

Reads Part 1 configs + Part 1 parking overlays + Part 2 people JSONs,
emits one complaints_{label}.json per society under ./people/. The
seeder in Part 6 ingests these and inserts into complaints +
complaint_ratings (and optionally complaint_messages /
complaint_status_history derived from the timeline).

Targets agreed in the Part 2 sign-off:
  status:           65% resolved / 20% closed / 10% in-progress / 5% zombie
  priority:         60% normal / 25% high / 5% urgent / 10% low
  resolution time:  75% within SLA / 15% slightly over / 7% well over / 3% overdue
  rating (resolved): 50% 5 / 25% 4 / 15% 3 / 7% 2 / 3% 1
  language:         ~70% English / ~15% Hinglish / ~10% Hindi / ~5% photo-only / voice-note / Telugu

★ CRON-SAFETY (Part 0-B). Every historical complaint here is in a NON-OPEN
status (resolved / closed / rejected) EXCEPT the explicit churn-orphan
records (which are deliberately in-progress / assigned to deactivated
staff — these are the zombies the dashboard needs to surface). The cron
ignores resolved/closed and the zombies have status open but no NEW
escalation will fire because the existing escalation_to_*_at timestamps
already mark the level they reached.

★ HISTORICAL RESOLUTION TIMESCALES vs DEMO SLA. The demo tenants have
ultra-short SLAs in category_sla_config (3-min L3 thresholds) for FAST
ESCALATION TESTING of fresh complaints. Historical records here use
REALISTIC hour-scale resolution times (4-72 hours typically). Dashboard
SLA-compliance metrics on historical records will look "way over SLA" —
this is acknowledged and explained in the walkthrough (Part 6); the
demo SLAs are for cron testing, not for backdating into historical
compliance metrics.

Usage:
    python generate_complaints.py            # all 4 societies
    python generate_complaints.py --sid 100  # one society
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Windows console defaults to cp1252; this script prints non-ASCII summary
# characters and writes JSON with Devanagari / Telugu text. Force UTF-8 so
# both stdout and the encoding-aware writes work uniformly.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from complaint_text_bank import (
    bank_stats, pick_template, pick_photo_only, pick_voice_note, pick_telugu,
    category_supports_voice, category_supports_photo,
)


HERE = Path(__file__).resolve().parent
PEOPLE_DIR = HERE / "people"
NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)


CONFIGS = {
    100: ("greenwood_residency.json",    "greenwood",   "parking_scenario_greenwood.json", "GW"),
    101: ("sunrise_nursing_home.json",   "sunrise",     None,                              "SR"),
    102: ("stellar_events.json",         "stellar",     None,                              "ST"),
    103: ("meridian_estate_office.json", "meridian",    "parking_scenario_meridian.json",  "MR"),
}

# Total complaint counts (target). Actual count = total includes orphans
# + parking-historicals + media + regular.
TOTAL_COMPLAINTS_PER_SOCIETY = {
    100: 120,
    101:  80,
    102:  40,
    103:  50,
}

# Status mix on regular (non-orphan, non-parking) complaints
STATUS_MIX = [
    ("resolved",   0.65),
    ("closed",     0.20),
    ("in_progress",0.10),
    ("rejected",   0.05),
]

PRIORITY_MIX = [
    ("normal", 0.60),
    ("high",   0.25),
    ("low",    0.10),
    ("urgent", 0.05),
]

# Resolution-time spread (multiplier on the per-category baseline hours)
# Drawn for resolved/closed complaints only.
RESOLUTION_SPREAD = [
    ("within",       0.75, (0.4, 0.9)),
    ("slightly",     0.15, (1.0, 1.3)),
    ("over",         0.07, (1.5, 2.5)),
    ("never_in_time",0.03, (3.0, 6.0)),  # extreme; still counted as resolved
]

# Per-category baseline resolution time (hours) — realistic operational
# values, used as the multiplier base. Independent of the demo SLAs in
# category_sla_config (those are for escalation testing only). Loosely
# follows Palms's seeded SLAs.
BASELINE_RESOLUTION_HOURS_BY_CATEGORY = {
    "Fire Safety":           1.0,
    "Security":              2.0,
    "Elevator":              2.0,
    "Lift":                  2.0,
    "Lift Down":             2.0,
    "Lift":                  2.0,
    "Generator/Power Backup": 4.0,
    "Power Outage":          4.0,
    "Electrical":            6.0,
    "Electrical — General":  6.0,
    "Electrical — Critical Area": 1.0,
    "Electrical — Suite":    6.0,
    "AC/Cooling":            4.0,
    "Patient Room AC":       2.0,
    "HVAC":                  6.0,
    "HVAC — Critical Area":  1.0,
    "HVAC — Ward":           4.0,
    "Plumbing":              8.0,
    "Plumbing — Critical Area": 1.0,
    "Plumbing — General":    8.0,
    "Water Supply":          4.0,
    "Sewage/Drainage":       4.0,
    "Lighting":              12.0,
    "Housekeeping":          24.0,
    "Garbage/Waste":         8.0,
    "Pest Control":          24.0,
    "Gardening":             48.0,
    "Carpentry":             24.0,
    "Painting":              48.0,
    "Civil/Structural":      72.0,
    "Building Maintenance":  48.0,
    "CCTV/Intercom":         24.0,
    "Card Access / Door":    4.0,
    "IT / Network":          4.0,
    "IT / Patient Records System": 4.0,
    "Swimming Pool":         24.0,
    "Sports/Gym/Clubhouse":  48.0,
    "Children's Play Area":  24.0,
    "Parking Management":    24.0,
    "Parking":               24.0,
    "Noise/Visitor":         4.0,
    "Reception / Visitor Mgmt": 8.0,
    "Pantry / Cafeteria":    24.0,
    "Cafeteria Food Quality": 4.0,
    "Cleanliness — Common Area": 24.0,
    "Cleanliness — Suite":   48.0,
    "Cleanliness — General": 24.0,
    "Cleanliness — Critical Area": 1.0,
    "Washroom":              8.0,
    "Meeting Room Booking":  4.0,
    "Conference Room AV":    4.0,
    "Bed/Mattress Issue":    8.0,
    "Nurse Call System":     1.0,
    "Pharmacy Stock-Out":    8.0,
    "Equipment Calibration": 24.0,
    "Medical Gas / Oxygen":  0.5,
    "Linen / Laundry":       8.0,
    "Food Service / Diet":   2.0,
    "Wheelchair / Stretcher":24.0,
    "Biomedical Waste":      8.0,
    "AV / Sound":            1.0,
    "Stage Setup":           2.0,
    "Catering — Food Quality": 1.0,
    "Catering — Service Delay": 2.0,
    "Decor":                 4.0,
    "Floral / Bridal Suite": 4.0,
    "Photography / Videography": 4.0,
    "Transport / Logistics": 4.0,
    "Vendor No-Show":        2.0,
    "Equipment Broken":      4.0,
    "Power / Generator":     1.0,
    "Crew Shortage / No-Show": 2.0,
    "Schedule Slip":         2.0,
    "Permit / Authority Issue": 4.0,
    "Client Complaint":      4.0,
    "Safety Incident":       1.0,
    "Pyrotechnics / SFX":    1.0,
    "Backstage / Green Room": 8.0,
    "Hostess / Usher":       8.0,
    "Signage / Wayfinding":  24.0,
    "Other":                 24.0,
}

# Rating distribution on resolved complaints (skewed positive but not unanimous)
RATING_DIST = [
    (5, 0.50), (4, 0.25), (3, 0.15), (2, 0.07), (1, 0.03),
]

# Optional rating feedback text by rating
RATING_FEEDBACK = {
    5: ["Excellent quick response, thank you", "Resolved beautifully", "Very satisfied", None, None],
    4: ["Good service overall", "Resolved well, slight delay", None],
    3: ["OK but could be faster", "Took longer than expected", None],
    2: ["Took too long, follow-up needed", "Quality of work poor"],
    1: ["Very dissatisfied", "Had to escalate twice", "Need management attention"],
}

# Language distribution for the raw_text
LANGUAGE_MIX = [
    ("en",       0.62),
    ("hinglish", 0.18),
    ("hi",       0.10),
    ("te",       0.02),
    ("photo",    0.04),
    ("voice",    0.04),
]

# Channel distribution
CHANNEL_MIX = [
    ("whatsapp", 0.65),
    ("dashboard",0.20),
    ("voice",    0.08),
    ("email",    0.05),
    ("sms",      0.02),
]


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _weighted_pick(rng: random.Random, dist: list[tuple]):
    items = [x[0] for x in dist]
    weights = [x[1] for x in dist]
    return rng.choices(items, weights=weights, k=1)[0]


def _weighted_pick_3(rng: random.Random, dist: list[tuple[str, float, tuple]]):
    """Distribution items are (label, weight, payload). Returns (label, payload)."""
    items = list(range(len(dist)))
    weights = [d[1] for d in dist]
    i = rng.choices(items, weights=weights, k=1)[0]
    return dist[i][0], dist[i][2]


def _parse_days_from_text(text: str, default: int) -> int:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not m:
        return default
    try:
        ts = datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
        return max(1, (NOW - ts).days)
    except Exception:
        return default


def _category_baseline_hours(category: str) -> float:
    return BASELINE_RESOLUTION_HOURS_BY_CATEGORY.get(category, 12.0)


def _category_weight(cat: dict) -> float:
    """Weighted pick across categories. 'common: true' → 3x weight."""
    return 3.0 if cat.get("common") else 1.0


def _category_default_priority(cat: dict, fallback: str = "normal") -> str:
    return cat.get("priority_default", fallback)


def _ticket(prefix: str, n: int) -> str:
    return f"{prefix}-2026-{n:05d}"


# Escalation thresholds (realistic hour scale for historical complaints)
ESCALATION_THRESHOLDS_HOURS = {
    1: 4.0,   # L1 manager after 4h
    2: 12.0,  # L2 sr_manager after 12h
    3: 24.0,  # L3 secretary/medical_supt after 24h
    4: 48.0,  # L4 chairman after 48h
}


def _escalation_timestamps(
    created_at: datetime,
    elapsed_hours: float,
) -> dict:
    """Return dict of escalated_to_*_at columns populated for any level
    whose threshold was exceeded during the complaint's life."""
    out: dict[str, str | None] = {
        "escalated_to_manager_at":     None,
        "escalated_to_sr_manager_at":  None,
        "escalated_to_secretary_at":   None,
        "escalated_to_chairman_at":    None,
    }
    cols = (
        (1, "escalated_to_manager_at"),
        (2, "escalated_to_sr_manager_at"),
        (3, "escalated_to_secretary_at"),
        (4, "escalated_to_chairman_at"),
    )
    for level, col in cols:
        th = ESCALATION_THRESHOLDS_HOURS[level]
        if elapsed_hours >= th:
            out[col] = _iso(created_at + timedelta(hours=th))
    return out


def _substitute(text: str, unit: str | None, plate: str | None = None) -> str:
    """Inject placeholders into a template string. Any placeholder that
    isn't filled gets stripped (replaced with a sensible default) so the
    final text never contains literal `{var}` substrings."""
    if not text:
        return text
    text = text.replace("{unit}", unit or "(unit)")
    text = text.replace("{plate}", plate or "(plate)")
    text = re.sub(r"\{detail\}", "see complaint detail", text)
    text = re.sub(r"\{slot\}", "(slot)", text)
    text = re.sub(r"\{time\}", "this morning", text)
    text = re.sub(r"\{violation_desc\}", "violation", text)
    # Any remaining {…} placeholder gets blanked out
    text = re.sub(r"\{[a-zA-Z_]+\}", "", text)
    return text


# ─────────────────────────────────────────────────────────────────────────
# Single-complaint constructor
# ─────────────────────────────────────────────────────────────────────────

def _make_complaint(
    rng: random.Random, ticket_number: str, sid: int, vertical: str,
    user: dict, unit_number: str | None, category: str, priority: str,
    status: str, channel: str, created_at: datetime,
    resolved_at: datetime | None, escalation_level_reached: int,
    assigned_staff_id_hint: int | None = None,
    contractor_id_hint: int | None = None,
    raw_text_override: str | None = None,
    detected_language_override: str | None = None,
    media_urls: list[str] | None = None,
    vehicle_plate: str | None = None, violation_type: str | None = None,
    clamped: int = 0, clamped_at_days_ago: int | None = None,
    major_incident: int = 0, major_incident_reason: str | None = None,
) -> dict:
    elapsed_h = (
        ((resolved_at or NOW) - created_at).total_seconds() / 3600.0
        if status in ("resolved", "closed", "rejected") else
        (NOW - created_at).total_seconds() / 3600.0
    )
    # Pick language + text. The language tag (`detected_language` on the
    # complaint) tracks what was ACTUALLY picked after any fallback —
    # so a "Pest Control" complaint that asked for Hindi but had no Hindi
    # template and fell through to English ends up tagged "en", not "hi".
    if raw_text_override is not None:
        raw_text = raw_text_override
        lang = detected_language_override or "en"
    else:
        lang_chosen = _weighted_pick(rng, LANGUAGE_MIX)

        # Skip media-style "languages" for categories that don't plausibly
        # carry that medium (e.g. voice notes don't belong on Pharmacy
        # Stock-Out tickets). Fall back to English.
        if lang_chosen == "voice" and not category_supports_voice(category):
            lang_chosen = "en"
        if lang_chosen == "photo" and not category_supports_photo(category):
            lang_chosen = "en"

        if lang_chosen == "photo":
            raw_text = pick_photo_only(rng)
            lang = "en"
        elif lang_chosen == "voice":
            raw_text = pick_voice_note(rng)
            lang = "hi"
        elif lang_chosen == "te":
            te = pick_telugu(rng, category)
            if te:
                raw_text = te
                lang = "te"
            else:
                tpl, actual_lang = pick_template(rng, vertical, category, "en")
                raw_text = tpl or f"Issue at {unit_number or '(unspecified)'} - {category}"
                lang = actual_lang
        else:
            tpl, actual_lang = pick_template(rng, vertical, category, lang_chosen)
            raw_text = tpl or f"Issue at {unit_number or '(unspecified)'} - {category}"
            lang = actual_lang
        raw_text = _substitute(raw_text, unit_number, vehicle_plate)

    # Escalation timestamps
    esc = _escalation_timestamps(created_at, elapsed_h) if escalation_level_reached > 0 else {
        "escalated_to_manager_at":     None,
        "escalated_to_sr_manager_at":  None,
        "escalated_to_secretary_at":   None,
        "escalated_to_chairman_at":    None,
    }
    # Cap escalation columns to the reached level — don't set columns
    # for levels above the one historically reached.
    keep = (
        ("escalated_to_manager_at",    1),
        ("escalated_to_sr_manager_at", 2),
        ("escalated_to_secretary_at",  3),
        ("escalated_to_chairman_at",   4),
    )
    for col, lvl in keep:
        if escalation_level_reached < lvl:
            esc[col] = None

    record = {
        "ticket_number": ticket_number,
        "society_id":    sid,
        "unit_number":   unit_number,
        "category":      category,
        "priority":      priority,
        "status":        status,
        "channel":       channel,
        "raw_text":      raw_text,
        "acknowledgement": "Received, processing." if status != "rejected" else None,
        "reporter_phone": user["phone"] if user else None,
        "reporter_email": None,
        "contractor_id_hint": contractor_id_hint,
        "assigned_staff_id_hint": assigned_staff_id_hint,
        "media_urls":    media_urls,
        "detected_language": lang,
        "official_summaries": None,
        "estimated_completion_date": None,
        **esc,
        "last_complainant_update_at":    _iso(NOW - timedelta(hours=elapsed_h * 0.7)) if status == "in_progress" else None,
        "last_assigned_staff_update_at": _iso(NOW - timedelta(hours=elapsed_h * 0.5)) if status == "in_progress" else None,
        "last_reminder_sent_at":         None,
        "reminder_sent_count": 0,
        "major_incident":          major_incident,
        "major_incident_flagged_at": _iso(created_at + timedelta(hours=2)) if major_incident else None,
        "major_incident_reason":   major_incident_reason,
        # Parking columns
        "vehicle_plate":   vehicle_plate,
        "vehicle_id_hint": None,  # seeder will resolve plate→vehicle_id at insert time
        "violation_type":  violation_type,
        "clamped":         clamped,
        "clamped_at":      _iso(created_at + timedelta(hours=4)) if clamped else None,
        "clamping_authorized_by_role": "secretary" if clamped else None,
        # Timestamps
        "created_at":  _iso(created_at),
        "updated_at":  _iso(resolved_at or NOW),
        "resolved_at": _iso(resolved_at) if resolved_at else None,
    }
    return record


def _make_rating(
    rng: random.Random, ticket_number: str, rating: int, created_at: datetime,
) -> dict:
    feedback_pool = RATING_FEEDBACK.get(rating, [None])
    feedback = rng.choice(feedback_pool)
    return {
        "ticket_number": ticket_number,
        "rating": rating,
        "feedback": feedback,
        "created_at": _iso(created_at + timedelta(hours=rng.randint(1, 48))),
    }


# ─────────────────────────────────────────────────────────────────────────
# Society generation
# ─────────────────────────────────────────────────────────────────────────

def _common_categories(config: dict) -> list[dict]:
    return [c for c in config["categories"] if c["name"] != "Other"]


def _random_user_for(rng: random.Random, soc_people: dict) -> dict | None:
    users = soc_people["users"]
    return rng.choice(users) if users else None


def _generate_regular_complaint(
    rng: random.Random, sid: int, vertical: str,
    config: dict, soc_people: dict, ticket_number: str,
) -> dict:
    user = _random_user_for(rng, soc_people)
    unit = user["unit_number"] if user else None
    cats = _common_categories(config)
    weights = [_category_weight(c) for c in cats]
    cat = rng.choices(cats, weights=weights, k=1)[0]
    category = cat["name"]
    priority = cat.get("priority_default", "normal")
    # Override priority to add some randomness
    if rng.random() < 0.35:
        priority = _weighted_pick(rng, PRIORITY_MIX)

    status = _weighted_pick(rng, STATUS_MIX)
    channel = _weighted_pick(rng, CHANNEL_MIX)

    # Created timestamp: spread over past 7 months, with evening bias
    days_ago = rng.randint(1, 210)
    hour = rng.choices(
        list(range(24)),
        weights=[1,1,1,1,1,2,3,4,5,6,6,6,5,4,4,5,7,8,9,8,6,5,3,2],
        k=1,
    )[0]
    created_at = NOW - timedelta(days=days_ago, hours=rng.randint(0, 23) - hour)
    created_at = created_at.replace(minute=rng.randint(0, 59), second=rng.randint(0, 59))

    baseline_h = _category_baseline_hours(category)
    if priority in ("high", "urgent"):
        baseline_h *= 0.5

    if status in ("resolved", "closed", "rejected"):
        _, (lo, hi) = _weighted_pick_3(rng, RESOLUTION_SPREAD)
        actual_h = baseline_h * rng.uniform(lo, hi)
        resolved_at = created_at + timedelta(hours=actual_h)
        if resolved_at > NOW:
            # Edge case — push resolution to "currently in_progress" if it would be future
            status = "in_progress"
            resolved_at = None
            elapsed_h = (NOW - created_at).total_seconds() / 3600.0
        else:
            elapsed_h = actual_h
    else:
        resolved_at = None
        elapsed_h = (NOW - created_at).total_seconds() / 3600.0

    # Escalation: derived from how long the complaint took relative to
    # ESCALATION_THRESHOLDS_HOURS
    esc_level = 0
    for lvl in (1, 2, 3, 4):
        if elapsed_h >= ESCALATION_THRESHOLDS_HOURS[lvl]:
            esc_level = lvl

    return _make_complaint(
        rng, ticket_number, sid, vertical, user, unit, category, priority,
        status, channel, created_at, resolved_at, esc_level,
    )


def _generate_orphan_complaints(
    rng: random.Random, sid: int, vertical: str,
    config: dict, soc_people: dict, ticket_start: int, prefix: str,
) -> list[dict]:
    """Generate complaints assigned to deactivated staff. These are the
    zombie/orphan records the dashboard should surface."""
    out: list[dict] = []
    cats = {c["name"]: c for c in config["categories"]}

    for staff in soc_people["staff_members"]:
        if staff["active"] != 0:
            continue
        cm = staff.get("__churn_meta__") or {}
        count = cm.get("holds_open_complaints_at_deactivation", 0)
        top_pri = cm.get("highest_open_priority", "normal")
        top_lvl = cm.get("highest_escalation_level_at_deactivation", 0)
        # Pick category matching staff's specialty if available, else
        # any common category
        specialty = staff.get("category_specialty")
        for i in range(count):
            ticket_start += 1
            tn = _ticket(prefix, ticket_start)
            cat_name = specialty if specialty in cats else rng.choice(
                [c["name"] for c in config["categories"] if c.get("common") and c["name"] != "Other"]
            )
            user = _random_user_for(rng, soc_people)
            unit = user["unit_number"] if user else None
            # First complaint gets the "worst case" priority + esc level
            priority = top_pri if i == 0 else "normal"
            esc_level = top_lvl if i == 0 else 0
            # Created shortly before deactivation
            deact_days = _parse_days_from_text(staff.get("deactivation_reason", ""), 45)
            days_before_deact = rng.randint(2, 14)
            created_at = NOW - timedelta(days=deact_days + days_before_deact, hours=rng.randint(0, 23))
            comp = _make_complaint(
                rng, tn, sid, vertical, user, unit, cat_name, priority,
                status="in_progress", channel="whatsapp",
                created_at=created_at, resolved_at=None,
                escalation_level_reached=esc_level,
            )
            # Tag for the seeder to wire assignment to this deactivated staff
            comp["__assigned_to_deactivated_staff__"] = {
                "phone": staff["phone"],
                "role_key": staff["role_key"],
                "deactivated_at": staff["deactivated_at"],
            }
            out.append(comp)

    # Also generate orphan jobs for the retired contractor
    for c in soc_people["contractors"]:
        if c["is_active"] != 0:
            continue
        cm = c.get("__churn_meta__") or {}
        count = cm.get("holds_open_jobs_at_retirement", 0)
        top_pri = cm.get("highest_open_priority", "normal")
        for i in range(count):
            ticket_start += 1
            tn = _ticket(prefix, ticket_start)
            cat_name = c["category"]
            user = _random_user_for(rng, soc_people)
            unit = user["unit_number"] if user else None
            retired_days = _parse_days_from_text(c.get("retirement_reason", ""), 30)
            days_before_retire = rng.randint(5, 20)
            created_at = NOW - timedelta(days=retired_days + days_before_retire, hours=rng.randint(0, 23))
            comp = _make_complaint(
                rng, tn, sid, vertical, user, unit, cat_name,
                priority=top_pri if i == 0 else "normal",
                status="in_progress", channel="whatsapp",
                created_at=created_at, resolved_at=None,
                escalation_level_reached=1,
            )
            comp["__assigned_to_retired_contractor__"] = {
                "phone": c["phone"],
                "vendor_name": c["vendor_name"],
                "retired_at": c["retired_at"],
            }
            out.append(comp)

    return out


def _generate_parking_historical(
    rng: random.Random, sid: int, vertical: str,
    config: dict, parking: dict, soc_people: dict,
    ticket_start: int, prefix: str,
) -> list[dict]:
    """Generate one complaint per historical violation on the
    deterministic repeat-offender plates."""
    out: list[dict] = []
    if not parking:
        return out
    cat_name = "Parking Management" if sid == 100 else "Parking"
    plates = parking["deterministic_repeat_offender_plates"]["plates"]
    for plate_info in plates:
        plate = plate_info["plate"]
        for vi, viol in enumerate(plate_info["violations_seeded"]):
            ticket_start += 1
            tn = _ticket(prefix, ticket_start)
            days_ago = viol["days_ago"]
            created_at = NOW - timedelta(days=days_ago, hours=rng.randint(0, 23))
            # All historical parking violations are in resolved status
            actual_h = rng.uniform(2.0, 24.0)
            resolved_at = created_at + timedelta(hours=actual_h)
            # Trigger major-incident on the 3rd or 4th violation of this plate
            is_third_plus = vi >= 2
            major = 1 if is_third_plus else 0
            major_reason = (
                f"Repeat offender — plate {plate} 3+ violations in 30 days"
                if major else None
            )
            user = _random_user_for(rng, soc_people)
            unit = plate_info.get("owner_unit") or (user["unit_number"] if user else None)
            comp = _make_complaint(
                rng, tn, sid, vertical, user, unit, cat_name,
                priority="high" if major else "normal",
                status="resolved", channel="whatsapp",
                created_at=created_at, resolved_at=resolved_at,
                escalation_level_reached=1 if major else 0,
                vehicle_plate=plate,
                violation_type=viol["type"],
                clamped=1 if viol.get("clamping_authorized") else 0,
                major_incident=major,
                major_incident_reason=major_reason,
            )
            # Override raw_text with a parking-specific phrasing
            comp["raw_text"] = _substitute(
                rng.choice([
                    "Vehicle {plate} {violation_desc} near {unit}",
                    "{plate} parked illegally — {violation_desc}",
                    "Violation: {plate} — {violation_desc}",
                ]),
                unit, plate,
            ).replace("{violation_desc}", viol["type"].replace("_", " "))
            out.append(comp)
    return out


def generate_society_complaints(sid: int) -> dict:
    config_filename, label, parking_filename, prefix = CONFIGS[sid]
    config = json.loads((HERE / config_filename).read_text(encoding="utf-8"))
    parking = json.loads((HERE / parking_filename).read_text(encoding="utf-8")) if parking_filename else None
    soc_people = json.loads((PEOPLE_DIR / f"{label}.json").read_text(encoding="utf-8"))
    vertical = config["_meta"]["vertical"]
    rng = random.Random(f"aibuildcare-complaints-{sid}-v1")

    complaints: list[dict] = []

    # Orphan complaints first (tickets 00001…)
    orphan = _generate_orphan_complaints(
        rng, sid, vertical, config, soc_people, ticket_start=0, prefix=prefix,
    )
    complaints.extend(orphan)
    next_n = len(orphan)

    # Parking historicals
    parking_hist = _generate_parking_historical(
        rng, sid, vertical, config, parking, soc_people,
        ticket_start=next_n, prefix=prefix,
    )
    complaints.extend(parking_hist)
    next_n += len(parking_hist)

    # Regular complaints to fill the target count
    target = TOTAL_COMPLAINTS_PER_SOCIETY[sid]
    remaining = max(0, target - len(complaints))
    for _ in range(remaining):
        next_n += 1
        complaints.append(_generate_regular_complaint(
            rng, sid, vertical, config, soc_people, _ticket(prefix, next_n),
        ))

    # Sort by created_at for readability
    complaints.sort(key=lambda c: c["created_at"])

    # Ratings on resolved complaints (skewed positive)
    ratings: list[dict] = []
    for c in complaints:
        if c["status"] == "resolved" and rng.random() < 0.85:  # 85% leave a rating
            r = _weighted_pick(rng, RATING_DIST)
            ratings.append(_make_rating(
                rng, c["ticket_number"], r,
                created_at=datetime.fromisoformat(c["resolved_at"]),
            ))

    return {
        "sid": sid,
        "society_name": config["society"]["name"],
        "vertical": vertical,
        "ticket_prefix": prefix,
        "complaints": complaints,
        "ratings": ratings,
        "_summary": _summarize(complaints, ratings),
    }


def _summarize(complaints: list[dict], ratings: list[dict]) -> dict:
    from collections import Counter
    s = {
        "total": len(complaints),
        "by_status":   dict(Counter(c["status"] for c in complaints)),
        "by_priority": dict(Counter(c["priority"] for c in complaints)),
        "by_language": dict(Counter(c["detected_language"] for c in complaints)),
        "by_channel":  dict(Counter(c["channel"] for c in complaints)),
        "escalated_any":  sum(1 for c in complaints if c["escalated_to_manager_at"]),
        "escalated_L2":   sum(1 for c in complaints if c["escalated_to_sr_manager_at"]),
        "escalated_L3":   sum(1 for c in complaints if c["escalated_to_secretary_at"]),
        "escalated_L4":   sum(1 for c in complaints if c["escalated_to_chairman_at"]),
        "major_incidents":sum(1 for c in complaints if c["major_incident"]),
        "clamped":        sum(1 for c in complaints if c["clamped"]),
        "orphan_zombies": sum(1 for c in complaints if c.get("__assigned_to_deactivated_staff__")),
        "retired_jobs":   sum(1 for c in complaints if c.get("__assigned_to_retired_contractor__")),
        "ratings_count":  len(ratings),
        "ratings_avg":    round(sum(r["rating"] for r in ratings) / len(ratings), 2) if ratings else None,
    }
    return s


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sid", type=int, default=None)
    args = p.parse_args()

    print(f"text bank stats: {bank_stats()}")
    print()

    for sid in CONFIGS:
        if args.sid and sid != args.sid:
            continue
        data = generate_society_complaints(sid)
        label = CONFIGS[sid][1]
        out_path = PEOPLE_DIR / f"complaints_{label}.json"
        out_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        s = data["_summary"]
        print(f"sid={sid} {data['society_name']} → {out_path.name}")
        print(f"  total={s['total']} | status={s['by_status']} | pri={s['by_priority']}")
        print(f"  lang={s['by_language']} | channel={s['by_channel']}")
        print(f"  escalated any={s['escalated_any']} L2={s['escalated_L2']} L3={s['escalated_L3']} L4={s['escalated_L4']}")
        print(f"  major_incidents={s['major_incidents']} clamped={s['clamped']} orphan_zombies={s['orphan_zombies']} retired_jobs={s['retired_jobs']}")
        print(f"  ratings count={s['ratings_count']} avg={s['ratings_avg']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
