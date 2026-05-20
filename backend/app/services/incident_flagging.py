"""E2d: major-incident auto-flagging.

Heuristics (first match wins, in this priority order):

  1. **rapid escalation** — chairman reached within 2h of creation.
  2. **safety-critical urgent** — category in the safety tier AND
     priority urgent/high.
  3. **repeat unit** — same unit_number has >= 2 complaints in the
     last 7 days (society-scoped).
  4. **category surge** — same society + category has >= 3 complaints
     created in the last 24h.

When a complaint is flagged, set major_incident=1 +
major_incident_flagged_at + major_incident_reason. Once set, never
re-evaluated (the column is idempotent state).

On flag, notify the society's escalation_hierarchy contacts whose
whatsapp_enabled=1 (committee/chairman/secretary/sr_manager/manager).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..db import get_conn
from .complaint_service import _now

log = logging.getLogger("aibuildcare.incident")

_SAFETY_CATEGORIES = ("Fire Safety", "Security", "Elevator",
                      "Civil/Structural", "Generator/Power Backup")
_HOT_PRIORITIES = ("urgent", "high")


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _reason_for(conn, c: dict, now: datetime) -> str | None:
    """Determine the major-incident reason or None."""
    # 1. rapid escalation
    created = _parse_ts(c.get("created_at"))
    chair = _parse_ts(c.get("escalated_to_chairman_at"))
    if created and chair:
        if (chair - created).total_seconds() / 3600.0 <= 2.0:
            return "rapid escalation to chairman (within 2h of creation)"
    # 2. safety-critical urgent
    if (c.get("category") in _SAFETY_CATEGORIES
            and c.get("priority") in _HOT_PRIORITIES):
        return f"safety-critical {c.get('category')} at {c.get('priority')} priority"
    # 3. repeat unit (>=2 in 7 days, same society + unit)
    unit = c.get("unit_number")
    if unit:
        cutoff = (now - timedelta(days=7)).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM complaints "
            "WHERE society_id = ? AND unit_number = ? "
            "AND created_at >= ?",
            (c["society_id"], unit, cutoff),
        ).fetchone()
        if row and dict(row)["n"] >= 2:
            return (
                f"repeat complaint from unit {unit} "
                f"within 7 days (n={dict(row)['n']})"
            )
    # 4. category surge (>=3 in 24h, same society + category)
    cat = c.get("category")
    if cat:
        cutoff24 = (now - timedelta(hours=24)).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM complaints "
            "WHERE society_id = ? AND category = ? "
            "AND created_at >= ?",
            (c["society_id"], cat, cutoff24),
        ).fetchone()
        if row and dict(row)["n"] >= 3:
            return (
                f"category surge: {dict(row)['n']} {cat} complaints "
                f"in 24h"
            )
    return None


def _notify_committee(conn, society_id: int, c: dict, reason: str) -> int:
    """WhatsApp the escalation hierarchy for this society. Returns the
    number of (graceful-no-op-aware) sends attempted."""
    rows = conn.execute(
        "SELECT person_name, phone, whatsapp_enabled "
        "FROM escalation_hierarchy "
        "WHERE society_id = ? AND active = 1 "
        "AND phone IS NOT NULL AND phone != ''",
        (society_id,),
    ).fetchall()
    if not rows:
        return 0
    from .notify import send_whatsapp

    body = (
        f"🚨 MAJOR INCIDENT — {c.get('ticket_number')} "
        f"({c.get('category') or 'Other'}, "
        f"{c.get('priority') or 'normal'}) "
        f"in unit {c.get('unit_number') or '?'}. "
        f"Reason: {reason}. Please review immediately."
    )
    n = 0
    for r in rows:
        d = dict(r)
        if d.get("whatsapp_enabled"):
            send_whatsapp(d["phone"], body)
            n += 1
    return n


def run_due_incident_flagging(now: datetime | None = None) -> dict:
    """Walk every open OR recently-resolved-within-7-days complaint
    not already flagged; if a heuristic fires, mark + notify."""
    now = now or datetime.now(timezone.utc)
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    out: dict = {"checked": 0, "flagged": 0, "errors": []}
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM complaints "
            "WHERE COALESCE(major_incident, 0) = 0 "
            "AND created_at >= ?",
            (cutoff_7d,),
        ).fetchall()
    for r in rows:
        c = dict(r)
        out["checked"] += 1
        try:
            with get_conn() as conn:
                reason = _reason_for(conn, c, now)
                if not reason:
                    continue
                conn.execute(
                    "UPDATE complaints SET major_incident = 1, "
                    "major_incident_flagged_at = ?, "
                    "major_incident_reason = ? WHERE id = ?",
                    (now.isoformat(), reason, c["id"]),
                )
                conn.execute(
                    "INSERT INTO complaint_messages "
                    "(complaint_id, sender, body) VALUES (?,?,?)",
                    (c["id"], "system",
                     f"⚠ Flagged as MAJOR INCIDENT: {reason}"),
                )
                _notify_committee(conn, c["society_id"], c, reason)
            out["flagged"] += 1
        except Exception as exc:
            log.warning(
                "incident flagging error cid=%s: %s",
                c.get("id"), exc,
            )
            out["errors"].append(
                {"complaint_id": c.get("id"), "error": str(exc)}
            )
    return out
