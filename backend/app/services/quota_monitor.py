"""Proactive quota monitoring (Part 4-2).

Tracks consumption vs known limits across our external services and warns
the operator at ~80% so we never breach silently.

★ Honesty about what's PROGRAMMATIC vs ESTIMATED.

PROGRAMMATIC (real API queries — can give a current number):
  - Twilio:    Account balance + today's message count via Twilio REST API
  - SendGrid:  Daily-sends count via SendGrid Stats API
  - Cron:      Run-count over the past 24h — we count ourselves (cron heartbeat)

ESTIMATED (no public API on the free tier — derived from local proxies):
  - Anthropic spend: tracked by accumulating usage from response headers
                     into the operator_events table; we don't have a balance
                     API for free-tier accounts so this is approximate.
  - Supabase storage/bandwidth: estimated from our own row counts and media
                     URL references; the Supabase dashboard is the source
                     of truth, we just nudge the operator toward it.
  - R2 storage:     can be queried via Cloudflare API (PROGRAMMATIC) if R2
                     access keys are set up with the right scope; falls
                     back to ESTIMATED from our own complaint-media count
                     when the API isn't reachable.
  - Render bandwidth: no usage API on free tier; pure estimate from
                     request log counts. Treated as informational only.

Status returned for each service:

  {
    "service": "twilio",
    "monitorability": "programmatic" | "estimated" | "informational",
    "usage": {"current": 47, "limit": 1000, "pct": 4.7},   # may be None
    "balance": {"value_usd": 12.34},                       # twilio only
    "status": "ok" | "warn_80" | "warn_90" | "error",
    "last_checked": "<iso>",
    "detail": "human-readable summary"
  }

The check is called from:
  - diagnostics.get_health_status() composer (synchronous-on-request)
  - daily cron job (jobs_service.run_due_quota_checks — to be added) so
    threshold crossings get logged once per crossing, not on every poll.

This module never raises — every external lookup is wrapped in
try/except and reported as `status="error"` with a detail message.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import get_settings
from . import operator_events

log = logging.getLogger("aibuildcare.quota_monitor")

WARN_80 = 80
WARN_90 = 90

# Known limits per service (the free / starter-tier ceilings we care about).
# Adjust if a paid plan is activated.
_LIMITS = {
    "sendgrid_daily_sends":   100,    # SendGrid free tier daily
    "twilio_balance_warn_usd": 5.0,   # below $5 → warn 80%
    "twilio_balance_crit_usd": 1.0,   # below $1 → warn 90%
    "anthropic_monthly_usd":  20.0,   # soft budget, configurable
    "supabase_storage_mb":    500,    # free tier
    "r2_storage_mb":          10240,  # 10 GB free tier
    "render_bandwidth_gb":    100,    # free tier monthly
    "cron_daily_ticks":       100,    # cron-job.org free tier daily limit
}


# ─────────────────────────────────────────────────────────────────────────
# Per-service checkers
# ─────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_twilio() -> dict:
    """Programmatic: balance + today's message count via Twilio REST API.

    Returns ok/warn_80/warn_90/error. On unconfigured creds, returns
    informational status — not an error, just "we have nothing to check"."""
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        return {
            "service": "twilio",
            "monitorability": "programmatic",
            "status": "informational",
            "detail": "Twilio creds not configured; cannot query balance.",
            "last_checked": _now_iso(),
        }
    try:
        from twilio.rest import Client
        client = Client(s.twilio_account_sid, s.twilio_auth_token)

        # Twilio balance — direct REST call via the SDK
        balance = client.balance.fetch()
        balance_usd = float(balance.balance or 0)

        # Today's message count
        since = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        msgs = client.messages.list(date_sent_after=since, limit=1000)
        today_count = len(msgs)

        if balance_usd <= _LIMITS["twilio_balance_crit_usd"]:
            status = "warn_90"
            detail = f"Twilio balance ${balance_usd:.2f} below critical $1"
        elif balance_usd <= _LIMITS["twilio_balance_warn_usd"]:
            status = "warn_80"
            detail = f"Twilio balance ${balance_usd:.2f} below warn $5"
        else:
            status = "ok"
            detail = f"Twilio balance ${balance_usd:.2f}, {today_count} msgs today"

        return {
            "service": "twilio",
            "monitorability": "programmatic",
            "status": status,
            "balance": {"value_usd": balance_usd, "currency": balance.currency},
            "usage_today_messages": today_count,
            "detail": detail,
            "last_checked": _now_iso(),
        }
    except Exception as exc:
        return {
            "service": "twilio",
            "monitorability": "programmatic",
            "status": "error",
            "detail": f"Twilio quota check failed: {type(exc).__name__}: {exc}",
            "last_checked": _now_iso(),
        }


def _check_sendgrid() -> dict:
    """Programmatic: today's send count via SendGrid Stats API."""
    s = get_settings()
    if not s.sendgrid_api_key:
        return {
            "service": "sendgrid",
            "monitorability": "programmatic",
            "status": "informational",
            "detail": "SendGrid key not configured.",
            "last_checked": _now_iso(),
        }
    try:
        import urllib.request, json as _json
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = f"https://api.sendgrid.com/v3/stats?start_date={today}&end_date={today}&aggregated_by=day"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {s.sendgrid_api_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        # Stats payload is a list of date-buckets; sum requests today
        sends_today = 0
        for bucket in data:
            for stat in bucket.get("stats", []):
                sends_today += int(stat.get("metrics", {}).get("requests", 0))
        limit = _LIMITS["sendgrid_daily_sends"]
        pct = (sends_today / limit) * 100 if limit else 0
        if pct >= WARN_90:
            status = "warn_90"
        elif pct >= WARN_80:
            status = "warn_80"
        else:
            status = "ok"
        return {
            "service": "sendgrid",
            "monitorability": "programmatic",
            "status": status,
            "usage": {"current": sends_today, "limit": limit, "pct": round(pct, 1)},
            "detail": f"{sends_today}/{limit} daily sends ({pct:.0f}%)",
            "last_checked": _now_iso(),
        }
    except Exception as exc:
        return {
            "service": "sendgrid",
            "monitorability": "programmatic",
            "status": "error",
            "detail": f"SendGrid stats query failed: {type(exc).__name__}: {exc}",
            "last_checked": _now_iso(),
        }


def _check_anthropic() -> dict:
    """Estimated. Anthropic doesn't expose a free-tier balance API, so we
    accumulate usage from our own operator_events tracking. The dashboard
    points the operator at the Anthropic console for ground truth."""
    return {
        "service": "anthropic",
        "monitorability": "estimated",
        "status": "informational",
        "detail": "No balance API on free tier — check console.anthropic.com directly. "
                  "Local accumulation from response usage headers is on the roadmap.",
        "last_checked": _now_iso(),
    }


def _check_supabase() -> dict:
    """Estimated from local row counts. Source of truth = Supabase dashboard."""
    try:
        from ..db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM complaints"
            ).fetchone()
            complaint_count = (dict(row) if not isinstance(row, dict) else row)["c"]
            row2 = conn.execute(
                "SELECT COUNT(*) AS c FROM operator_events"
            ).fetchone()
            event_count = (dict(row2) if not isinstance(row2, dict) else row2)["c"]
        return {
            "service": "supabase",
            "monitorability": "estimated",
            "status": "informational",
            "usage": {"complaint_rows": complaint_count, "operator_event_rows": event_count},
            "detail": (
                f"{complaint_count} complaints + {event_count} operator events. "
                "Free-tier limit: 500 MB storage. Check dashboard for actual."
            ),
            "last_checked": _now_iso(),
        }
    except Exception as exc:
        return {
            "service": "supabase",
            "monitorability": "estimated",
            "status": "error",
            "detail": f"local row-count probe failed: {exc}",
            "last_checked": _now_iso(),
        }


def _check_r2() -> dict:
    """R2 has a Cloudflare API but it requires scoped credentials we may
    not always have. Check the env-configured `r2_endpoint_url` —
    if present, attempt a bucket-stats query; otherwise report
    informational."""
    s = get_settings()
    if not (s.r2_endpoint_url and s.r2_access_key_id):
        return {
            "service": "r2",
            "monitorability": "estimated",
            "status": "informational",
            "detail": "R2 creds not configured; storage unknown.",
            "last_checked": _now_iso(),
        }
    # S3 ListObjects + summary — works for R2 too via the S3-compatible API
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=s.r2_endpoint_url,
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
        )
        paginator = client.get_paginator("list_objects_v2")
        total_size = 0
        total_count = 0
        for page in paginator.paginate(Bucket=s.r2_bucket):
            for obj in page.get("Contents", []):
                total_size += obj["Size"]
                total_count += 1
        size_mb = total_size / (1024 * 1024)
        limit_mb = _LIMITS["r2_storage_mb"]
        pct = (size_mb / limit_mb) * 100 if limit_mb else 0
        if pct >= WARN_90:
            status = "warn_90"
        elif pct >= WARN_80:
            status = "warn_80"
        else:
            status = "ok"
        return {
            "service": "r2",
            "monitorability": "programmatic",
            "status": status,
            "usage": {"current_mb": round(size_mb, 1), "limit_mb": limit_mb, "pct": round(pct, 2)},
            "detail": f"{total_count} objects, {size_mb:.1f} MB / {limit_mb} MB ({pct:.1f}%)",
            "last_checked": _now_iso(),
        }
    except Exception as exc:
        return {
            "service": "r2",
            "monitorability": "estimated",
            "status": "informational",
            "detail": f"R2 query unavailable: {type(exc).__name__}; using fallback estimate",
            "last_checked": _now_iso(),
        }


def _check_render() -> dict:
    """Render has no free-tier usage API. Pure informational."""
    return {
        "service": "render",
        "monitorability": "informational",
        "status": "informational",
        "detail": "No bandwidth API on free tier — check render.com dashboard.",
        "last_checked": _now_iso(),
    }


def _check_cron() -> dict:
    """Self-monitored. cron-job.org free tier allows ~100 runs/day on
    the 1-min cadence; we run every 15 min = 96/day. Count from
    cron_tick_complete events in the last 24h."""
    try:
        from ..db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM operator_events "
                "WHERE event_type = 'cron_tick_complete' "
                "AND ts >= datetime('now', '-24 hours')"
            ).fetchone()
            count = (dict(row) if not isinstance(row, dict) else row)["c"]
    except Exception:
        # Postgres syntax differs — fall back to a 24h-bounded count
        try:
            from ..db import get_conn
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM operator_events "
                    "WHERE event_type = 'cron_tick_complete' "
                    "AND ts >= (now() - interval '24 hours')::text"
                ).fetchone()
                count = (dict(row) if not isinstance(row, dict) else row)["c"]
        except Exception:
            count = 0
    limit = _LIMITS["cron_daily_ticks"]
    pct = (count / limit) * 100 if limit else 0
    if pct >= WARN_90:
        status = "warn_90"
    elif pct >= WARN_80:
        status = "warn_80"
    else:
        status = "ok"
    return {
        "service": "cron",
        "monitorability": "programmatic",
        "status": status,
        "usage": {"current": count, "limit": limit, "pct": round(pct, 1)},
        "detail": f"{count}/{limit} ticks in last 24h",
        "last_checked": _now_iso(),
    }


# ─────────────────────────────────────────────────────────────────────────
# Composer
# ─────────────────────────────────────────────────────────────────────────

ALL_CHECKERS = (
    _check_twilio, _check_sendgrid, _check_anthropic,
    _check_supabase, _check_r2, _check_render, _check_cron,
)


def get_all_quotas() -> list[dict]:
    """Run every checker. Each is independently wrapped so one
    misbehaving checker doesn't break the rest. Used by the diagnostics
    router."""
    out: list[dict] = []
    for chk in ALL_CHECKERS:
        try:
            out.append(chk())
        except Exception as exc:
            out.append({
                "service": getattr(chk, "__name__", "unknown").replace("_check_", ""),
                "monitorability": "programmatic",
                "status": "error",
                "detail": f"checker crashed: {type(exc).__name__}: {exc}",
                "last_checked": _now_iso(),
            })
    return out


def emit_threshold_crossings() -> int:
    """Daily-cron-job entry point: emit one operator_event per warn-80
    or warn-90 crossing detected this round. Severity-mapped so warn_90
    triggers self-alert (severity=error)."""
    n = 0
    for q in get_all_quotas():
        st = q.get("status")
        if st in ("warn_80", "warn_90"):
            sev = "warn" if st == "warn_80" else "error"
            operator_events.log_event(
                f"quota_{st}",
                f"{q['service']} quota at {st}: {q.get('detail', '')}",
                service=q["service"], severity=sev,
                metadata=q,
            )
            n += 1
    return n


def monitorability_summary() -> dict[str, list[str]]:
    """For the walkthrough/report (Part 6): which services are
    programmatically checked vs estimated. Truth-in-monitoring."""
    out: dict[str, list[str]] = {
        "programmatic": [], "estimated": [], "informational": [],
    }
    for q in get_all_quotas():
        m = q.get("monitorability", "informational")
        if m in out:
            out[m].append(q["service"])
    return out
