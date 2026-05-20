"""Manual escalation (E1c).

Auto-cron escalation is E2. This module handles:
  - the manual `escalate` action (one-level-at-a-time, society-scoped),
  - CRUD over the per-society escalation_hierarchy.

Level → column mapping (schema-locked):
  1: manager     -> escalated_to_manager_at
  2: sr_manager  -> escalated_to_sr_manager_at
  3: secretary   -> escalated_to_secretary_at
  4: chairman    -> escalated_to_chairman_at

A society's `escalation_hierarchy` table holds one row per level
(role_name + person_name + phone + whatsapp_enabled), enabling
notification on escalation without hard-coding people.
"""
from __future__ import annotations

from ..db import get_conn
from .complaint_service import (
    ComplaintError,
    _now,
    _row_to_dict,
    _sid,
)


_LEVEL_TO_ROLE = {1: "manager", 2: "sr_manager",
                  3: "secretary", 4: "chairman"}
_LEVEL_TO_COLUMN = {
    1: "escalated_to_manager_at",
    2: "escalated_to_sr_manager_at",
    3: "escalated_to_secretary_at",
    4: "escalated_to_chairman_at",
}
_VALID_ROLES = frozenset(_LEVEL_TO_ROLE.values())
_MAX_LEVEL = max(_LEVEL_TO_ROLE)


# --- read --------------------------------------------------------------
def _current_level(complaint: dict) -> int:
    """0 if never escalated; otherwise the highest level reached."""
    for lvl in range(_MAX_LEVEL, 0, -1):
        if complaint.get(_LEVEL_TO_COLUMN[lvl]):
            return lvl
    return 0


def _hierarchy_row(conn, society_id: int, level: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM escalation_hierarchy "
        "WHERE society_id = ? AND escalation_level = ? "
        "AND active = 1 ORDER BY id LIMIT 1",
        (society_id, level),
    ).fetchone()
    return dict(row) if row else None


# --- the action --------------------------------------------------------
def escalate(complaint_id: int, society_id: int) -> dict:
    """Bump the complaint to the next escalation level. Returns the
    updated complaint dict with `escalated_level`/`escalated_role`/
    `notified_person` keys appended. Raises ComplaintError on missing
    complaint, missing hierarchy entry, or already-at-max."""
    with get_conn() as conn:
        sid = _sid(conn, society_id)
        row = conn.execute(
            "SELECT * FROM complaints WHERE id = ? AND society_id = ?",
            (complaint_id, sid),
        ).fetchone()
        if not row:
            raise ComplaintError("complaint not found")
        c = dict(row)
        cur = _current_level(c)
        if cur >= _MAX_LEVEL:
            raise ComplaintError(
                f"already escalated to level {cur} (max)"
            )
        next_lvl = cur + 1
        role_name = _LEVEL_TO_ROLE[next_lvl]
        col = _LEVEL_TO_COLUMN[next_lvl]
        person = _hierarchy_row(conn, sid, next_lvl)
        if not person:
            raise ComplaintError(
                f"no active escalation contact at level {next_lvl} "
                f"({role_name}) for this society"
            )
        ts = _now()
        # whitelisted column name (not user input) — same pattern as
        # the audited ORDER BY whitelist in list_complaints
        conn.execute(
            f"UPDATE complaints SET {col} = ?, updated_at = ? "
            "WHERE id = ?",
            (ts, ts, complaint_id),
        )
        conn.execute(
            "INSERT INTO complaint_status_history "
            "(complaint_id, from_status, to_status, changed_by) "
            "VALUES (?,?,?,?)",
            (complaint_id, c.get("status"), c.get("status"),
             f"escalated->{role_name}"),
        )
        conn.execute(
            "INSERT INTO complaint_messages (complaint_id, sender, body) "
            "VALUES (?,?,?)",
            (complaint_id, "system",
             f"Escalated to level {next_lvl} ({role_name}: "
             f"{person['person_name']})."),
        )
        out = conn.execute(
            "SELECT * FROM complaints WHERE id = ?", (complaint_id,)
        ).fetchone()
        result = _row_to_dict(out)
    # notification AFTER tx commit (graceful if Twilio absent)
    result["escalated_level"] = next_lvl
    result["escalated_role"] = role_name
    result["notified_person"] = {
        "name": person["person_name"],
        "phone": person.get("phone"),
        "whatsapp_enabled": bool(person.get("whatsapp_enabled")),
    }
    if person.get("phone") and person.get("whatsapp_enabled"):
        from .notify import send_whatsapp

        send_whatsapp(
            person["phone"],
            f"⚠ ESCALATION L{next_lvl}: complaint "
            f"{result['ticket_number']} ({result.get('category')}) "
            f"in unit {result.get('unit_number') or '?'} needs your "
            f"attention.",
        )
    return result


# --- hierarchy CRUD ---------------------------------------------------
def list_hierarchy(society_id: int) -> list[dict]:
    with get_conn() as conn:
        return [
            dict(r) for r in conn.execute(
                "SELECT * FROM escalation_hierarchy "
                "WHERE society_id = ? ORDER BY escalation_level, id",
                (society_id,),
            ).fetchall()
        ]


def add_hierarchy(
    society_id: int,
    role_name: str,
    person_name: str,
    phone: str | None = None,
    whatsapp_enabled: bool = True,
    email: str | None = None,
    escalation_level: int = 1,
    response_time_target_minutes: int = 60,
) -> dict:
    if role_name not in _VALID_ROLES:
        raise ComplaintError(
            f"role_name must be one of {sorted(_VALID_ROLES)}"
        )
    if escalation_level not in _LEVEL_TO_ROLE:
        raise ComplaintError(
            f"escalation_level must be 1..{_MAX_LEVEL}"
        )
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO escalation_hierarchy "
            "(society_id, role_name, person_name, phone, "
            "whatsapp_enabled, email, escalation_level, "
            "response_time_target_minutes, active) "
            "VALUES (?,?,?,?,?,?,?,?,1)",
            (society_id, role_name, person_name, phone,
             1 if whatsapp_enabled else 0, email,
             escalation_level, response_time_target_minutes),
        )
        out = conn.execute(
            "SELECT * FROM escalation_hierarchy WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(out)


_PATCHABLE = frozenset({
    "role_name", "person_name", "phone", "whatsapp_enabled", "email",
    "escalation_level", "response_time_target_minutes", "active",
})


def update_hierarchy(eid: int, society_id: int, **fields) -> dict:
    if not fields:
        raise ComplaintError("no fields to update")
    bad = set(fields) - _PATCHABLE
    if bad:
        raise ComplaintError(f"unknown field(s): {sorted(bad)}")
    if ("role_name" in fields
            and fields["role_name"] not in _VALID_ROLES):
        raise ComplaintError("invalid role_name")
    if ("escalation_level" in fields
            and fields["escalation_level"] not in _LEVEL_TO_ROLE):
        raise ComplaintError("invalid escalation_level")
    sets, params = [], []
    for k, v in fields.items():
        sets.append(f"{k} = ?")  # k is whitelisted via _PATCHABLE
        params.append(1 if k in ("whatsapp_enabled", "active") and v
                      else (0 if k in ("whatsapp_enabled", "active")
                            else v))
    params.extend([eid, society_id])
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE escalation_hierarchy SET {', '.join(sets)} "
            "WHERE id = ? AND society_id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise ComplaintError("hierarchy entry not found")
        out = conn.execute(
            "SELECT * FROM escalation_hierarchy WHERE id = ?", (eid,)
        ).fetchone()
        return dict(out)


def delete_hierarchy(eid: int, society_id: int) -> int:
    with get_conn() as conn:
        c = conn.execute(
            "DELETE FROM escalation_hierarchy "
            "WHERE id = ? AND society_id = ?",
            (eid, society_id),
        )
        return c.rowcount
