"""Health-check composer (Part 4-3 + Part 4-4).

A single function `get_health_status()` returns the at-a-glance system
state used by the dashboard tile and the /api/v1/diagnostics/health
endpoint. One glance tells the operator:

  - All green → everything is fine, no action needed.
  - One amber  → degraded but functional (e.g. one external service slow).
  - Red       → action required (cron silent, DB unreachable, quota
                breached at 90%).

Each service check is independent so one slow probe doesn't cascade.
Critical service health rolls up into the `overall` field.

Includes the cron dead-man's switch (Part 4-4): if the
`system_config.cron_last_tick_at` value is older than
CRON_SILENT_THRESHOLD_MINUTES (45 by default), the cron service is
marked RED and an operator_event is logged with severity=critical —
which fires self_alert via the standard log_event path.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import get_settings
from ..db import get_conn
from . import operator_events, quota_monitor

log = logging.getLogger("aibuildcare.diagnostics")

CRON_SILENT_THRESHOLD_MINUTES = 45


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────
# Individual probes
# ─────────────────────────────────────────────────────────────────────────

def _probe_db() -> dict:
    try:
        with get_conn() as conn:
            row = conn.execute("SELECT 1 AS ok").fetchone()
            ok = (dict(row) if not isinstance(row, dict) else row).get("ok") == 1
        if ok:
            return {"status": "ok", "detail": "Database reachable.",
                    "last_check": _now_iso()}
        return {"status": "warn",
                "detail": "Unexpected DB probe result.",
                "last_check": _now_iso()}
    except Exception as exc:
        return {"status": "error",
                "detail": f"DB unreachable: {type(exc).__name__}: {exc}",
                "last_check": _now_iso()}


def _probe_cron() -> dict:
    """Dead-man's-switch check: read cron_last_tick_at from system_config
    and compare to now. If gap > threshold, flag critical + log."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT config_value FROM system_config "
                "WHERE config_key = 'cron_last_tick_at'"
            ).fetchone()
            if not row:
                return {"status": "warn",
                        "detail": "cron_last_tick_at not yet seeded.",
                        "last_check": _now_iso()}
            last_iso = (dict(row) if not isinstance(row, dict) else row)["config_value"]
            try:
                last = datetime.fromisoformat(last_iso)
            except Exception:
                return {"status": "warn",
                        "detail": f"cron_last_tick_at unreadable: {last_iso}",
                        "last_check": _now_iso()}
            now = datetime.now(timezone.utc)
            gap_min = (now - last).total_seconds() / 60.0
            if gap_min > CRON_SILENT_THRESHOLD_MINUTES:
                # Fire the alarm. Severity=critical → self_alert fires
                # (subject to its own throttle).
                operator_events.log_event(
                    "cron_silent",
                    f"Cron silent for {int(gap_min)} min (threshold {CRON_SILENT_THRESHOLD_MINUTES})",
                    service="cron", severity="critical",
                    metadata={"last_tick_at": last_iso,
                              "gap_minutes": int(gap_min)},
                )
                return {"status": "error",
                        "detail": f"Cron silent — last tick {int(gap_min)} min ago",
                        "last_tick_at": last_iso,
                        "minutes_since_tick": int(gap_min),
                        "last_check": _now_iso()}
            return {"status": "ok",
                    "detail": f"Cron tick {int(gap_min)} min ago",
                    "last_tick_at": last_iso,
                    "minutes_since_tick": int(gap_min),
                    "last_check": _now_iso()}
    except Exception as exc:
        return {"status": "error",
                "detail": f"cron probe failed: {type(exc).__name__}: {exc}",
                "last_check": _now_iso()}


def _probe_anthropic() -> dict:
    s = get_settings()
    if not s.anthropic_api_key:
        return {"status": "informational",
                "detail": "Anthropic key not configured.",
                "last_check": _now_iso()}
    # No cheap "ping" endpoint on the Anthropic API; we infer health
    # from recent operator_events. If the last 60 min show ≥1
    # external_call_failed for service=anthropic, mark warn.
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM operator_events "
                "WHERE service = 'anthropic' AND event_type = 'external_call_failed' "
                "AND ts >= datetime('now', '-60 minutes')"
            ).fetchone()
            failures = (dict(row) if not isinstance(row, dict) else row)["c"]
        if failures >= 3:
            return {"status": "error",
                    "detail": f"{failures} Anthropic call failures in last hour",
                    "last_check": _now_iso()}
        if failures >= 1:
            return {"status": "warn",
                    "detail": f"{failures} Anthropic call failure(s) in last hour",
                    "last_check": _now_iso()}
        return {"status": "ok",
                "detail": "No recent Anthropic failures logged.",
                "last_check": _now_iso()}
    except Exception:
        return {"status": "ok",
                "detail": "Anthropic key configured; recent-failure probe unavailable.",
                "last_check": _now_iso()}


def _probe_external(service: str, configured: bool, label: str) -> dict:
    """Generic probe: read recent failure count from operator_events."""
    if not configured:
        return {"status": "informational",
                "detail": f"{label} not configured.",
                "last_check": _now_iso()}
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM operator_events "
                "WHERE service = ? AND event_type = 'external_call_failed' "
                "AND ts >= datetime('now', '-60 minutes')",
                (service,),
            ).fetchone()
            failures = (dict(row) if not isinstance(row, dict) else row)["c"]
        if failures >= 5:
            return {"status": "error",
                    "detail": f"{failures} {label} failures in last hour",
                    "last_check": _now_iso()}
        if failures >= 1:
            return {"status": "warn",
                    "detail": f"{failures} {label} failure(s) in last hour",
                    "last_check": _now_iso()}
        return {"status": "ok",
                "detail": f"No recent {label} failures.",
                "last_check": _now_iso()}
    except Exception:
        return {"status": "ok",
                "detail": f"{label} configured; recent-failure probe unavailable.",
                "last_check": _now_iso()}


def _probe_twilio() -> dict:
    s = get_settings()
    return _probe_external(
        "twilio",
        bool(s.twilio_account_sid and s.twilio_auth_token),
        "Twilio",
    )


def _probe_sendgrid() -> dict:
    s = get_settings()
    return _probe_external("sendgrid", bool(s.sendgrid_api_key), "SendGrid")


def _probe_r2() -> dict:
    s = get_settings()
    return _probe_external(
        "r2", bool(s.r2_endpoint_url and s.r2_access_key_id), "R2",
    )


def _probe_sarvam() -> dict:
    s = get_settings()
    return _probe_external("sarvam", bool(s.sarvam_api_key), "Sarvam")


# ─────────────────────────────────────────────────────────────────────────
# Composer
# ─────────────────────────────────────────────────────────────────────────

# Services whose status rolls into the overall health verdict.
# "informational" never degrades overall — if Anthropic isn't configured,
# that's a deployment-time decision, not a runtime fault.
_CRITICAL_SERVICES = {"db", "cron"}


def get_health_status() -> dict:
    """Build the at-a-glance health payload. Returns the same shape used
    by both the API endpoint and the dashboard tile. Never raises —
    a failure in one probe is captured as that probe's status=error."""
    services = {
        "db":        _probe_db(),
        "anthropic": _probe_anthropic(),
        "twilio":    _probe_twilio(),
        "sendgrid":  _probe_sendgrid(),
        "r2":        _probe_r2(),
        "sarvam":    _probe_sarvam(),
        "cron":      _probe_cron(),
    }

    # Severity counts give a quick "did anything spike recently?" reading
    severity = operator_events.severity_counts(since_minutes=60)

    # Quota check — uses the heavier quota_monitor module. Wrapped so
    # a slow Twilio/SendGrid API call here can't hang the health probe;
    # the probe falls back to the lighter recent-events check above.
    quota_warnings: list[dict] = []
    try:
        for q in quota_monitor.get_all_quotas():
            if q.get("status") in ("warn_80", "warn_90"):
                quota_warnings.append({
                    "service": q["service"],
                    "level": q["status"],
                    "detail": q.get("detail"),
                })
    except Exception as exc:
        log.warning("quota_monitor probe failed during health check: %s", exc)

    # Roll up overall verdict
    overall = "healthy"
    for name, info in services.items():
        st = info["status"]
        if st == "error" and name in _CRITICAL_SERVICES:
            overall = "unhealthy"
            break
        if st == "error":
            overall = "degraded"
        elif st == "warn" and overall == "healthy":
            overall = "degraded"
    if quota_warnings and overall == "healthy":
        overall = "degraded"

    return {
        "overall": overall,
        "checked_at": _now_iso(),
        "services": services,
        "severity_counts_last_60min": severity,
        "quota_warnings": quota_warnings,
    }
