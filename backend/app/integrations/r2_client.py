"""Cloudflare R2 (S3-compatible) media storage.

Used to persist complaint photos so Claude's vision can fetch them by
public URL and the dashboard can display them. Twilio media URLs expire
and require auth, so we re-host. If R2 is not configured the helpers
no-op (return None) and the caller still creates the ticket.
"""
from __future__ import annotations

import logging
import uuid

from ..config import get_settings

log = logging.getLogger("aibuildcare.r2")


def is_configured() -> bool:
    s = get_settings()
    return bool(
        s.r2_endpoint_url
        and s.r2_access_key_id
        and s.r2_secret_access_key
        and s.r2_public_base_url
    )


def _client():
    import boto3

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        region_name="auto",
    )


def upload_bytes(data: bytes, content_type: str, ext: str = "") -> str | None:
    """Upload bytes, return a public URL, or None if R2 is unconfigured
    or the upload fails (never raises - media must not break intake)."""
    if not is_configured():
        log.info("R2 not configured; skipping media upload (%d bytes)", len(data))
        return None
    s = get_settings()
    key = f"complaints/{uuid.uuid4().hex}{ext}"
    try:
        _client().put_object(
            Bucket=s.r2_bucket,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        return f"{s.r2_public_base_url.rstrip('/')}/{key}"
    except Exception as exc:  # pragma: no cover - network failure path
        log.warning("R2 upload failed: %s", exc)
        # Visible in the diagnostics tile / event log; complaint still
        # gets created (media just won't render).
        try:
            from ..services import operator_events
            operator_events.log_event(
                "external_call_failed",
                f"R2 upload failed ({len(data)} bytes): "
                f"{type(exc).__name__}: {exc}",
                service="r2", severity="error",
                metadata={"exc_type": type(exc).__name__,
                          "exc_str": str(exc)[:300],
                          "key": key,
                          "size_bytes": len(data)},
            )
        except Exception:
            pass
        return None
