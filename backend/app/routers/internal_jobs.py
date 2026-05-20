"""Internal cron endpoint (E2).

A free external cron caller (cron-job.org / UptimeRobot / Render Cron)
sends POST /internal/jobs/tick with header ``X-Internal-Secret``. The
endpoint is disabled (503) until ``AIBUILDCARE_INTERNAL_JOBS_SECRET``
is set on Render — this prevents the path from being usable in dev or
during accidental public deploys.

Hardening (Gemini audit fixes):
  - ``secrets.compare_digest()`` to defeat timing-attack secret guessing
  - returns 202 + spawns ``run_tick()`` via ``BackgroundTasks`` so
    Render's ~30 s HTTP timeout cannot truncate a slow tick. Per-tick
    job stats now go to logs (and a future admin endpoint) rather
    than the response body.
"""
import logging
import secrets

from fastapi import (
    APIRouter, BackgroundTasks, Depends, Header, HTTPException, status,
)

from ..config import get_settings
from ..services import jobs_service

router = APIRouter(prefix="/internal/jobs", tags=["internal-jobs"])
log = logging.getLogger("aibuildcare.jobs")


def _check_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    cfg = get_settings().internal_jobs_secret
    if not cfg:
        raise HTTPException(503, "internal jobs not configured")
    if not secrets.compare_digest(x_internal_secret or "", cfg):
        raise HTTPException(403, "invalid secret")


def _safe_run_tick() -> None:
    """B1 follow-up: defense-in-depth outer guard.

    ``run_tick`` already has a per-job try/except, but anything that
    raises *before* that loop (an ``ImportError`` on its deferred
    sub-imports, a connection-pool exhaustion at module load, etc.)
    would crash the background task with no visible signal — FastAPI's
    BackgroundTasks swallows exceptions and the cron pinger sees 202
    regardless. Wrapping here guarantees a single ``log.exception`` if
    that ever happens, so ops can grep ``tick crashed`` to spot it."""
    try:
        jobs_service.run_tick()
    except Exception:
        log.exception("tick crashed")


@router.post(
    "/tick",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_check_secret)],
)
def tick(background_tasks: BackgroundTasks) -> dict:
    """Queue all due jobs asynchronously; return 202 immediately.

    Each job is idempotent + self-throttled by DB state, so it is safe
    to spawn-and-forget. Per-tick rollup is logged by
    ``jobs_service.run_tick`` (``log.info('tick complete: ...')``);
    top-level crashes are caught by ``_safe_run_tick``."""
    background_tasks.add_task(_safe_run_tick)
    return {"status": "accepted"}
