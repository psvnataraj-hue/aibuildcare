"""Self-alerting via WhatsApp (Part 4-5).

When a critical event is logged via operator_events.log_event() at
severity in ("error","critical"), this module is called to deliver a
short alert directly to the operator's WhatsApp (Nataraj's number).

Throttling: same (event_type, service) key fires AT MOST once per
THROTTLE_MINUTES (default 30) — prevents alert storms when a single
underlying outage triggers the same event repeatedly. Throttling state
lives in `system_config` rows keyed `alert_throttle:<event_type>:<service>`
with the last-fired timestamp as the value.

The destination phone is the existing escalation_hierarchy L4 entry on
Palms (society_id=1), which is Nataraj's number per project memory. If
no L4 entry exists, the alert silently falls back to a stdlib-logger
WARN and the operator-event row already exists in the DB. Critically,
this module never raises — a failed self-alert must not break the
caller's flow."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..db import get_conn

log = logging.getLogger("aibuildcare.self_alert")

THROTTLE_MINUTES = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _throttle_key(event_type: str, service: str | None) -> str:
    return f"alert_throttle:{event_type}:{service or 'system'}"


def _should_fire(event_type: str, service: str | None) -> bool:
    """Return True if THROTTLE_MINUTES has elapsed since the last fire
    of the same (event_type, service) pair. Records the new firing time
    if so (so checking is idempotent)."""
    key = _throttle_key(event_type, service)
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT config_value FROM system_config WHERE config_key = ?",
                (key,),
            ).fetchone()
            now = _now()
            now_iso = now.isoformat()
            if row:
                last_iso = (dict(row) if not isinstance(row, dict) else row)["config_value"]
                try:
                    last = datetime.fromisoformat(last_iso)
                    if (now - last) < timedelta(minutes=THROTTLE_MINUTES):
                        return False
                except Exception:
                    pass  # corrupt timestamp → treat as expired
                conn.execute(
                    "UPDATE system_config SET config_value = ?, updated_at = ? "
                    "WHERE config_key = ?",
                    (now_iso, now_iso, key),
                )
            else:
                conn.execute(
                    "INSERT INTO system_config (config_key, config_value, updated_at) "
                    "VALUES (?, ?, ?)",
                    (key, now_iso, now_iso),
                )
        return True
    except Exception as exc:
        # If we can't even read the throttle state, prefer firing once
        # over silently dropping — the operator needs to know.
        log.warning("self_alert throttle check failed: %s — firing anyway", exc)
        return True


def _operator_phone() -> str | None:
    """Find Nataraj's WhatsApp number via Palms (sid=1) L4 hierarchy
    entry. Returns None if the table is empty or doesn't have a row;
    self_alert then falls back to log-only."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT phone FROM escalation_hierarchy "
                "WHERE society_id = 1 AND escalation_level = 1 "
                "AND active = 1 AND whatsapp_enabled = 1 "
                "ORDER BY id LIMIT 1"
            ).fetchone()
            if row:
                return (dict(row) if not isinstance(row, dict) else row)["phone"]
    except Exception as exc:
        log.warning("self_alert phone lookup failed: %s", exc)
    return None


def _severity_emoji(severity: str) -> str:
    return {
        "info": "ℹ️",
        "warn": "⚠️",
        "error": "❌",
        "critical": "🔴",
    }.get(severity, "•")


def _format_message(
    event_type: str, service: str | None, severity: str, message: str,
    metadata: dict[str, Any] | None,
) -> str:
    """Short WhatsApp message — phone screens don't have room for stack
    traces. Keep under 320 chars."""
    icon = _severity_emoji(severity)
    head = f"{icon} AIBuildCare ({severity.upper()})"
    svc = f"[{service}] " if service else ""
    body = f"{head}\n{svc}{event_type}\n\n{message}"
    if len(body) > 320:
        body = body[:316] + "…"
    return body


def send(
    *,
    event_type: str,
    service: str | None,
    severity: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Best-effort WhatsApp delivery to the operator. Returns True if a
    send was attempted (not necessarily delivered), False if throttled
    or no destination phone is known. Never raises."""
    try:
        if not _should_fire(event_type, service):
            log.info(
                "self_alert throttled: %s/%s (already fired in last %d min)",
                event_type, service, THROTTLE_MINUTES,
            )
            return False
        to = _operator_phone()
        if not to:
            log.warning(
                "self_alert: no operator phone available, would have sent: %s",
                message,
            )
            return False
        # Late import — notify.py uses operator_events which uses self_alert
        # at runtime via log_event(severity=error). Late-import keeps the
        # module graph acyclic at import time.
        from . import notify
        body = _format_message(event_type, service, severity, message, metadata)
        notify.send_whatsapp(to, body)
        return True
    except Exception as exc:
        log.warning("self_alert.send failed: %s", exc)
        return False
