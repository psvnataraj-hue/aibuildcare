"""E2: cron-driven background jobs (idempotent).

A free external cron (cron-job.org / UptimeRobot HTTP keyword
monitor) hits POST /internal/jobs/tick periodically. Each job is
self-contained, stateless, and tolerates partial failure (one bad
complaint never breaks the whole tick).

Today (E2a): auto-escalation.
Coming soon: staff reminders, complainant updates, weekly summary,
major-incident flagging.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from ..db import get_conn
from . import escalation_service
from .complaint_service import _now, _row_to_dict

log = logging.getLogger("aibuildcare.jobs")

_OPEN_STATES = ("received", "acknowledged", "assigned", "in_progress")


# ---- helpers --------------------------------------------------------
def _sla_for(society_id: int, category: str | None) -> dict | None:
    if not category:
        return None
    with get_conn() as conn:
        r = conn.execute(
            "SELECT escalation_levels, priority_high_multiplier "
            "FROM category_sla_config "
            "WHERE society_id = ? AND category = ?",
            (society_id, category),
        ).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["escalation_levels"] = json.loads(
            d.get("escalation_levels") or "{}"
        )
    except (TypeError, ValueError):
        d["escalation_levels"] = {}
    return d


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # ISO-8601 with timezone (the way the app writes it)
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _elapsed_hours(c: dict, now: datetime) -> float | None:
    """Hours since the complaint was created. Negative or None means
    we can't compute, skip."""
    created = _parse_ts(c.get("created_at"))
    if not created:
        return None
    return max(0.0, (now - created).total_seconds() / 3600.0)


# ---- auto-escalation -----------------------------------------------
def _evaluate_complaint(c: dict, now: datetime) -> int:
    """Apply per-level SLA thresholds; may bump multiple levels in
    one tick if the complaint is very overdue. Returns the count of
    levels escalated this tick (0 = nothing to do)."""
    sla = _sla_for(c["society_id"], c.get("category"))
    if not sla:
        return 0
    levels = sla.get("escalation_levels") or {}
    if not levels:
        return 0
    elapsed = _elapsed_hours(c, now)
    if elapsed is None:
        return 0
    # urgent / high priority get a multiplier (e.g. 0.5 -> 2x sensitivity)
    mult = float(sla.get("priority_high_multiplier") or 1.0)
    if c.get("priority") not in ("urgent", "high"):
        mult = 1.0
    effective = elapsed / mult if mult else elapsed

    current = escalation_service._current_level(c)
    bumped = 0
    while current < escalation_service._MAX_LEVEL:
        nxt = current + 1
        threshold = (levels.get(str(nxt)) or {}).get("after_hours")
        if threshold is None or effective < float(threshold):
            break
        try:
            escalation_service.escalate(c["id"], c["society_id"])
            bumped += 1
            current = nxt
        except Exception as exc:
            # missing hierarchy, already-max, etc. -- log + stop
            log.info(
                "escalation skipped (cid=%s, lvl=%s): %s",
                c["id"], nxt, exc,
            )
            break
    return bumped


def run_due_escalations(now: datetime | None = None) -> dict:
    """Walk every open complaint; auto-escalate those past SLA.
    Returns: {checked, escalated, errors[]}.
    """
    now = now or datetime.now(timezone.utc)
    placeholders = ",".join("?" * len(_OPEN_STATES))
    out: dict = {"checked": 0, "escalated": 0, "errors": []}
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM complaints WHERE status IN ({placeholders})",
            tuple(_OPEN_STATES),
        ).fetchall()
    for r in rows:
        c = _row_to_dict(r)
        if not c:
            continue
        out["checked"] += 1
        try:
            n = _evaluate_complaint(c, now)
            out["escalated"] += n
        except Exception as exc:  # never let one bad row kill the tick
            log.warning(
                "auto-escalate error cid=%s: %s", c.get("id"), exc
            )
            out["errors"].append(
                {"complaint_id": c.get("id"), "error": str(exc)}
            )
    return out


# ---- staff reminders (E2b) ------------------------------------------
_STAFF_REMINDER_HOURS = 2.0
_STAFF_REMINDABLE_STATES = ("assigned", "acknowledged")


def run_due_staff_reminders(now: datetime | None = None) -> dict:
    """Nudge staff who have assigned complaints that are >2h since
    last activity AND haven't been moved into in_progress yet.
    Throttled by complaints.last_reminder_sent_at (no more than once
    per ~2h per complaint).
    """
    now = now or datetime.now(timezone.utc)
    out: dict = {"checked": 0, "reminded": 0, "errors": []}
    placeholders = ",".join("?" * len(_STAFF_REMINDABLE_STATES))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT c.id AS cid, c.ticket_number, c.unit_number, "
            f"c.category, c.updated_at, c.last_reminder_sent_at, "
            f"c.reminder_sent_count, "
            f"sm.phone_primary AS staff_phone, sm.name AS staff_name, "
            f"sm.whatsapp_enabled AS staff_wa "
            f"FROM complaints c "
            f"JOIN staff_members sm ON sm.id = c.assigned_staff_id "
            f"WHERE c.status IN ({placeholders}) "
            f"AND sm.active = 1",
            tuple(_STAFF_REMINDABLE_STATES),
        ).fetchall()
    for r in rows:
        c = dict(r)
        out["checked"] += 1
        try:
            anchor = (_parse_ts(c.get("last_reminder_sent_at"))
                      or _parse_ts(c.get("updated_at")))
            if not anchor:
                continue
            elapsed_h = (now - anchor).total_seconds() / 3600.0
            if elapsed_h < _STAFF_REMINDER_HOURS:
                continue
            if c.get("staff_wa") and c.get("staff_phone"):
                from .notify import send_whatsapp

                send_whatsapp(
                    c["staff_phone"],
                    f"⏰ REMINDER: complaint {c['ticket_number']} "
                    f"({c.get('category')}) in unit "
                    f"{c.get('unit_number') or '?'} is still pending. "
                    f"Please update status or resolve.",
                )
            with get_conn() as conn:
                conn.execute(
                    "UPDATE complaints SET last_reminder_sent_at = ?, "
                    "reminder_sent_count = "
                    "COALESCE(reminder_sent_count, 0) + 1 "
                    "WHERE id = ?",
                    (now.isoformat(), c["cid"]),
                )
            out["reminded"] += 1
        except Exception as exc:
            log.warning(
                "staff reminder error cid=%s: %s", c.get("cid"), exc
            )
            out["errors"].append(
                {"complaint_id": c.get("cid"), "error": str(exc)}
            )
    return out


# ---- complainant updates (E2b) --------------------------------------
_COMPLAINANT_UPDATE_HOURS = 4.0
_COMPLAINANT_UPDATABLE_STATES = (
    "received", "acknowledged", "assigned", "in_progress",
)


def run_due_complainant_updates(now: datetime | None = None) -> dict:
    """Periodically reassure the resident their complaint is being
    handled. Throttled by complaints.last_complainant_update_at."""
    now = now or datetime.now(timezone.utc)
    out: dict = {"checked": 0, "updated": 0, "errors": []}
    placeholders = ",".join("?" * len(_COMPLAINANT_UPDATABLE_STATES))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, ticket_number, status, reporter_phone, "
            f"category, created_at, last_complainant_update_at, "
            f"estimated_completion_date "
            f"FROM complaints "
            f"WHERE status IN ({placeholders}) "
            f"AND reporter_phone IS NOT NULL "
            f"AND reporter_phone != ''",
            tuple(_COMPLAINANT_UPDATABLE_STATES),
        ).fetchall()
    for r in rows:
        c = dict(r)
        out["checked"] += 1
        try:
            anchor = (_parse_ts(c.get("last_complainant_update_at"))
                      or _parse_ts(c.get("created_at")))
            if not anchor:
                continue
            elapsed_h = (now - anchor).total_seconds() / 3600.0
            if elapsed_h < _COMPLAINANT_UPDATE_HOURS:
                continue
            eta = c.get("estimated_completion_date")
            eta_line = f" Est. completion: {eta[:10]}." if eta else ""
            msg = (
                f"Update on {c['ticket_number']} ({c.get('category')}): "
                f"status is '{c['status']}'. We're on it.{eta_line}"
            )
            from .notify import send_whatsapp

            send_whatsapp(c["reporter_phone"], msg)
            with get_conn() as conn:
                conn.execute(
                    "UPDATE complaints SET "
                    "last_complainant_update_at = ? WHERE id = ?",
                    (now.isoformat(), c["id"]),
                )
            out["updated"] += 1
        except Exception as exc:
            log.warning(
                "complainant update error cid=%s: %s",
                c.get("id"), exc,
            )
            out["errors"].append(
                {"complaint_id": c.get("id"), "error": str(exc)}
            )
    return out


# ---- tick -----------------------------------------------------------
def run_tick(now: datetime | None = None) -> dict:
    """Run every due job. Each in its own try/except so a single job
    failure doesn't abort the tick."""
    summary: dict = {}
    for name, fn in (
        ("auto_escalations", run_due_escalations),
        ("staff_reminders", run_due_staff_reminders),
        ("complainant_updates", run_due_complainant_updates),
    ):
        try:
            summary[name] = fn(now)
        except Exception as exc:  # last-resort guard
            log.exception("%s top-level failure: %s", name, exc)
            summary[name] = {"error": str(exc)}
    return summary
