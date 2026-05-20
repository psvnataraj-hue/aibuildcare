"""E3a: society-scoped CRUD over staff_members + staff_categories.

Mutations require RBAC permission MODIFY_STAFF (manager / sr_manager /
secretary / chairman + admin by default). Society scope is enforced
on every query — a society's manager cannot read or mutate another
society's staff.

Categories are M:N: each staff member can handle any subset of the
24 enumerated complaint categories (services/haiku_parser.CATEGORIES),
with a `primary_category` boolean per row + a `skill_level` enum
(junior/senior/expert). Routing service already consumes this.
"""
from __future__ import annotations

from ..db import get_conn
from .complaint_service import ComplaintError
from .haiku_parser import CATEGORIES as _VALID_CATEGORIES

_VALID_SKILL_LEVELS = frozenset({"junior", "senior", "expert"})


def _validate_category(category: str) -> None:
    if category not in _VALID_CATEGORIES:
        raise ComplaintError(
            f"unknown category: {category!r} "
            f"(must be one of the 24 system categories)"
        )


def _validate_skill(skill: str) -> None:
    if skill not in _VALID_SKILL_LEVELS:
        raise ComplaintError(
            f"skill_level must be one of {sorted(_VALID_SKILL_LEVELS)}"
        )


def _categories_for_staff(conn, staff_id: int) -> list[dict]:
    return [
        dict(r) for r in conn.execute(
            "SELECT category, primary_category, skill_level "
            "FROM staff_categories WHERE staff_id = ? "
            "ORDER BY primary_category DESC, category",
            (staff_id,),
        ).fetchall()
    ]


def _shape(row: dict, categories: list[dict]) -> dict:
    """Cast booleans + attach categories."""
    out = dict(row)
    out["whatsapp_enabled"] = bool(out.get("whatsapp_enabled"))
    out["sms_fallback"] = bool(out.get("sms_fallback"))
    out["active"] = bool(out.get("active"))
    out["categories"] = [
        {
            "category": c["category"],
            "primary_category": bool(c["primary_category"]),
            "skill_level": c["skill_level"],
        }
        for c in categories
    ]
    return out


# --- reads -----------------------------------------------------------
def list_staff(
    society_id: int, include_inactive: bool = False
) -> list[dict]:
    with get_conn() as conn:
        sql = (
            "SELECT * FROM staff_members WHERE society_id = ?"
            + ("" if include_inactive else " AND active = 1")
            + " ORDER BY name"
        )
        rows = [dict(r) for r in conn.execute(sql, (society_id,)).fetchall()]
        return [_shape(r, _categories_for_staff(conn, r["id"])) for r in rows]


def get_staff(staff_id: int, society_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM staff_members "
            "WHERE id = ? AND society_id = ?",
            (staff_id, society_id),
        ).fetchone()
        if not row:
            raise ComplaintError("staff not found")
        return _shape(dict(row), _categories_for_staff(conn, staff_id))


# --- create ----------------------------------------------------------
def create_staff(
    society_id: int,
    name: str,
    phone_primary: str,
    phone_secondary: str | None = None,
    whatsapp_enabled: bool = True,
    sms_fallback: bool = True,
    email: str | None = None,
    shift_pattern: str | None = None,
    hire_date: str | None = None,
    emergency_contact: str | None = None,
    notes: str | None = None,
    categories: list[dict] | None = None,
) -> dict:
    if not name or not name.strip():
        raise ComplaintError("name is required")
    if not phone_primary or not phone_primary.strip():
        raise ComplaintError("phone_primary is required")
    categories = categories or []
    for c in categories:
        _validate_category(c.get("category", ""))
        _validate_skill(c.get("skill_level", "junior"))
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO staff_members (society_id, name, phone_primary, "
            "phone_secondary, whatsapp_enabled, sms_fallback, email, "
            "shift_pattern, active, hire_date, emergency_contact, notes) "
            "VALUES (?,?,?,?,?,?,?,?,1,?,?,?)",
            (society_id, name, phone_primary, phone_secondary,
             1 if whatsapp_enabled else 0, 1 if sms_fallback else 0,
             email, shift_pattern, hire_date, emergency_contact, notes),
        )
        sid = cur.lastrowid
        for c in categories:
            conn.execute(
                "INSERT INTO staff_categories "
                "(staff_id, category, primary_category, skill_level) "
                "VALUES (?,?,?,?)",
                (sid, c["category"],
                 1 if c.get("primary_category") else 0,
                 c.get("skill_level", "junior")),
            )
        out = conn.execute(
            "SELECT * FROM staff_members WHERE id = ?", (sid,)
        ).fetchone()
        return _shape(dict(out), _categories_for_staff(conn, sid))


# --- update ----------------------------------------------------------
_PATCHABLE = frozenset({
    "name", "phone_primary", "phone_secondary",
    "whatsapp_enabled", "sms_fallback", "email", "shift_pattern",
    "hire_date", "emergency_contact", "notes", "active",
})


def update_staff(staff_id: int, society_id: int, **fields) -> dict:
    if not fields:
        raise ComplaintError("no fields to update")
    bad = set(fields) - _PATCHABLE
    if bad:
        raise ComplaintError(f"unknown field(s): {sorted(bad)}")
    sets, params = [], []
    bool_cols = ("whatsapp_enabled", "sms_fallback", "active")
    for k, v in fields.items():
        sets.append(f"{k} = ?")  # whitelisted via _PATCHABLE
        if k in bool_cols:
            params.append(1 if v else 0)
        else:
            params.append(v)
    params.extend([staff_id, society_id])
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE staff_members SET {', '.join(sets)} "
            "WHERE id = ? AND society_id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise ComplaintError("staff not found")
        out = conn.execute(
            "SELECT * FROM staff_members WHERE id = ?", (staff_id,)
        ).fetchone()
        return _shape(dict(out), _categories_for_staff(conn, staff_id))


# --- deactivate (soft delete) ---------------------------------------
def deactivate_staff(staff_id: int, society_id: int) -> dict:
    return update_staff(staff_id, society_id, active=False)


# --- category subresource -------------------------------------------
def add_category(
    staff_id: int, society_id: int, category: str,
    primary_category: bool = False, skill_level: str = "junior",
) -> dict:
    _validate_category(category)
    _validate_skill(skill_level)
    with get_conn() as conn:
        owns = conn.execute(
            "SELECT 1 FROM staff_members "
            "WHERE id = ? AND society_id = ?",
            (staff_id, society_id),
        ).fetchone()
        if not owns:
            raise ComplaintError("staff not found")
        # upsert via DELETE-then-INSERT (UNIQUE(staff_id,category))
        conn.execute(
            "DELETE FROM staff_categories "
            "WHERE staff_id = ? AND category = ?",
            (staff_id, category),
        )
        conn.execute(
            "INSERT INTO staff_categories "
            "(staff_id, category, primary_category, skill_level) "
            "VALUES (?,?,?,?)",
            (staff_id, category,
             1 if primary_category else 0, skill_level),
        )
    return get_staff(staff_id, society_id)


def remove_category(
    staff_id: int, society_id: int, category: str
) -> dict:
    with get_conn() as conn:
        owns = conn.execute(
            "SELECT 1 FROM staff_members "
            "WHERE id = ? AND society_id = ?",
            (staff_id, society_id),
        ).fetchone()
        if not owns:
            raise ComplaintError("staff not found")
        conn.execute(
            "DELETE FROM staff_categories "
            "WHERE staff_id = ? AND category = ?",
            (staff_id, category),
        )
    return get_staff(staff_id, society_id)
