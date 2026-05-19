"""Audio transcription.

Order of preference:
  1. Sarvam AI Speech-to-Text (saarika) - best accuracy for the 9
     major Indian languages + Hinglish code-mixing. Cloud API, no RAM
     cost, works on Render free. Enabled when AIBUILDCARE_SARVAM_API_KEY
     is set.
  2. Local Whisper (openai-whisper) - free, but PyTorch is heavy
     (~1 GB RAM); only where requirements-audio.txt is installed.
  3. Graceful no-op - returns ('', None) so the caller still logs the
     complaint ("voice note received") instead of 500ing.
"""
from __future__ import annotations

import logging
import tempfile

from ..config import get_settings

log = logging.getLogger("aibuildcare.audio")

_model = None
_load_failed = False

SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
_CT = {
    "ogg": "audio/ogg", "opus": "audio/ogg", "mp3": "audio/mpeg",
    "m4a": "audio/mp4", "mp4": "audio/mp4", "amr": "audio/amr",
    "wav": "audio/wav", "flac": "audio/flac", "webm": "audio/webm",
}


def available() -> bool:
    if get_settings().sarvam_api_key:
        return True
    try:
        import whisper  # noqa: F401

        return True
    except Exception:
        return False


def _sarvam(audio_bytes: bytes, ext: str) -> tuple[str, str | None] | None:
    """Return (text, lang) via Sarvam, or None to fall through."""
    s = get_settings()
    if not s.sarvam_api_key:
        return None
    try:
        import httpx

        files = {
            "file": (
                f"audio.{ext}",
                audio_bytes,
                _CT.get(ext, "application/octet-stream"),
            )
        }
        data = {
            "model": s.sarvam_model,
            "language_code": "unknown",  # auto-detect Indian languages
            "mode": "transcribe",
        }
        r = httpx.post(
            SARVAM_URL,
            headers={"api-subscription-key": s.sarvam_api_key},
            files=files,
            data=data,
            timeout=60,
        )
        r.raise_for_status()
        j = r.json()
        return (j.get("transcript", "").strip(), j.get("language_code"))
    except Exception as exc:
        log.warning("Sarvam transcription failed: %s", exc)
        return ("", None)


def _get_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    try:
        import whisper

        _model = whisper.load_model(get_settings().whisper_model)
    except Exception as exc:
        _load_failed = True
        log.warning("whisper unavailable: %s", exc)
    return _model


def transcribe(audio_bytes: bytes, ext: str = "ogg") -> tuple[str, str | None]:
    """Return (text, detected_language). ('', None) if unavailable."""
    via_sarvam = _sarvam(audio_bytes, ext)
    if via_sarvam is not None:
        return via_sarvam
    model = _get_model()
    if model is None:
        return "", None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=f".{ext}", delete=False
        ) as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        result = model.transcribe(path, language=None)
        return (result.get("text", "").strip(), result.get("language"))
    except Exception as exc:  # pragma: no cover - env dependent
        log.warning("whisper transcription failed: %s", exc)
        return "", None
