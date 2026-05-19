"""Local Whisper transcription (openai-whisper, free, no API key).

PyTorch is heavy (~1 GB RAM). It is NOT in the main requirements.txt so
the core deploy stays light; install backend/requirements-audio.txt where
RAM allows. Import + model load are lazy and failure-tolerant: if whisper
or torch is unavailable, transcribe() returns ('', None) and the caller
still logs the complaint (e.g. "voice note received") instead of 500ing.
"""
from __future__ import annotations

import logging
import tempfile

from ..config import get_settings

log = logging.getLogger("aibuildcare.whisper")

_model = None
_load_failed = False


def available() -> bool:
    try:
        import whisper  # noqa: F401

        return True
    except Exception:
        return False


def _get_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    try:
        import whisper

        _model = whisper.load_model(get_settings().whisper_model)
    except Exception as exc:
        _load_failed = True
        log.warning("whisper unavailable; audio will not be transcribed: %s", exc)
    return _model


def transcribe(audio_bytes: bytes, ext: str = "ogg") -> tuple[str, str | None]:
    """Return (text, detected_language). ('', None) if unavailable."""
    model = _get_model()
    if model is None:
        return "", None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        result = model.transcribe(path, language=None)
        return (result.get("text", "").strip(), result.get("language"))
    except Exception as exc:  # pragma: no cover - runtime/env dependent
        log.warning("transcription failed: %s", exc)
        return "", None
