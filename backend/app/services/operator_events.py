"""Operator-readable event log.

A single chokepoint for surfacing system events to the operator
(Nataraj / Sravya during testing). Used by:

  - notify.py        — logs TEST_PHONE_SKIPPED, external-send failures
  - jobs_service.py  — logs cron tick start/complete and per-job stats
  - quota_monitor.py — logs quota-warning crossings
  - diagnostics.py   — health-check failures
  - internal_jobs    — seeding-lock activations

Design choices:

- ★ NEVER raises. log_event swallows every exception so a logging
  failure cannot break the calling code path. This is the
  graceful-degradation requirement applied to logging itself.
- ★ Operator-readable, not stack-trace-y. Each row carries a one-line
  message + a service tag + a severity + optional structured metadata
  (JSON-stringified). The query helper renders the most-recent rows
  in human-scannable form.
- Optional severity-gated self-alert: severity in ("error","critical")
  triggers a self_alert.send() — see self_alert.py for throttling.
  Wired with a late import to avoid circular dependency (self_alert
  uses notify which uses operator_events).

Event-type vocabulary (extensible — these are conventions, not enums):

  test_phone_skipped       — Layer 2 cron safety, every test-range no-op
  seeding_lock_active      — Layer 3 cron safety, tick endpoint skipped
  external_call_failed     — Anthropic/Twilio/SendGrid/R2/Sarvam down
  external_call_succeeded  — for diagnostics warm-state tracking
  quota_warning_80         — quota crossed 80% threshold
  quota_warning_90         — quota crossed 90% threshold
  cron_silent              — dead-man's switch (no tick in 45 min)
  cron_tick_complete       — heartbeat
  health_check_degraded    — composite health turned amber/red
  data_integrity_warning   — orphans surfaced, etc.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..db import get_conn

log = logging.getLogger("aibuildcare.operator_events")


# Severities that trigger self-alert. Set wide initially; throttle in
# self_alert keeps it from becoming noise.
_ALERT_SEVERITIES = frozenset({"error", "critical"})


def log_event(
    event_type: str,
    message: str,
    *,
    service: str | None = None,
    severity: str = "info",
    metadata: dict[str, Any] | None = None,
    society_id: int | None = None,
    alert: bool | None = None,
) -> int | None:
    """Append a row to operator_events. Returns the new id, or None if
    logging failed (which is silently swallowed — see module docstring).

    Args:
        event_type:  short stable identifier (see vocabulary in module
                     docstring). Used by dashboards to filter.
        message:     one-line human-readable description. Visible in the
                     operator log; should explain WHAT, not the full
                     stack trace.
        service:     which external service this event relates to
                     ("twilio", "sendgrid", "anthropic", "r2", "sarvam",
                     "cron", "db", or None for system-level events).
        severity:    "info" / "warn" / "error" / "critical".
        metadata:    structured detail. JSON-serialised at write time.
        society_id:  if the event is tenant-scoped, the affected society.
        alert:       force-enable or force-disable self-alerting,
                     regardless of severity. Defaults to None
                     (severity-driven).
    """
    try:
        meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
    except Exception:
        meta_json = None

    new_id: int | None = None
    try:
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO operator_events "
                "(event_type, service, severity, message, metadata, society_id) "
                "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                (event_type, service, severity, message, meta_json, society_id),
            ).fetchone()
            if row:
                # row can be a dict (psycopg2 RealDictCursor) or tuple
                new_id = row["id"] if isinstance(row, dict) else row[0]
    except Exception:
        # Try without RETURNING (older SQLite) — INSERT without id read
        try:
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO operator_events "
                    "(event_type, service, severity, message, metadata, society_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (event_type, service, severity, message, meta_json, society_id),
                )
        except Exception as exc:
            # Final fallback: log to stdlib logger so we lose nothing
            log.warning("operator_events log failed: %s | %s/%s | %s",
                        exc, event_type, service, message)

    # Self-alerting (late import — see module docstring)
    should_alert = alert if alert is not None else (severity in _ALERT_SEVERITIES)
    if should_alert:
        try:
            from . import self_alert
            self_alert.send(event_type=event_type, service=service,
                            severity=severity, message=message,
                            metadata=metadata)
        except Exception as exc:
            log.warning("self_alert dispatch failed: %s", exc)

    return new_id


def recent_events(
    limit: int = 100, severity: str | None = None,
    service: str | None = None, since_minutes: int | None = None,
    unseen_only: bool = False,
) -> list[dict]:
    """Query the operator-event log. Returns most-recent first.

    Used by the diagnostics router's /events endpoint and by the
    dashboard tile."""
    where = []
    params: list[Any] = []
    if severity:
        where.append("severity = ?")
        params.append(severity)
    if service:
        where.append("service = ?")
        params.append(service)
    if since_minutes is not None:
        where.append("ts >= datetime('now', ?)")
        params.append(f"-{since_minutes} minutes")
    if unseen_only:
        where.append("seen = 0")

    sql = "SELECT id, ts, event_type, service, severity, message, metadata, " \
          "society_id, seen FROM operator_events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    try:
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
    except Exception:
        # Postgres doesn't accept SQLite's datetime('now', '-N minutes')
        # syntax. For pg we just drop the since_minutes filter and let
        # the caller post-filter; this only matters in pg.
        sql_pg = "SELECT id, ts, event_type, service, severity, message, " \
                 "metadata, society_id, seen FROM operator_events " \
                 "ORDER BY ts DESC LIMIT %s"
        try:
            with get_conn() as conn:
                rows = [dict(r) for r in conn.execute(sql_pg, (limit,)).fetchall()]
        except Exception as exc:
            log.warning("recent_events query failed on both backends: %s", exc)
            return []

    for r in rows:
        if r.get("metadata"):
            try:
                r["metadata"] = json.loads(r["metadata"])
            except Exception:
                pass
    return rows


def mark_seen(event_ids: list[int]) -> int:
    """Mark events as seen. Returns count updated. Used by the operator
    UI's 'acknowledge' action."""
    if not event_ids:
        return 0
    placeholders = ",".join("?" for _ in event_ids)
    try:
        with get_conn() as conn:
            cur = conn.execute(
                f"UPDATE operator_events SET seen = 1 WHERE id IN ({placeholders})",
                tuple(event_ids),
            )
            return cur.rowcount if hasattr(cur, "rowcount") else len(event_ids)
    except Exception as exc:
        log.warning("mark_seen failed: %s", exc)
        return 0


def severity_counts(since_minutes: int = 60) -> dict[str, int]:
    """Count events by severity over the last N minutes. Used by the
    diagnostics health-check composer."""
    out = {"info": 0, "warn": 0, "error": 0, "critical": 0}
    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT severity, COUNT(*) AS c FROM operator_events "
                "WHERE ts >= datetime('now', ?) GROUP BY severity",
                (f"-{since_minutes} minutes",),
            ).fetchall()
            for r in rows:
                rd = dict(r)
                if rd["severity"] in out:
                    out[rd["severity"]] = rd["c"]
    except Exception:
        # Best-effort; the composer treats unknown counts as 0
        pass
    return out
