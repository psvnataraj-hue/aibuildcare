"""Text-to-Speech via Sarvam AI (bulbul) for the WhatsApp voice reply.

Returns MP3 bytes (audio/mpeg) so the audio flows straight to WhatsApp
via Twilio media with NO transcoding (Render free tier has no ffmpeg;
WhatsApp accepts audio/mpeg natively).

Graceful by contract: every failure path returns None so the caller
still sends the plain-text acknowledgement.
"""
from __future__ import annotations

import base64
import logging

from ..config import get_settings

log = logging.getLogger("aibuildcare.tts")

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

# The Haiku parser stores detected_language as an English word.
_WORD_TO_BCP47 = {
    "english": "en-IN", "hindi": "hi-IN", "hinglish": "hi-IN",
    "marathi": "mr-IN", "gujarati": "gu-IN", "punjabi": "pa-IN",
    "kannada": "kn-IN", "tamil": "ta-IN", "telugu": "te-IN",
    "malayalam": "ml-IN", "bengali": "bn-IN", "odia": "od-IN",
}
# Whisper (fallback STT) yields ISO-639-1 codes instead.
_ISO2_TO_BCP47 = {
    "en": "en-IN", "hi": "hi-IN", "mr": "mr-IN", "gu": "gu-IN",
    "pa": "pa-IN", "kn": "kn-IN", "ta": "ta-IN", "te": "te-IN",
    "ml": "ml-IN", "bn": "bn-IN", "or": "od-IN", "od": "od-IN",
}
_SUPPORTED = set(_WORD_TO_BCP47.values())
_DEFAULT = "en-IN"
# Sarvam v2 caps text at 1500 chars; acks are short, keep margin.
_MAX_CHARS = 1000


def to_bcp47(detected: str | None) -> str:
    """Normalise a stored language label to a Sarvam BCP-47 code.

    Accepts the parser's English word ('hindi'), a Whisper ISO-2 code
    ('hi'), or an already-BCP-47 tag ('hi-IN'). Unknown -> en-IN.
    """
    if not detected:
        return _DEFAULT
    key = detected.strip().lower()
    if key in _WORD_TO_BCP47:
        return _WORD_TO_BCP47[key]
    if "-" in key:  # e.g. 'hi-in' -> 'hi-IN'
        norm = key.split("-")[0] + "-IN"
        if norm in _SUPPORTED:
            return norm
    if key in _ISO2_TO_BCP47:
        return _ISO2_TO_BCP47[key]
    return _DEFAULT


def available() -> bool:
    return bool(get_settings().sarvam_api_key)


def synthesize(
    text: str, detected_language: str | None = None
) -> tuple[bytes, str, str] | None:
    """Synthesize speech. Returns (mp3_bytes, ext, content_type) or None.

    None on any failure (no key, empty text, network, bad response) so
    the caller falls back to the text-only acknowledgement.
    """
    s = get_settings()
    if not s.sarvam_api_key:
        return None
    text = (text or "").strip()
    if not text:
        return None
    try:
        import httpx

        r = httpx.post(
            SARVAM_TTS_URL,
            headers={"api-subscription-key": s.sarvam_api_key},
            json={
                "text": text[:_MAX_CHARS],
                "target_language_code": to_bcp47(detected_language),
                "model": s.sarvam_tts_model,
                "speaker": s.sarvam_tts_speaker,
                "output_audio_codec": "mp3",
            },
            timeout=60,
        )
        r.raise_for_status()
        audios = r.json().get("audios") or []
        if not audios:
            log.warning("Sarvam TTS returned no audio")
            return None
        return (base64.b64decode(audios[0]), "mp3", "audio/mpeg")
    except Exception as exc:  # never break the ack path
        log.warning("Sarvam TTS failed: %s", exc)
        return None
