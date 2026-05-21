"""Part 6 — seeder + per-tenant wipe utility for synthetic demo tenants.

Reads the Part 1 configs, Part 2 people JSONs, and Part 3 complaint
JSONs from ./ and ./people/ respectively, then performs FK-safe inserts
into the AIBuildCare DB. Idempotent: re-running upserts by deterministic
keys (society id, phone, plate, ticket_number) so a second run is a
no-op or a refresh, not a duplicate.

Usage from repo root:

    # Seed all 4 demo societies (idempotent)
    AIBUILDCARE_TESTER_PASSWORD=hunter2 python -m backend.seed_synthetic.runner seed

    # Seed just one
    AIBUILDCARE_TESTER_PASSWORD=hunter2 python -m backend.seed_synthetic.runner seed --sid 100

    # Wipe one demo society (refuses sid=1, refuses non-is_demo=1)
    python -m backend.seed_synthetic.runner wipe --sid 100

    # Show what would be wiped without actually doing it
    python -m backend.seed_synthetic.runner wipe --sid 100 --dry-run

★ DUAL-GUARD against wiping production data (Part 0-A):

  1. SQL guard: SELECT is_demo FROM societies WHERE id = ?; refuse if 0.
  2. Hardcoded guard: if sid == 1: refuse always, regardless of is_demo.

Both must be passed for a wipe to proceed. Either failing = abort.

★ SEEDING_LOCK should be set BEFORE running this script if the live
   Render cron could fire during the seeding window:

       export AIBUILDCARE_SEEDING_LOCK=1
       python -m backend.seed_synthetic.runner seed
       # ... verify ...
       unset AIBUILDCARE_SEEDING_LOCK

   The script does NOT set the lock itself — that's an operator
   responsibility, intentional.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow `python -m backend.seed_synthetic.runner …` from repo root by
# putting `backend/` on the path.
_THIS = Path(__file__).resolve()
_BACKEND_DIR = _THIS.parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db import get_conn, init_db
from app.security import hash_password


HERE = _THIS.parent
PEOPLE_DIR = HERE / "people"

CONFIGS = {
    100: ("greenwood_residency.json",    "greenwood",   "parking_scenario_greenwood.json"),
    101: ("sunrise_nursing_home.json",   "sunrise",     None),
    102: ("stellar_events.json",         "stellar",     None),
    103: ("meridian_estate_office.json", "meridian",    "parking_scenario_meridian.json"),
}

TESTER_PASSWORD_ENV = "AIBUILDCARE_TESTER_PASSWORD"


# ─────────────────────────────────────────────────────────────────────────
# Tiny helpers
# ─────────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _scalar(row: Any, key: str) -> Any:
    if row is None:
        return None
    return row[key] if isinstance(row, dict) else row[0]


def _exists(conn, sql: str, params: tuple) -> bool:
    return conn.execute(sql, params).fetchone() is not None


# ─────────────────────────────────────────────────────────────────────────
# Seed — society + sla_config
# ─────────────────────────────────────────────────────────────────────────

def _upsert_society(conn, config: dict) -> None:
    """Insert society with the locked sid (100..103). UPSERT-by-id."""
    sid = config["_meta"]["sid"]
    soc = config["society"]
    name = soc["name"]
    address = soc.get("address", "")
    is_demo = config["_meta"].get("is_demo", 1)

    row = conn.execute(
        "SELECT id FROM societies WHERE id = ?", (sid,),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE societies SET name = ?, address = ?, is_demo = ? "
            "WHERE id = ?",
            (name, address, is_demo, sid),
        )
    else:
        # NOTE: explicit id insert. Both Postgres SERIAL and SQLite
        # AUTOINCREMENT accept an explicit id; Postgres requires us
        # to bump the sequence afterwards to avoid future collisions.
        conn.execute(
            "INSERT INTO societies (id, name, address, is_demo) "
            "VALUES (?, ?, ?, ?)",
            (sid, name, address, is_demo),
        )
        # Postgres-only sequence bump — silently swallowed on SQLite.
        try:
            conn.execute(
                "SELECT setval('societies_id_seq', "
                "(SELECT MAX(id) FROM societies))"
            )
        except Exception:
            pass


def _seed_sla_config(conn, config: dict) -> None:
    """Per-society, per-category SLA rows (per Part 0-C the demo SLAs
    are ultra-short for testability)."""
    sid = config["_meta"]["sid"]
    sla = config["sla_config"]
    default = sla["default"]
    overrides = sla.get("overrides", {})

    esc_levels = json.dumps(default["escalation_levels"])
    for cat in config["categories"]:
        cat_name = cat["name"]
        over = overrides.get(cat_name, {})
        resp = over.get(
            "target_response_time_minutes",
            default["target_response_time_minutes"],
        )
        resolve_h = over.get(
            "target_resolution_time_hours",
            default["target_resolution_time_hours"],
        )
        multiplier = default.get("priority_high_multiplier", 0.5)

        if _exists(
            conn,
            "SELECT 1 FROM category_sla_config "
            "WHERE society_id = ? AND category = ?",
            (sid, cat_name),
        ):
            conn.execute(
                "UPDATE category_sla_config SET "
                "target_response_time_minutes = ?, "
                "target_resolution_time_hours = ?, "
                "priority_high_multiplier = ?, "
                "escalation_levels = ? "
                "WHERE society_id = ? AND category = ?",
                (resp, resolve_h, multiplier, esc_levels, sid, cat_name),
            )
        else:
            conn.execute(
                "INSERT INTO category_sla_config "
                "(society_id, category, target_response_time_minutes, "
                "target_resolution_time_hours, priority_high_multiplier, "
                "escalation_levels) VALUES (?, ?, ?, ?, ?, ?)",
                (sid, cat_name, resp, resolve_h, multiplier, esc_levels),
            )


# ─────────────────────────────────────────────────────────────────────────
# Seed — units
# ─────────────────────────────────────────────────────────────────────────

def _seed_units(
    conn, sid: int, people: dict,
) -> dict[str, int]:
    """Upsert one units row per occupied unit. Returns a map
    unit_number -> unit_id for FK resolution."""
    unit_id_by_number: dict[str, int] = {}
    seen: set[str] = set()
    for u in people["users"]:
        n = u.get("unit_number")
        if not n or n in seen:
            continue
        seen.add(n)
        owner_name = u.get("full_name")
        if sid == 103:
            owner_name = u.get("tenant_company") or owner_name
        existing = conn.execute(
            "SELECT id FROM units WHERE society_id = ? AND unit_number = ?",
            (sid, n),
        ).fetchone()
        if existing:
            uid = _scalar(existing, "id")
            conn.execute(
                "UPDATE units SET owner_name = ?, phone = ? WHERE id = ?",
                (owner_name, u["phone"], uid),
            )
        else:
            cur = conn.execute(
                "INSERT INTO units (society_id, unit_number, owner_name, phone) "
                "VALUES (?, ?, ?, ?)",
                (sid, n, owner_name, u["phone"]),
            )
            uid = _scalar(
                conn.execute(
                    "SELECT id FROM units WHERE society_id = ? AND unit_number = ?",
                    (sid, n),
                ).fetchone(),
                "id",
            )
        unit_id_by_number[n] = uid
    return unit_id_by_number


# ─────────────────────────────────────────────────────────────────────────
# Seed — staff_members (active + deactivated) + staff_categories
# ─────────────────────────────────────────────────────────────────────────

def _seed_staff(
    conn, sid: int, people: dict, config: dict,
) -> dict[str, int]:
    """Insert staff_members + staff_categories; return phone -> staff_id."""
    by_phone: dict[str, int] = {}

    for s in people["staff_members"]:
        phone = s["phone"]
        existing = conn.execute(
            "SELECT id FROM staff_members WHERE society_id = ? "
            "AND phone_primary = ?",
            (sid, phone),
        ).fetchone()
        notes_json = json.dumps({
            "role_key": s["role_key"],
            "title": s["title"],
            "in_chain": s["in_chain"],
            "chain_level": s.get("chain_level"),
            "deactivation_reason": s.get("deactivation_reason"),
            "is_test_user": s.get("is_test_user", True),
        })
        if existing:
            sid_row = _scalar(existing, "id")
            conn.execute(
                "UPDATE staff_members SET name = ?, whatsapp_enabled = ?, "
                "active = ?, notes = ? WHERE id = ?",
                (s["full_name"],
                 1 if s["phone_whatsapp_enabled"] else 0,
                 s["active"], notes_json, sid_row),
            )
        else:
            conn.execute(
                "INSERT INTO staff_members (society_id, name, phone_primary, "
                "whatsapp_enabled, active, hire_date, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, s["full_name"], phone,
                 1 if s["phone_whatsapp_enabled"] else 0,
                 s["active"], s.get("created_at"), notes_json),
            )
            sid_row = _scalar(
                conn.execute(
                    "SELECT id FROM staff_members WHERE society_id = ? "
                    "AND phone_primary = ?",
                    (sid, phone),
                ).fetchone(),
                "id",
            )
        by_phone[phone] = sid_row

        # staff_categories — link to category specialty if set
        cat = s.get("category_specialty")
        if cat:
            if not _exists(
                conn,
                "SELECT 1 FROM staff_categories "
                "WHERE staff_id = ? AND category = ?",
                (sid_row, cat),
            ):
                conn.execute(
                    "INSERT INTO staff_categories "
                    "(staff_id, category, primary_category, skill_level) "
                    "VALUES (?, ?, 1, 'mid')",
                    (sid_row, cat),
                )

    return by_phone


# ─────────────────────────────────────────────────────────────────────────
# Seed — contractors (active + retired) + contractor_categories
# ─────────────────────────────────────────────────────────────────────────

def _seed_contractors(
    conn, sid: int, people: dict,
) -> dict[str, int]:
    by_phone: dict[str, int] = {}
    for c in people["contractors"]:
        phone = c["phone"]
        existing = conn.execute(
            "SELECT id FROM contractors WHERE society_id = ? AND phone = ?",
            (sid, phone),
        ).fetchone()
        if existing:
            cid = _scalar(existing, "id")
            conn.execute(
                "UPDATE contractors SET name = ?, specialty = ?, "
                "average_rating = ?, is_active = ? WHERE id = ?",
                (c["vendor_name"], c["category"], c["rating"],
                 c["is_active"], cid),
            )
        else:
            conn.execute(
                "INSERT INTO contractors (society_id, name, phone, "
                "specialty, average_rating, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sid, c["vendor_name"], phone, c["category"],
                 c["rating"], c["is_active"]),
            )
            cid = _scalar(
                conn.execute(
                    "SELECT id FROM contractors WHERE society_id = ? AND phone = ?",
                    (sid, phone),
                ).fetchone(),
                "id",
            )
        by_phone[phone] = cid

        # contractor_categories link
        if not _exists(
            conn,
            "SELECT 1 FROM contractor_categories WHERE contractor_id = ? "
            "AND category = ?",
            (cid, c["category"]),
        ):
            conn.execute(
                "INSERT INTO contractor_categories "
                "(contractor_id, category, primary_category, "
                "average_rating) VALUES (?, ?, 1, ?)",
                (cid, c["category"], c["rating"]),
            )
    return by_phone


# ─────────────────────────────────────────────────────────────────────────
# Seed — escalation_hierarchy
# ─────────────────────────────────────────────────────────────────────────

def _seed_hierarchy(
    conn, sid: int, people: dict, config: dict,
) -> None:
    """Build escalation_hierarchy rows from the seeded staff at each
    chain level."""
    # Find the active staff members at each level
    chain = config["escalation_chain"]
    chain_levels = {c["level"]: c["role_key"] for c in chain}
    for level, role_key in chain_levels.items():
        match = next(
            (s for s in people["staff_members"]
             if s.get("role_key") == role_key and s["active"] == 1),
            None,
        )
        if not match:
            continue
        existing = conn.execute(
            "SELECT id FROM escalation_hierarchy "
            "WHERE society_id = ? AND escalation_level = ? "
            "AND person_name = ?",
            (sid, level, match["full_name"]),
        ).fetchone()
        if existing:
            continue  # already linked
        # Also dedup by (sid, level, phone) — different name same person
        if _exists(
            conn,
            "SELECT 1 FROM escalation_hierarchy WHERE society_id = ? "
            "AND escalation_level = ? AND phone = ?",
            (sid, level, match["phone"]),
        ):
            continue
        conn.execute(
            "INSERT INTO escalation_hierarchy "
            "(society_id, role_name, person_name, phone, "
            "whatsapp_enabled, escalation_level, "
            "response_time_target_minutes, active) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, 1)",
            (sid, match["title"], match["full_name"], match["phone"],
             level, 60),
        )


# ─────────────────────────────────────────────────────────────────────────
# Seed — vehicles
# ─────────────────────────────────────────────────────────────────────────

def _seed_vehicles(
    conn, sid: int, people: dict,
) -> dict[str, int]:
    by_plate: dict[str, int] = {}
    for v in people["vehicles"]:
        plate = v["plate"]
        existing = conn.execute(
            "SELECT id FROM vehicles WHERE society_id = ? AND plate_number = ?",
            (sid, plate),
        ).fetchone()
        notes = json.dumps({
            "is_test_vehicle": v.get("is_test_vehicle", True),
            "owner_tenant_company": v.get("owner_tenant_company"),
            "slot": v.get("slot"),
            "is_deterministic": v.get("__is_deterministic__", False),
        })
        if existing:
            vid = _scalar(existing, "id")
            conn.execute(
                "UPDATE vehicles SET owner_name = ?, owner_phone = ?, "
                "owner_unit_number = ?, vehicle_type = ?, "
                "active = ?, notes = ? WHERE id = ?",
                (v["owner_name"], v["owner_phone"], v["owner_unit"],
                 v["vehicle_type"], v["active"], notes, vid),
            )
        else:
            conn.execute(
                "INSERT INTO vehicles (society_id, plate_number, "
                "owner_unit_number, owner_name, owner_phone, "
                "vehicle_type, registered_at, active, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, plate, v["owner_unit"], v["owner_name"],
                 v["owner_phone"], v["vehicle_type"],
                 v.get("registered_at"), v["active"], notes),
            )
            vid = _scalar(
                conn.execute(
                    "SELECT id FROM vehicles WHERE society_id = ? "
                    "AND plate_number = ?",
                    (sid, plate),
                ).fetchone(),
                "id",
            )
        by_plate[plate] = vid
    return by_plate


# ─────────────────────────────────────────────────────────────────────────
# Seed — complaints + ratings
# ─────────────────────────────────────────────────────────────────────────

_COMPLAINT_COLUMNS = (
    "ticket_number", "society_id", "unit_id", "unit_number",
    "category", "priority", "status", "channel", "raw_text",
    "acknowledgement", "reporter_phone", "reporter_email",
    "contractor_id", "media_urls", "detected_language",
    "estimated_completion_date", "assigned_staff_id",
    "escalated_to_manager_at", "escalated_to_sr_manager_at",
    "escalated_to_secretary_at", "escalated_to_chairman_at",
    "last_complainant_update_at", "last_assigned_staff_update_at",
    "last_reminder_sent_at", "major_incident",
    "major_incident_flagged_at", "major_incident_reason",
    "vehicle_plate", "vehicle_id", "violation_type",
    "clamped", "clamped_at",
    "created_at", "updated_at", "resolved_at",
)


def _seed_complaints(
    conn, sid: int, complaints_data: dict,
    unit_id_by_number: dict[str, int],
    staff_by_phone: dict[str, int],
    contractor_by_phone: dict[str, int],
    vehicle_by_plate: dict[str, int],
) -> int:
    """Insert (or upsert by ticket_number) every complaint record.
    Resolves __assigned_to_deactivated_staff__ / __assigned_to_retired_
    contractor__ / vehicle_plate to real FK ids at insert time."""
    inserted = 0
    for c in complaints_data["complaints"]:
        tn = c["ticket_number"]
        if _exists(conn, "SELECT 1 FROM complaints WHERE ticket_number = ?", (tn,)):
            continue  # idempotent — leave existing rows alone

        # Resolve FKs
        unit_id = unit_id_by_number.get(c["unit_number"]) if c.get("unit_number") else None
        assigned_staff_id = None
        contractor_id = None

        churn = c.get("__assigned_to_deactivated_staff__")
        if churn:
            assigned_staff_id = staff_by_phone.get(churn["phone"])
        retired = c.get("__assigned_to_retired_contractor__")
        if retired:
            contractor_id = contractor_by_phone.get(retired["phone"])

        vehicle_id = vehicle_by_plate.get(c.get("vehicle_plate")) if c.get("vehicle_plate") else None

        row = {
            "ticket_number": tn,
            "society_id": sid,
            "unit_id": unit_id,
            "unit_number": c.get("unit_number"),
            "category": c["category"],
            "priority": c["priority"],
            "status": c["status"],
            "channel": c["channel"],
            "raw_text": c["raw_text"],
            "acknowledgement": c.get("acknowledgement"),
            "reporter_phone": c.get("reporter_phone"),
            "reporter_email": c.get("reporter_email"),
            "contractor_id": contractor_id,
            "media_urls": json.dumps(c["media_urls"]) if c.get("media_urls") else None,
            "detected_language": c.get("detected_language"),
            "estimated_completion_date": c.get("estimated_completion_date"),
            "assigned_staff_id": assigned_staff_id,
            "escalated_to_manager_at": c.get("escalated_to_manager_at"),
            "escalated_to_sr_manager_at": c.get("escalated_to_sr_manager_at"),
            "escalated_to_secretary_at": c.get("escalated_to_secretary_at"),
            "escalated_to_chairman_at": c.get("escalated_to_chairman_at"),
            "last_complainant_update_at": c.get("last_complainant_update_at"),
            "last_assigned_staff_update_at": c.get("last_assigned_staff_update_at"),
            "last_reminder_sent_at": c.get("last_reminder_sent_at"),
            "major_incident": c.get("major_incident", 0),
            "major_incident_flagged_at": c.get("major_incident_flagged_at"),
            "major_incident_reason": c.get("major_incident_reason"),
            "vehicle_plate": c.get("vehicle_plate"),
            "vehicle_id": vehicle_id,
            "violation_type": c.get("violation_type"),
            "clamped": c.get("clamped", 0),
            "clamped_at": c.get("clamped_at"),
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
            "resolved_at": c.get("resolved_at"),
        }
        cols = ", ".join(_COMPLAINT_COLUMNS)
        placeholders = ", ".join("?" for _ in _COMPLAINT_COLUMNS)
        values = tuple(row[k] for k in _COMPLAINT_COLUMNS)
        conn.execute(
            f"INSERT INTO complaints ({cols}) VALUES ({placeholders})",
            values,
        )
        inserted += 1

    # Ratings
    for r in complaints_data.get("ratings", []):
        comp = conn.execute(
            "SELECT id FROM complaints WHERE ticket_number = ?",
            (r["ticket_number"],),
        ).fetchone()
        if not comp:
            continue
        cid = _scalar(comp, "id")
        if _exists(conn, "SELECT 1 FROM complaint_ratings WHERE complaint_id = ?", (cid,)):
            continue
        conn.execute(
            "INSERT INTO complaint_ratings (complaint_id, rating, "
            "feedback, created_at) VALUES (?, ?, ?, ?)",
            (cid, r["rating"], r.get("feedback"), r["created_at"]),
        )
    return inserted


# ─────────────────────────────────────────────────────────────────────────
# Seed — tester accounts (users table)
# ─────────────────────────────────────────────────────────────────────────

def _seed_tester_accounts(conn, password: str) -> int:
    """Bcrypt the env-provided password once and insert all 12 tester
    accounts. Skips reserved_live_resident_slots (those wait for real
    phones)."""
    payload = _read_json(PEOPLE_DIR / "tester_accounts.json")
    hashed = hash_password(password)
    inserted = 0
    for a in payload["accounts"]:
        email_sid = f"{a['email']}#{a['society_id']}"  # composite identity
        # Tester accounts are SCOPED — each (email, society_id) is a
        # separate user record so the same email logs into different
        # tenants. Users table has UNIQUE(email) so we encode the sid
        # into the email for storage: sravya.resident+sid100@…
        encoded_email = a["email"].replace(
            "@", f"+sid{a['society_id']}@",
        )
        if _exists(
            conn, "SELECT 1 FROM users WHERE email = ?", (encoded_email,),
        ):
            continue
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, "
            "role, society_id, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (encoded_email, hashed,
             f"TESTER {a['email'].split('@')[0]} (sid={a['society_id']})",
             a["role"], a["society_id"]),
        )
        inserted += 1
    return inserted


# ─────────────────────────────────────────────────────────────────────────
# Society-wide seed
# ─────────────────────────────────────────────────────────────────────────

def seed_society(sid: int) -> dict:
    """Run the full seed for one society."""
    config_file, label, _ = CONFIGS[sid]
    config = _read_json(HERE / config_file)
    people = _read_json(PEOPLE_DIR / f"{label}.json")
    complaints_data = _read_json(PEOPLE_DIR / f"complaints_{label}.json")

    summary = {"sid": sid, "label": label}
    with get_conn() as conn:
        _upsert_society(conn, config)
        summary["society"] = "upserted"

        _seed_sla_config(conn, config)
        summary["sla_config_rows"] = len(config["categories"])

        unit_map = _seed_units(conn, sid, people)
        summary["units"] = len(unit_map)

        staff_map = _seed_staff(conn, sid, people, config)
        summary["staff_members"] = len(staff_map)

        contractor_map = _seed_contractors(conn, sid, people)
        summary["contractors"] = len(contractor_map)

        _seed_hierarchy(conn, sid, people, config)
        summary["escalation_hierarchy"] = "linked"

        vehicle_map = _seed_vehicles(conn, sid, people)
        summary["vehicles"] = len(vehicle_map)

        comp_count = _seed_complaints(
            conn, sid, complaints_data, unit_map,
            staff_map, contractor_map, vehicle_map,
        )
        summary["complaints_inserted"] = comp_count
        summary["complaints_total_seeded"] = len(complaints_data["complaints"])

    return summary


def seed_all(password: str | None = None) -> list[dict]:
    """Seed all 4 demo societies + tester accounts. Returns per-society
    summaries."""
    init_db()  # ensure schema is current
    summaries = []
    for sid in CONFIGS:
        summaries.append(seed_society(sid))
    # Tester accounts — separate pass since they're not society-scoped
    if password:
        with get_conn() as conn:
            n = _seed_tester_accounts(conn, password)
            summaries.append({"tester_accounts_inserted": n})
    else:
        summaries.append({
            "tester_accounts_inserted": 0,
            "note": f"{TESTER_PASSWORD_ENV} not set — tester accounts skipped",
        })
    return summaries


# ─────────────────────────────────────────────────────────────────────────
# Wipe — per-tenant with dual-guard
# ─────────────────────────────────────────────────────────────────────────

# Reverse FK order. Each tuple is (table, where-clause-by-sid). Tables
# that don't have society_id directly are joined back through their
# parent.
_WIPE_ORDER = [
    ("complaint_ratings",       "complaint_id IN (SELECT id FROM complaints WHERE society_id = ?)"),
    ("complaint_messages",      "complaint_id IN (SELECT id FROM complaints WHERE society_id = ?)"),
    ("complaint_status_history","complaint_id IN (SELECT id FROM complaints WHERE society_id = ?)"),
    ("complaints",              "society_id = ?"),
    ("vehicles",                "society_id = ?"),
    ("staff_categories",        "staff_id IN (SELECT id FROM staff_members WHERE society_id = ?)"),
    ("staff_members",           "society_id = ?"),
    ("contractor_categories",   "contractor_id IN (SELECT id FROM contractors WHERE society_id = ?)"),
    ("contractors",             "society_id = ?"),
    ("escalation_hierarchy",    "society_id = ?"),
    ("category_sla_config",     "society_id = ?"),
    ("role_permission_overrides","society_id = ?"),
    ("weekly_summaries_sent",   "society_id = ?"),
    ("units",                   "society_id = ?"),
    ("users",                   "society_id = ? AND role != 'admin'"),
    ("operator_events",         "society_id = ?"),
    # societies last — only if we want to fully remove the demo tenant
    ("societies",               "id = ?"),
]


def _wipe_dual_guard(conn, sid: int) -> None:
    """Refuse to wipe unless BOTH guards pass.

    Guard 1: hardcoded sid != 1 (Palms is structurally untouchable).
    Guard 2: societies.is_demo = 1 (only demo tenants are wipe-eligible).
    """
    if sid == 1:
        raise SystemExit(
            "REFUSED: wipe_society called with sid=1 (Palms Residency, "
            "real pilot). This is a hardcoded guard that cannot be "
            "overridden — to truly wipe Palms, code must change."
        )
    row = conn.execute(
        "SELECT is_demo, name FROM societies WHERE id = ?", (sid,),
    ).fetchone()
    if not row:
        raise SystemExit(f"REFUSED: society sid={sid} not found.")
    row_d = dict(row) if not isinstance(row, dict) else row
    if not row_d.get("is_demo"):
        raise SystemExit(
            f"REFUSED: society sid={sid} ('{row_d.get('name')}') has "
            "is_demo=0. The wipe utility only operates on tenants "
            "explicitly marked as demo. Set is_demo=1 manually if you "
            "truly know what you're doing — but doing so also requires "
            "passing the sid!=1 hardcoded check."
        )


def wipe_society(sid: int, dry_run: bool = False) -> dict:
    """Cascade-delete every row owned by the given demo society. Refuses
    sid=1 unconditionally; refuses any non-is_demo=1 society."""
    init_db()
    summary = {"sid": sid, "dry_run": dry_run, "deleted": {}}
    with get_conn() as conn:
        _wipe_dual_guard(conn, sid)

        for table, where in _WIPE_ORDER:
            count_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", (sid,),
            ).fetchone()
            count = _scalar(count_row, "c")
            summary["deleted"][table] = count
            if not dry_run and count:
                conn.execute(f"DELETE FROM {table} WHERE {where}", (sid,))

        # Also wipe tester-account user rows scoped to this sid
        tester_count_row = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE society_id = ? "
            "AND role != 'admin'", (sid,),
        ).fetchone()
        summary["deleted"]["tester_users"] = _scalar(tester_count_row, "c")
        # Already covered by the users entry in _WIPE_ORDER above.

    return summary


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

def _format_summary(s: dict) -> str:
    if "sid" in s:
        lines = [f"sid={s['sid']} ({s.get('label','?')}):"]
        for k, v in s.items():
            if k in ("sid", "label"):
                continue
            lines.append(f"    {k}: {v}")
        return "\n".join(lines)
    return json.dumps(s, indent=2)


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sp_seed = sub.add_parser("seed", help="Seed demo data into all (or one) demo tenant")
    sp_seed.add_argument("--sid", type=int, default=None)
    sp_wipe = sub.add_parser("wipe", help="Wipe one demo tenant (refuses sid=1)")
    sp_wipe.add_argument("--sid", type=int, required=True)
    sp_wipe.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.cmd == "seed":
        password = os.getenv(TESTER_PASSWORD_ENV) or ""
        if not password:
            print(
                f"WARN: {TESTER_PASSWORD_ENV} not set — tester accounts "
                "will be skipped. Demo content (societies + people + "
                "complaints) will still seed."
            )
        init_db()
        if args.sid:
            summaries = [seed_society(args.sid)]
        else:
            summaries = seed_all(password)
        for s in summaries:
            print(_format_summary(s))
        return 0

    if args.cmd == "wipe":
        summary = wipe_society(args.sid, dry_run=args.dry_run)
        verb = "WOULD DELETE" if args.dry_run else "DELETED"
        print(f"{verb} from sid={summary['sid']}:")
        for t, c in summary["deleted"].items():
            print(f"    {t:30}  {c}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
