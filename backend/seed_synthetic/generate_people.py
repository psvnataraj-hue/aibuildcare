"""Synthetic-people generator for AIBuildCare demo tenants.

Reads Part 1 tenant configs + parking overlays from this directory, emits
deterministic per-society JSON files under ./people/. The seeder in Part 6
ingests those JSONs and inserts into the DB; nothing in this script
touches the DB directly.

Usage:
    python generate_people.py            # generate all 4 societies
    python generate_people.py --sid 100  # generate one society
    python generate_people.py --verify   # validate existing output only

Outputs:
    people/greenwood.json    (sid=100)
    people/sunrise.json      (sid=101)
    people/stellar.json      (sid=102)
    people/meridian.json     (sid=103)
    people/tester_accounts.json

## Design highlights

- Deterministic. random.Random is seeded per-society with a fixed string,
  so re-running the generator on a clean checkout produces identical
  output. Re-seeding never produces "different Sravya."

- Phone banding. All numbers are 10-digit Indian mobiles in the reserved
  +91 99000 XXXXX test-range block (Part 0-B). The 5-digit local part
  splits as {band}{4-digit-local}; banding by role lets an operator
  scanning the event log read TEST_PHONE_SKIPPED entries at a glance:

    +91 99000 0NNNN  user       (resident / ward staff / tenant employee / client)
    +91 99000 1NNNN  staff      (housekeeper / manager / nurse-supervisor / event runner)
    +91 99000 2NNNN  contractor primary contact
    +91 99000 3NNNN  vehicle owner (non-user — visitor / cab driver / courier)

  Within each band, society-offset blocks of 250 keep numbers globally
  unique (Greenwood 0000-0249, Sunrise 0250-0499, Stellar 0500-0749,
  Meridian 0750-0999).

  The 3-4 deterministic parking-overlay phones committed in Part 1
  (e.g. +919900000301) are in the test range but pre-date the banding
  scheme — the allocator reserves them so it doesn't collide, but they
  don't follow the band convention.

- Realistic spread. Contractor ratings drawn from a fixed band so each
  society has one low-rated outlier (3.2 — a poor performer the system
  flags during demos). Complaint-time spread (resolution times, status
  mix, ratings) is applied in Part 3, not here.

- Churn. Each config's churn_seeds drive the generation of deactivated
  staff (active=0, deactivated_at, deactivation_reason set, holding open
  complaints to be wired up in Part 3) and one retired contractor per
  society.

- Tester accounts. Two sravya.* accounts (resident + ops/secretary) on
  each of the 4 demo societies, plus nataraj.ops@ on each. All non-admin
  per the audit finding that admin role has cross-tenant reach.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from name_pools import (
    pick_name,
    pool_stats,
    FORBIDDEN_FULL_NAMES,
    FORBIDDEN_SURNAMES_FOR_LEADERSHIP,
)


HERE = Path(__file__).resolve().parent
PEOPLE_DIR = HERE / "people"

CONFIGS = {
    100: ("greenwood_residency.json",    "greenwood",   "parking_scenario_greenwood.json"),
    101: ("sunrise_nursing_home.json",   "sunrise",     None),
    102: ("stellar_events.json",         "stellar",     None),
    103: ("meridian_estate_office.json", "meridian",    "parking_scenario_meridian.json"),
}

# Society-offset block within each phone band (250 numbers per society)
SOCIETY_PHONE_OFFSET = {
    100:   0,
    101: 250,
    102: 500,
    103: 750,
}

# Realistic contractor-rating spread per society (10 contractors max).
# One low-rated outlier (3.2) per vertical to give demos a "system surfaces
# poor performers" story. Stable ordering: list[i] is used for the i-th
# contractor specialty in the config.
CONTRACTOR_RATING_SPREAD = [4.6, 4.4, 4.2, 4.2, 4.1, 4.0, 3.9, 3.8, 3.6, 3.2]

# Reference time used for created_at / deactivated_at timestamps.
# Anchored to today so the data ages naturally with the calendar.
NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────
# Phone allocator
# ─────────────────────────────────────────────────────────────────────────

class PhoneAllocator:
    """Hands out phones from the reserved +91 99000 XXXXX test range.

    Tracks used numbers across all bands so global uniqueness is
    guaranteed. The society offset keeps each tenant's pool to a
    contiguous 250-number block per role-band; if we ever exceed 250
    of any one type on one society, we raise rather than silently
    overflow into another society's block."""

    BAND_USER       = 0
    BAND_STAFF      = 1
    BAND_CONTRACTOR = 2
    BAND_VEHICLE    = 3

    def __init__(self) -> None:
        self._next_by_band_society: dict[tuple[int, int], int] = {}
        self._used: set[str] = set()

    def reserve(self, phone: str) -> None:
        """Mark an externally-specified phone (e.g., from a parking
        config's deterministic plate) as already used so we don't
        collide."""
        self._used.add(phone)

    def allocate(self, band: int, society_id: int) -> str:
        """Return a 10-digit Indian mobile in the reserved test range.

        Format: +91 99000 {band}{n:04d}
        - "+91" country code
        - "99000" 5-digit test-range prefix
        - {band} single-digit role indicator (0=user, 1=staff, 2=contractor, 3=vehicle)
        - {n:04d} 4-digit local index 0000-0999 (society offset baked in)

        Society-offset blocks (250 numbers each, contiguous within the
        4-digit local space):
          Greenwood 0000-0249, Sunrise 0250-0499,
          Stellar  0500-0749, Meridian 0750-0999
        """
        base = SOCIETY_PHONE_OFFSET[society_id]
        key = (band, society_id)
        i = self._next_by_band_society.get(key, 0)
        while True:
            n = base + i
            i += 1
            if i > 250:
                raise RuntimeError(
                    f"Phone band exhausted: band={band} society={society_id} "
                    f"used > 250 within society offset. Bump pool size or "
                    f"reallocate banding."
                )
            phone = f"+9199000{band}{n:04d}"
            if phone in self._used:
                continue
            self._used.add(phone)
            self._next_by_band_society[key] = i
            return phone


# ─────────────────────────────────────────────────────────────────────────
# Records (kept simple dicts — the seeder will map to DB rows)
# ─────────────────────────────────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _days_ago(d: int, hour: int = 9) -> str:
    return _iso(NOW.replace(hour=hour, minute=0, second=0) - timedelta(days=d))


def _make_user(
    sid: int, phone: str, full_name: str, role: str,
    unit_number: str | None, tenant_company: str | None,
    created_days_ago: int, active: int = 1,
) -> dict:
    return {
        "phone": phone,
        "full_name": full_name,
        "role": role,
        "society_id": sid,
        "unit_number": unit_number,
        "tenant_company": tenant_company,
        "active": active,
        "is_test_user": True,
        "created_at": _days_ago(created_days_ago),
    }


def _make_staff(
    sid: int, phone: str, full_name: str, role_key: str, title: str,
    category_specialty: str | None, in_chain: bool, chain_level: int | None,
    created_days_ago: int, active: int,
    deactivated_at: str | None, deactivation_reason: str | None,
) -> dict:
    return {
        "phone": phone,
        "full_name": full_name,
        "role_key": role_key,
        "title": title,
        "society_id": sid,
        "category_specialty": category_specialty,
        "in_chain": in_chain,
        "chain_level": chain_level,
        "active": active,
        "deactivated_at": deactivated_at,
        "deactivation_reason": deactivation_reason,
        "phone_whatsapp_enabled": True if active else False,
        "is_test_user": True,
        "created_at": _days_ago(created_days_ago),
    }


def _make_contractor(
    sid: int, phone: str, vendor_name: str, primary_contact_name: str,
    category: str, rating: float,
    created_days_ago: int, is_active: int,
    retired_at: str | None, retirement_reason: str | None,
) -> dict:
    return {
        "phone": phone,
        "vendor_name": vendor_name,
        "primary_contact_name": primary_contact_name,
        "category": category,
        "rating": rating,
        "society_id": sid,
        "is_active": is_active,
        "retired_at": retired_at,
        "retirement_reason": retirement_reason,
        "is_test_vendor": True,
        "created_at": _days_ago(created_days_ago),
    }


def _make_vehicle(
    sid: int, plate: str, owner_name: str, owner_phone: str,
    owner_unit: str, owner_tenant_company: str | None,
    vehicle_type: str, slot: str | None,
    registered_days_ago: int, active: int = 1,
    clamped: int = 0,
) -> dict:
    return {
        "plate": plate,
        "owner_name": owner_name,
        "owner_phone": owner_phone,
        "owner_unit": owner_unit,
        "owner_tenant_company": owner_tenant_company,
        "vehicle_type": vehicle_type,
        "slot": slot,
        "society_id": sid,
        "active": active,
        "clamped": clamped,
        "is_test_vehicle": True,
        "registered_at": _days_ago(registered_days_ago),
    }


# ─────────────────────────────────────────────────────────────────────────
# Vertical-specific unit / user generation
# ─────────────────────────────────────────────────────────────────────────

def _greenwood_units(config: dict) -> list[str]:
    """Tower A/B/C/D × floor 1-12 × unit A/B/C/D. Sample 50."""
    units = [
        f"{t['id']}-{floor}{letter}"
        for t in config["structure"]["towers"]
        for floor in range(1, t["floors"] + 1)
        for letter in ["A", "B", "C", "D"][: t["units_per_floor"]]
    ]
    return units  # full list; sampler picks 50


def _sunrise_units(config: dict) -> list[str]:
    """Wings × floors × departments × rooms × beds. Build all routing keys."""
    out: list[str] = []
    dept_short = {
        "General Ward": "GW", "Private Wards": "PR", "Maternity Ward": "MW",
        "Paediatric Ward": "PD", "Emergency": "EM", "ICU": "ICU",
        "NICU": "NICU", "OT": "OT", "Reception": "REC", "Pharmacy": "PHARM",
        "Lab": "LAB", "X-ray": "XRAY", "MRI": "MRI", "CT": "CT",
        "Admin Office": "ADMIN",
    }
    for wing in config["structure"]["wings"]:
        wid = wing["id"]
        for fl in wing["floors"]:
            ds = dept_short.get(fl["department"], fl["department"][:5].upper())
            rooms = fl["rooms"]
            beds = fl["beds_per_room"]
            for r in range(1, rooms + 1):
                room_num = f"{fl['floor']}{r:02d}"  # "101", "102", ...
                if beds == 0:
                    out.append(f"{wid}-{ds}-{room_num}" if r > 1 else f"{wid}-{ds}")
                else:
                    for b in range(1, beds + 1):
                        out.append(f"{wid}-{ds}-{room_num}-B{b}")
    return out


def _stellar_units(config: dict) -> list[str]:
    return [ev["event_id"] for ev in config["structure"]["active_events"]]


def _meridian_units(config: dict) -> list[str]:
    out = []
    for b in config["structure"]["buildings"]:
        for fl in range(1, b["floors"] + 1):
            for s in range(1, b["suites_per_floor"] + 1):
                out.append(f"{b['id']}-F{fl:02d}-S{s:02d}")
    return out


UNIT_BUILDERS = {
    100: _greenwood_units,
    101: _sunrise_units,
    102: _stellar_units,
    103: _meridian_units,
}

# Number of "user" (filer) records per society
USER_COUNTS = {100: 50, 101: 30, 102: 15, 103: 50}

# How user.role is set per vertical (the existing schema accepts any
# string; the actual permission resolution happens via rbac.ROLE_PERMISSIONS)
USER_ROLE_BY_SOCIETY = {
    100: "resident",         # housing
    101: "staff",            # ward staff filing on infrastructure
    102: "resident",         # client contacts (no event-specific role exists)
    103: "resident",         # tenant employees (closest role we have)
}

# Fictitious tenant companies for Meridian (used as units.owner_name +
# tenant_company on Meridian users)
MERIDIAN_TENANT_COMPANIES = [
    "Stratus Analytics Pvt Ltd",
    "Northwind Logistics LLP",
    "ByteStream Software India",
    "Lighthouse Consulting Group",
    "Verdant Renewables Pvt Ltd",
    "Acorn Legal Advisors",
    "Pinnacle Architecture Studio",
    "MediQuant Diagnostics",
    "Trellis Marketing Solutions",
    "Crescent Capital Advisors",
    "Aspire EduTech Pvt Ltd",
    "Mosaic Design Collective",
    "Beacon HR Solutions",
    "Cobalt Trading Co",
    "Saffron Foods Procurement LLP",
]


# ─────────────────────────────────────────────────────────────────────────
# Per-society generation
# ─────────────────────────────────────────────────────────────────────────

def generate_society(
    config: dict,
    parking: dict | None,
    sid: int,
    allocator: PhoneAllocator,
    rng: random.Random,
) -> dict:
    # Build unit list
    units = UNIT_BUILDERS[sid](config)
    target_user_count = USER_COUNTS[sid]
    # Sample units for occupancy. When the pool is smaller than the
    # target count (Stellar — 5 events, 15 client contacts), allow
    # multiple users per unit by oversampling with replacement; otherwise
    # sample without replacement so each unit has at most one occupant.
    if target_user_count <= len(units):
        occupied_units = rng.sample(units, target_user_count)
    else:
        # Each unit gets at least one user, then extras are drawn with
        # replacement so the smaller pool still hits the target count.
        occupied_units = list(units)
        extras_needed = target_user_count - len(units)
        occupied_units.extend(rng.choices(units, k=extras_needed))

    # ── Users ─────────────────────────────────────────────────────────
    users: list[dict] = []
    user_role = USER_ROLE_BY_SOCIETY[sid]
    if sid == 103:
        # Meridian: each suite occupied by one tenant company; users are
        # employees thereof. Assign tenant companies round-robin across
        # occupied suites so several suites share a company (anchor tenants).
        company_by_unit: dict[str, str] = {}
        for i, u in enumerate(occupied_units):
            company_by_unit[u] = MERIDIAN_TENANT_COMPANIES[
                i % len(MERIDIAN_TENANT_COMPANIES)
            ]
    for u in occupied_units:
        gender = rng.choice(["M", "F"])
        _, _, full_name, _ = pick_name(rng, sid, gender=gender)
        phone = allocator.allocate(PhoneAllocator.BAND_USER, sid)
        tenant_co = company_by_unit.get(u) if sid == 103 else None
        users.append(_make_user(
            sid, phone, full_name, user_role, u, tenant_co,
            created_days_ago=rng.randint(60, 540),  # users joined 2-18 months ago
        ))

    # ── Staff (active) ────────────────────────────────────────────────
    staff: list[dict] = []
    for role in config["staff_roles"]:
        for i in range(role["count"]):
            # Leadership roles (in_chain or top-of-chain) get name-screened
            is_leader = bool(role.get("in_chain")) and role.get("chain_level", 0) >= 2
            _, _, full_name, _ = pick_name(rng, sid, is_leadership=is_leader)
            phone = allocator.allocate(PhoneAllocator.BAND_STAFF, sid)
            staff.append(_make_staff(
                sid, phone, full_name,
                role_key=role["role_key"],
                title=role["title"],
                category_specialty=role.get("category_specialty"),
                in_chain=bool(role.get("in_chain")),
                chain_level=role.get("chain_level"),
                created_days_ago=rng.randint(180, 900),
                active=1,
                deactivated_at=None,
                deactivation_reason=None,
            ))

    # ── Staff (deactivated, churn_seeds) ─────────────────────────────
    churn = config.get("churn_seeds", {})
    for d in churn.get("deactivated_staff", []):
        role_key = d["role_key"]
        # Find the role config to get the title
        role_cfg = next(
            (r for r in config["staff_roles"] if r["role_key"] == role_key),
            {"title": role_key, "in_chain": False, "chain_level": None,
             "category_specialty": None},
        )
        _, _, full_name, _ = pick_name(rng, sid)
        phone = allocator.allocate(PhoneAllocator.BAND_STAFF, sid)
        # deactivation_reason from config contains a date — parse out for
        # the deactivated_at, fall back to 45 days ago
        reason_text = d.get("reason", "")
        deact_days_ago = _extract_days_from_reason(reason_text, default_days_ago=45)
        staff.append(_make_staff(
            sid, phone, full_name,
            role_key=role_key,
            title=role_cfg["title"],
            category_specialty=role_cfg.get("category_specialty"),
            in_chain=bool(role_cfg.get("in_chain")),
            chain_level=role_cfg.get("chain_level"),
            created_days_ago=rng.randint(360, 1200),  # they were here longer
            active=0,
            deactivated_at=_days_ago(deact_days_ago, hour=17),
            deactivation_reason=reason_text,
        ))
        # Embed churn metadata for Part 3 to wire up open complaints
        staff[-1]["__churn_meta__"] = {
            "holds_open_complaints_at_deactivation": d.get(
                "holds_open_complaints_at_deactivation", 0
            ),
            "highest_open_priority": d.get("highest_open_priority", "normal"),
            "highest_escalation_level_at_deactivation": d.get(
                "highest_escalation_level_at_deactivation", 0
            ),
        }

    # ── Contractors (active) ──────────────────────────────────────────
    contractors: list[dict] = []
    for i, spec in enumerate(config["contractor_specialties"]):
        _, _, contact_name, _ = pick_name(rng, sid)
        phone = allocator.allocate(PhoneAllocator.BAND_CONTRACTOR, sid)
        rating = CONTRACTOR_RATING_SPREAD[
            i % len(CONTRACTOR_RATING_SPREAD)
        ]
        contractors.append(_make_contractor(
            sid, phone, spec["vendor_name"], contact_name,
            category=spec["category"], rating=rating,
            created_days_ago=rng.randint(180, 720),
            is_active=1, retired_at=None, retirement_reason=None,
        ))

    # ── Contractor (retired, churn_seeds) ─────────────────────────────
    rc = churn.get("retired_contractor")
    if rc:
        _, _, contact_name, _ = pick_name(rng, sid)
        phone = allocator.allocate(PhoneAllocator.BAND_CONTRACTOR, sid)
        rd = _extract_days_from_reason(rc.get("reason", ""), default_days_ago=30)
        contractors.append(_make_contractor(
            sid, phone, rc["vendor_name"], contact_name,
            category=rc["category"],
            rating=3.2,  # the deliberately-poor performer
            created_days_ago=rng.randint(540, 1200),
            is_active=0,
            retired_at=_days_ago(rd, hour=17),
            retirement_reason=rc.get("reason", ""),
        ))
        contractors[-1]["__churn_meta__"] = {
            "holds_open_jobs_at_retirement": rc.get(
                "holds_open_jobs_at_retirement", 0
            ),
            "highest_open_priority": rc.get("highest_open_priority", "normal"),
        }

    # ── Vehicles (parking overlay) ────────────────────────────────────
    vehicles: list[dict] = []
    if parking:
        # 1. Reserve the deterministic repeat-offender phones so we don't
        #    collide on them
        for d in parking["deterministic_repeat_offender_plates"]["plates"]:
            allocator.reserve(d["owner_phone"])
        # 2. Generated regular vehicles (~50-80 per society)
        veh_target = parking["registered_vehicles_to_seed"]["total_vehicles"]
        veh_types = parking["registered_vehicles_to_seed"]["by_type"]
        # Build list of vehicle types in the right proportions
        type_pool: list[str] = []
        for vt, n in veh_types.items():
            type_pool.extend([vt] * n)
        rng.shuffle(type_pool)
        # Vehicles owned by occupied units
        for i, vt in enumerate(type_pool):
            # Assign vehicle to a unit owner
            owner = rng.choice(users) if users else None
            if owner is None:
                continue
            plate = _generate_plate(rng, sid, used_plates={v["plate"] for v in vehicles})
            slot = _assign_slot(rng, sid, i, vt)
            vehicles.append(_make_vehicle(
                sid, plate,
                owner_name=owner["full_name"],
                owner_phone=owner["phone"],
                owner_unit=owner["unit_number"],
                owner_tenant_company=owner.get("tenant_company"),
                vehicle_type=vt, slot=slot,
                registered_days_ago=rng.randint(30, 720),
                active=1,
            ))
        # 3. Add the deterministic repeat-offender plates verbatim
        for d in parking["deterministic_repeat_offender_plates"]["plates"]:
            # Try to find a name matching the owner_unit; fall back to
            # a fresh-picked name (works for VISITOR / CAB-DRIVER cases)
            owner_user = next(
                (u for u in users if u["unit_number"] == d.get("owner_unit")),
                None,
            )
            if owner_user:
                owner_name = owner_user["full_name"]
            else:
                _, _, owner_name, _ = pick_name(rng, sid)
            vehicles.append(_make_vehicle(
                sid, d["plate"],
                owner_name=owner_name,
                owner_phone=d["owner_phone"],
                owner_unit=d.get("owner_unit", "VISITOR"),
                owner_tenant_company=d.get("owner_tenant_company"),
                vehicle_type=d["vehicle_type"],
                slot=None,
                registered_days_ago=rng.randint(90, 720),
                active=1,
                clamped=1 if any(
                    v.get("clamping_authorized") for v in d.get("violations_seeded", [])
                ) else 0,
            ))
            # Stamp the deterministic plates for Part 3 to wire violations
            vehicles[-1]["__seeded_violations__"] = d.get("violations_seeded", [])
            vehicles[-1]["__is_deterministic__"] = True

    return {
        "sid": sid,
        "society": config["society"],
        "vertical": config["_meta"]["vertical"],
        "users": users,
        "staff_members": staff,
        "contractors": contractors,
        "vehicles": vehicles,
    }


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _extract_days_from_reason(reason: str, default_days_ago: int) -> int:
    """Pull a 'days ago' integer from a reason string with an embedded
    ISO date like '2026-04-22'. Falls back to default if not parseable."""
    import re
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", reason)
    if not m:
        return default_days_ago
    try:
        ts = datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
        return max(1, (NOW - ts).days)
    except Exception:
        return default_days_ago


_PLATE_STATE_BY_SID = {
    100: "MH", 101: "MH", 102: "MH", 103: "WB",
}
_PLATE_DISTRICT_BY_SID = {
    100: 12,  # Pune (MH-12)
    101:  2,  # Mumbai (MH-02)
    102:  2,  # Mumbai (MH-02)
    103:  2,  # Kolkata (WB-02)
}
_PLATE_LETTERS_POOL = "ABCDEFGHJKLMNPQRSTUVWXY"  # no I/O/Z (Z used for forbidden)


def _generate_plate(
    rng: random.Random, sid: int, used_plates: set[str],
) -> str:
    state = _PLATE_STATE_BY_SID[sid]
    district = f"{_PLATE_DISTRICT_BY_SID[sid]:02d}"
    for _ in range(100):
        ll = rng.choice(_PLATE_LETTERS_POOL) + rng.choice(_PLATE_LETTERS_POOL)
        nnnn = f"{rng.randint(1000, 9999)}"
        plate = f"{state}-{district}-{ll}-{nnnn}"
        if plate not in used_plates:
            return plate
    raise RuntimeError("Plate generation exhausted")


def _assign_slot(rng: random.Random, sid: int, i: int, vt: str) -> str | None:
    if sid == 100:
        # Greenwood: alternating Basement A / B
        bank = "A" if i % 2 == 0 else "B"
        n = (i // 2) + 1
        return f"Basement-{bank}-{n:03d}"
    if sid == 103:
        # Meridian: alternating B1 / B2 tower basements
        bank = "A" if i % 2 == 0 else "B"
        tower_prefix = "B1-A" if bank == "A" else "B2-B"
        n = (i // 2) + 1
        return f"{tower_prefix}-{n:03d}"
    return None


# ─────────────────────────────────────────────────────────────────────────
# Tester accounts
# ─────────────────────────────────────────────────────────────────────────

def _tester_accounts(societies: list[dict]) -> dict:
    """Build the tester_accounts.json structure.

    Per the audit finding, NO admin role is used on demo tenants — admin
    has cross-tenant reach. All tester accounts are non-admin and
    society-scoped.

    Three personas:
      sravya.resident@aibuildcare.app  on each demo society as role=resident
      sravya.ops@aibuildcare.app       on each demo society as role=secretary
      nataraj.ops@aibuildcare.app      on each demo society as role=secretary

    Sravya gets a "resident" account anchored to a real seeded unit on
    each tenant so she can file complaints as an end-user. Sravya's "ops"
    and Nataraj's "ops" accounts both use role=secretary, which carries
    the _LEADER permission set (file/view/assign/resolve/escalate/
    authorize_enforcement + modify_config + approve_reports + view_financial).
    Per rbac.py:50, secretary respects society_id in queries — verified
    by audit.

    Password handling: the seeder (Part 6) reads AIBUILDCARE_TESTER_PASSWORD
    from env, bcrypts it, and inserts. No plaintext passwords in the repo.
    Same password used for all tester accounts for ease of demo use.
    """
    accounts: list[dict] = []
    society_meta = {s["sid"]: s["society"]["name"] for s in societies}

    # Sravya — resident on each demo tenant
    for s in societies:
        sid = s["sid"]
        # Pick a real seeded unit for her resident account so the
        # dashboard renders her as a "real" filer with an address.
        if s["users"]:
            anchor_unit = s["users"][0]["unit_number"]
        else:
            anchor_unit = None
        accounts.append({
            "email":           "sravya.resident@aibuildcare.app",
            "society_id":      sid,
            "society_name":    society_meta[sid],
            "role":            "resident",
            "purpose":         "TESTER — files complaints from end-user perspective",
            "unit_number":     anchor_unit,
            "phone":           "+919900000001",  # outside generator-allocated range
            "active":          1,
            "is_test_account": True,
        })

    # Sravya — ops (secretary) on each demo tenant
    for s in societies:
        sid = s["sid"]
        accounts.append({
            "email":           "sravya.ops@aibuildcare.app",
            "society_id":      sid,
            "society_name":    society_meta[sid],
            "role":            "secretary",
            "purpose":         "TESTER — operator view; can assign, resolve, escalate, authorize enforcement",
            "unit_number":     None,
            "phone":           "+919900000002",
            "active":          1,
            "is_test_account": True,
        })

    # Nataraj — ops (secretary) on each demo tenant
    for s in societies:
        sid = s["sid"]
        accounts.append({
            "email":           "nataraj.ops@aibuildcare.app",
            "society_id":      sid,
            "society_name":    society_meta[sid],
            "role":            "secretary",
            "purpose":         "OPERATOR — Nataraj per-demo login (NOT the Palms admin); scoped to this demo tenant only",
            "unit_number":     None,
            "phone":           "+919900000003",
            "active":          1,
            "is_test_account": True,
        })

    return {
        "_meta": {
            "description":
                "Tester + operator accounts for demo tenants. NO admin role "
                "used on demos per audit finding (admin has cross-tenant "
                "reach via /analytics, /contractors, /admin/permissions). "
                "All accounts use society-scoped non-admin roles.",
            "password_env_var": "AIBUILDCARE_TESTER_PASSWORD",
            "password_handling":
                "Seeder Part 6 reads the env var at apply time, bcrypts it, "
                "and inserts. Same password reused across all tester "
                "accounts for demo simplicity.",
            "out_of_scope_by_design":
                "Sravya never gets an account on sid=1 (Palms). Nataraj's "
                "real Palms admin account is unchanged by this seeding.",
        },
        "accounts": accounts,
    }


# ─────────────────────────────────────────────────────────────────────────
# Drive
# ─────────────────────────────────────────────────────────────────────────

def generate_all(only_sid: int | None = None) -> dict[str, dict]:
    """Generate every demo society (or just one) and the tester accounts.

    Returns a dict of output-filename → payload so the caller can write
    to disk after we've verified everything cross-references correctly."""
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    allocator = PhoneAllocator()
    # Reserve the manual tester phones so generator never collides
    for p in ("+919900000001", "+919900000002", "+919900000003"):
        allocator.reserve(p)

    payloads: dict[str, dict] = {}
    societies: list[dict] = []
    for sid, (config_filename, label, parking_filename) in CONFIGS.items():
        if only_sid and sid != only_sid:
            continue
        config = json.loads((HERE / config_filename).read_text(encoding="utf-8"))
        parking = (
            json.loads((HERE / parking_filename).read_text(encoding="utf-8"))
            if parking_filename
            else None
        )
        rng = random.Random(f"aibuildcare-{sid}-v1")
        soc = generate_society(config, parking, sid, allocator, rng)
        payloads[f"{label}.json"] = soc
        societies.append(soc)

    # Tester accounts (only generated when we did the full sweep — they
    # need all societies' info)
    if only_sid is None:
        payloads["tester_accounts.json"] = _tester_accounts(societies)

    return payloads


def write_payloads(payloads: dict[str, dict]) -> None:
    for filename, data in payloads.items():
        path = PEOPLE_DIR / filename
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


# ─────────────────────────────────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────────────────────────────────

def verify(payloads: dict[str, dict]) -> tuple[bool, list[str]]:
    """Sanity-check the generated payloads.

    Catches: phone collisions, churn count mismatches, names hitting the
    forbidden list, unit numbers referenced that don't exist in config,
    contractor rating outside [0,5]. Returns (ok, issues)."""
    issues: list[str] = []
    seen_phones: dict[str, str] = {}

    societies = [v for k, v in payloads.items() if k != "tester_accounts.json"]

    for soc in societies:
        sid = soc["sid"]
        # Phones
        for kind in ("users", "staff_members", "contractors"):
            for r in soc[kind]:
                ph = r["phone"]
                if not ph.startswith("+9199000"):
                    issues.append(
                        f"[sid={sid}] {kind} phone outside test range: {ph} "
                        f"({r.get('full_name') or r.get('vendor_name')})"
                    )
                if ph in seen_phones:
                    issues.append(
                        f"[sid={sid}] phone collision: {ph} used by "
                        f"{seen_phones[ph]} and now {kind}/{r.get('full_name') or r.get('vendor_name')}"
                    )
                else:
                    seen_phones[ph] = f"sid={sid}/{kind}/{r.get('full_name') or r.get('vendor_name')}"
        # Names not forbidden
        for r in soc["users"] + soc["staff_members"]:
            name = r["full_name"]
            parts = name.split()
            if len(parts) >= 2 and (parts[0], parts[-1]) in FORBIDDEN_FULL_NAMES:
                issues.append(
                    f"[sid={sid}] FORBIDDEN_FULL_NAME hit: {name}"
                )
        # Leadership surname screening
        for r in soc["staff_members"]:
            if r.get("in_chain") and (r.get("chain_level") or 0) >= 2:
                last = r["full_name"].split()[-1]
                if last in FORBIDDEN_SURNAMES_FOR_LEADERSHIP:
                    issues.append(
                        f"[sid={sid}] leadership-forbidden surname: {r['full_name']} "
                        f"({r['role_key']}, chain_level={r['chain_level']})"
                    )
        # Contractor ratings
        for c in soc["contractors"]:
            if not (0 <= c["rating"] <= 5):
                issues.append(
                    f"[sid={sid}] contractor rating out of range: "
                    f"{c['vendor_name']} = {c['rating']}"
                )
        # Vehicle owner phones in test range
        for v in soc["vehicles"]:
            if not v["owner_phone"].startswith("+9199000"):
                issues.append(
                    f"[sid={sid}] vehicle owner phone outside test range: "
                    f"{v['plate']} → {v['owner_phone']}"
                )

    return (len(issues) == 0, issues)


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

def _summary_line(soc: dict) -> str:
    sid = soc["sid"]
    name = soc["society"]["name"]
    return (
        f"  sid={sid} {name}: "
        f"users={len(soc['users'])} "
        f"staff_active={sum(1 for s in soc['staff_members'] if s['active']==1)} "
        f"staff_deactivated={sum(1 for s in soc['staff_members'] if s['active']==0)} "
        f"contractors_active={sum(1 for c in soc['contractors'] if c['is_active']==1)} "
        f"contractors_retired={sum(1 for c in soc['contractors'] if c['is_active']==0)} "
        f"vehicles={len(soc['vehicles'])}"
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sid", type=int, default=None,
                   help="Generate only this society (100/101/102/103)")
    p.add_argument("--verify", action="store_true",
                   help="Generate but don't write; verify only")
    args = p.parse_args()

    print(f"name pool stats: {pool_stats()}")
    payloads = generate_all(only_sid=args.sid)

    print("\nGenerated:")
    for filename, data in payloads.items():
        if filename == "tester_accounts.json":
            print(f"  {filename}: {len(data['accounts'])} accounts")
        else:
            print(_summary_line(data))

    ok, issues = verify({k: v for k, v in payloads.items()
                         if k != "tester_accounts.json"})
    print(f"\nverification: {'OK' if ok else 'FAIL'}")
    for i in issues:
        print(f"  - {i}")
    if not ok:
        return 1

    if not args.verify:
        write_payloads(payloads)
        print(f"\nWrote to {PEOPLE_DIR}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
