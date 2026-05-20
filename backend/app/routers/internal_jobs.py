"""Internal cron endpoint (E2).

A free external cron caller (cron-job.org / UptimeRobot / Render Cron)
sends POST /internal/jobs/tick with header `X-Internal-Secret`. The
endpoint is disabled (503) until AIBUILDCARE_INTERNAL_JOBS_SECRET is
set on Render — this prevents the path from being usable in dev or
during accidental public deploys.
"""
from fastapi import APIRouter, Depends, Header, HTTPException

from ..config import get_settings
from ..services import jobs_service

router = APIRouter(prefix="/internal/jobs", tags=["internal-jobs"])


def _check_secret(
    x_internal_secret: str | None = Header(default=None),
) -> None:
    secret = get_settings().internal_jobs_secret
    if not secret:
        raise HTTPException(503, "internal jobs not configured")
    if x_internal_secret != secret:
        raise HTTPException(403, "invalid secret")


@router.post("/tick", dependencies=[Depends(_check_secret)])
def tick() -> dict:
    """Run all due jobs. Safe to call any frequency >= a few minutes;
    each job is idempotent."""
    return jobs_service.run_tick()
