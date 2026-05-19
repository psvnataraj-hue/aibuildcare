"""Manager-configurable runtime settings (system_config table)."""
from __future__ import annotations

from datetime import datetime, timezone

from ..db import get_conn

DEFAULTS = {
    "max_pending_jobs_per_contractor": "10",
    "load_balancing_enabled": "true",
    # Comma-separated language codes for the staff-facing complaint
    # summary the parser generates. Default Hindi; a society can set
    # e.g. "en,hi,mr" to get all three. No code/migration needed.
    "official_summary_languages": "hi",
    # WhatsApp voice-note reply policy:
    #   off       -> text acknowledgement only
    #   on_audio  -> also send a voice note ONLY when the resident's
    #                complaint itself contained an audio note (mirror)
    #   always    -> always send text + voice note
    "whatsapp_voice_reply_mode": "on_audio",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def all_config() -> dict[str, str]:
    out = dict(DEFAULTS)
    with get_conn() as conn:
        for r in conn.execute(
            "SELECT config_key, config_value FROM system_config"
        ).fetchall():
            d = dict(r)
            out[d["config_key"]] = d["config_value"]
    return out


def get_config(key: str, default: str | None = None) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT config_value FROM system_config WHERE config_key = ?",
            (key,),
        ).fetchone()
    if row:
        return dict(row)["config_value"]
    return DEFAULTS.get(key, default)


def get_int(key: str, default: int) -> int:
    try:
        return int(get_config(key, str(default)))
    except (TypeError, ValueError):
        return default


def get_bool(key: str, default: bool = False) -> bool:
    v = get_config(key, "true" if default else "false")
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def set_config(key: str, value: str) -> dict:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM system_config WHERE config_key = ?", (key,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE system_config SET config_value = ?, updated_at = ? "
                "WHERE config_key = ?",
                (str(value), _now(), key),
            )
        else:
            conn.execute(
                "INSERT INTO system_config (config_key, config_value, "
                "updated_at) VALUES (?,?,?)",
                (key, str(value), _now()),
            )
    return {"config_key": key, "config_value": str(value)}
