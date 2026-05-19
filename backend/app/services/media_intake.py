"""Pull media off inbound webhooks.

Twilio posts NumMedia + MediaUrl{i} + MediaContentType{i}. Media URLs
require the account's basic auth and expire, so we download immediately,
re-host images on R2 (public URL for Claude vision + dashboard) and hand
audio bytes to the transcriber.
"""
from __future__ import annotations

import logging

import httpx

from ..config import get_settings
from ..integrations import r2_client

log = logging.getLogger("aibuildcare.media")

_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/amr": ".amr",
}


def _download(url: str) -> tuple[bytes, str] | None:
    s = get_settings()
    auth = None
    if "twilio.com" in url and s.twilio_account_sid:
        auth = (s.twilio_account_sid, s.twilio_auth_token)
    try:
        r = httpx.get(url, auth=auth, follow_redirects=True, timeout=30)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "").split(";")[0]
    except Exception as exc:  # media must never break intake
        log.warning("media download failed (%s): %s", url, exc)
        return None


def extract_twilio_media(
    form: dict,
) -> tuple[list[str], list[tuple[bytes, str]]]:
    """Return (image_public_urls, [(audio_bytes, content_type), ...])."""
    try:
        n = int(form.get("NumMedia", "0") or "0")
    except ValueError:
        n = 0
    images: list[str] = []
    audio: list[tuple[bytes, str]] = []
    for i in range(n):
        url = form.get(f"MediaUrl{i}")
        ctype = (form.get(f"MediaContentType{i}") or "").lower()
        if not url:
            continue
        got = _download(url)
        if not got:
            continue
        data, real_ct = got
        ctype = ctype or real_ct
        if ctype.startswith("image/"):
            public = r2_client.upload_bytes(
                data, ctype, _EXT.get(ctype, ".jpg")
            )
            if public:
                images.append(public)
        elif ctype.startswith("audio/"):
            audio.append((data, ctype))
    return images, audio
