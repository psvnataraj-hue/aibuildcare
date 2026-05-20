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
from .complaint_service import _row_to_dict

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


# ---- tick -----------------------------------------------------------
def run_tick(now: datetime | None = None) -> dict:
    """Run every due job. Each in its own try/except so a single job
    failure doesn't abort the tick."""
    summary: dict = {}
    try:
        summary["auto_escalations"] = run_due_escalations(now)
    except Exception as exc:  # last-resort guard
        log.exception("auto-escalations top-level failure: %s", exc)
        summary["auto_escalations"] = {"error": str(exc)}
    return summary
