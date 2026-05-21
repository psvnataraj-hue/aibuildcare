"""Diagnostics endpoints (Part 4).

Three endpoints behind /api/v1/diagnostics:

  GET  /health    — at-a-glance health for the dashboard tile.
                    Public-ish: returns coarse status without secrets.
                    Used by Sravya during testing + Nataraj during ops.

  GET  /events    — operator-event log tail (auth required).
                    Filters: ?severity=, ?service=, ?since_minutes=,
                    ?unseen_only=true, ?limit=N.

  GET  /quotas    — full quota-monitor report (auth required).
                    Includes the monitorability summary so the operator
                    can tell at a glance which services are
                    programmatically checked vs estimated.

  POST /events/seen   — mark events as seen by id list (auth required).

  POST /trigger-tick  — Part 5-2: tester-only manual cron trigger on
                        demo tenants for fast escalation verification.

The legacy GET /health endpoint (at the root, returning {"status":"ok"})
stays for backwards compatibility with Render's wakeup pings; this new
/api/v1/diagnostics/health is the rich version.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..deps import current_user
from ..services import diagnostics as diag
from ..services import operator_events, quota_monitor, jobs_service

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])
log = logging.getLogger("aibuildcare.diagnostics_router")


@router.get("/health")
def get_health(user: dict | None = Depends(current_user)) -> dict:
    """At-a-glance health. Available to any authenticated user — Sravya
    sees the same dashboard the operator does, which is the point: she
    can self-diagnose 'is it me or the system?' during live testing
    without needing to ping Nataraj."""
    return diag.get_health_status()


@router.get("/events")
def get_events(
    limit: int = Query(default=100, ge=1, le=1000),
    severity: str | None = Query(default=None),
    service: str | None = Query(default=None),
    since_minutes: int | None = Query(default=None, ge=1),
    unseen_only: bool = Query(default=False),
    user: dict = Depends(current_user),
) -> dict:
    """Operator-event log tail. society_id-scoped: a tenant secretary
    only sees their own society's events (society_id IS NULL events
    are system-wide and visible to all)."""
    events = operator_events.recent_events(
        limit=limit, severity=severity, service=service,
        since_minutes=since_minutes, unseen_only=unseen_only,
    )
    # Tenant scoping: a non-admin sees only events for their society or
    # global ones. Admin sees all (and we accept that admin has
    # cross-tenant reach per finding 001 — flagged for separate fix).
    if user.get("role") != "admin":
        own_sid = user.get("society_id")
        events = [e for e in events
                  if e.get("society_id") in (None, own_sid)]
    return {"events": events, "count": len(events)}


class _MarkSeenBody(BaseModel):
    event_ids: list[int]


@router.post("/events/seen")
def mark_events_seen(
    body: _MarkSeenBody,
    user: dict = Depends(current_user),
) -> dict:
    n = operator_events.mark_seen(body.event_ids)
    return {"marked_seen": n}


@router.get("/quotas")
def get_quotas(user: dict = Depends(current_user)) -> dict:
    """Full quota-monitor report. Includes monitorability summary so the
    operator can see honestly which services are programmatic vs
    estimated."""
    return {
        "quotas": quota_monitor.get_all_quotas(),
        "monitorability_summary": quota_monitor.monitorability_summary(),
    }


@router.post("/trigger-tick")
def trigger_tick_manually(
    user: dict = Depends(current_user),
) -> dict:
    """Part 5-2: tester-only manual escalation-check trigger.

    Scoping: only works for users on DEMO societies (is_demo=1). Refuses
    for non-demo tenants — the real Palms cron is fired by cron-job.org
    on its schedule, never by a manual endpoint. Lets Sravya verify
    escalation in seconds instead of waiting for the 15-min cron cadence.

    Defense in depth: even if a real-tenant user somehow reaches this
    endpoint, the is_demo check refuses it. Cron job itself is
    idempotent (status-based skip) so even a misfire is harmless on
    historical data."""
    sid = user.get("society_id")
    if sid is None:
        raise HTTPException(403, "no society")

    # Verify this society is_demo=1
    from ..db import get_conn
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT is_demo FROM societies WHERE id = ?", (sid,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "society not found")
            is_demo = (dict(row) if not isinstance(row, dict) else row).get("is_demo", 0)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"society lookup failed: {exc}")

    if not is_demo:
        raise HTTPException(
            403,
            "trigger-tick is only available on demo tenants — the real "
            "cron schedule on production tenants must not be advanced by a "
            "manual call.",
        )

    # Run synchronously so the tester sees the result immediately.
    # The tick is fast (few hundred ms typically) so this is fine.
    try:
        summary = jobs_service.run_tick()
        operator_events.log_event(
            "manual_tick_triggered",
            f"manual /trigger-tick by user on demo sid={sid}",
            service="cron", severity="info",
            metadata={"summary": summary, "triggered_by_user_id": user.get("id")},
            society_id=sid,
        )
        return {"status": "ok", "summary": summary}
    except Exception as exc:
        raise HTTPException(500, f"tick failed: {exc}")
