import logging
import re

from fastapi import APIRouter, Request

from ..config import get_settings
from ..integrations import r2_client
from ..services import complaint_service as svc
from ..services import (
    audio_transcriber,
    haiku_parser,
    media_intake,
    tts,
    vendor_directory,
)
from ..services.ws_hub import hub
from ..services.notify import (
    send_whatsapp,
    send_whatsapp_media,
    send_sms,
    send_email,
)

log = logging.getLogger("aibuildcare.webhooks")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TAG_RE = re.compile(r"<[^>]+>")

# E1b'': resident self-service vendor directory via WhatsApp.
# Trigger words must be EXPLICIT search intent; bare problem text
# (e.g. "AC kharab") stays a complaint.
_DIRECTORY_INTENT_RE = re.compile(
    r"\b(find|looking for|connect me to|vendor for|directory|"
    r"hire (?:a )?|recommend (?:a |me a )?)\b",
    re.IGNORECASE,
)


def _is_directory_request(text: str) -> bool:
    return bool(_DIRECTORY_INTENT_RE.search(text or ""))


def _inbound_society() -> int:
    """Which society an inbound (no-auth) WhatsApp/SMS/Form message
    belongs to. Until per-society inbound identifiers (Enterprise R1)
    land, everything defaults to the first society."""
    from ..db import get_conn

    try:
        with get_conn() as conn:
            r = conn.execute(
                "SELECT id FROM societies ORDER BY id LIMIT 1"
            ).fetchone()
            return dict(r)["id"] if r else 1
    except Exception:
        return 1


def _format_directory_reply(category: str, vendors: list[dict]) -> str:
    if not vendors:
        return (
            f"Sorry, no vetted {category} vendors are currently "
            f"available in your society. For a society-level issue "
            f"please describe the problem directly."
        )
    lines = [
        f"Here are vetted {category} vendors in your society "
        f"(tap a link to chat directly):"
    ]
    for i, v in enumerate(vendors[:5], 1):
        rating = (f"⭐ {v['average_rating']:.1f}"
                  if v.get("average_rating") is not None else "")
        link = v.get("wa_link") or v.get("phone") or "(no contact)"
        lines.append(f"{i}. {v['name']} {rating} — {link}")
    lines.append(
        "\n(For a society/common-area issue, describe the problem "
        "and we'll log it as a complaint.)"
    )
    return "\n".join(lines)


def _email_addr(raw: str) -> str:
    """'Name <a@b.com>' / 'a@b.com' -> 'a@b.com' (or '')."""
    m = _EMAIL_RE.search(raw or "")
    return m.group(0) if m else ""


def _strip_html(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html or "")).strip()

router = APIRouter(tags=["webhooks"])


def _with_audio(body: str, audio: list[tuple[bytes, str]]) -> str:
    """Append any transcribed voice notes to the text body."""
    parts = [body] if body else []
    for data, ctype in audio:
        ext = ctype.split("/")[-1] or "ogg"
        text, _lang = audio_transcriber.transcribe(data, ext)
        if text:
            parts.append(text)
        elif not parts:
            parts.append("[voice note received - transcription unavailable]")
    return " ".join(p for p in parts if p).strip()


def _voice_reply_mode() -> str:
    """Society-configurable policy; resilient (never degrades intake)."""
    try:
        from ..services import system_config

        return system_config.get_config(
            "whatsapp_voice_reply_mode", "on_audio"
        )
    except Exception:
        return "on_audio"


def _maybe_voice_reply(
    phone: str, c: dict, inbound_had_audio: bool
) -> None:
    """Best-effort: voice the ack via Sarvam TTS -> R2 -> WhatsApp media.
    Every failure is swallowed; the text ack was already sent.

    Gated by a global env kill-switch, then the society's
    whatsapp_voice_reply_mode (off / on_audio / always)."""
    if not get_settings().whatsapp_voice_reply_enabled:
        return
    mode = _voice_reply_mode()
    if mode == "off":
        return
    if mode == "on_audio" and not inbound_had_audio:
        return  # resident sent text -> reply text only
    try:
        out = tts.synthesize(c["acknowledgement"], c.get("detected_language"))
        if not out:
            return
        data, ext, ctype = out
        url = r2_client.upload_bytes(data, ctype, f".{ext}")
        if not url:
            return
        send_whatsapp_media(phone, url)
    except Exception as exc:  # never break the webhook response
        log.warning("voice reply skipped: %s", exc)


@router.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp(request: Request) -> dict:
    form = dict(await request.form())
    phone = str(form.get("From", "")).replace("whatsapp:", "").strip()
    body = str(form.get("Body", ""))
    images, audio = media_intake.extract_twilio_media(form)
    text = _with_audio(body, audio) or "[media received]"

    # E1b'': resident self-service vendor directory short-circuits
    # complaint creation when the user explicitly asked us to FIND a
    # vendor (e.g. "looking for a carpenter for my flat").
    if phone and _is_directory_request(text):
        cat = haiku_parser._classify(text)
        if cat != "Other":
            vendors = vendor_directory.list_vendors(
                _inbound_society(), cat
            )
            send_whatsapp(phone, _format_directory_reply(cat, vendors))
            return {"ok": True, "directory": True, "category": cat,
                    "vendor_count": len(vendors)}

    c = svc.create_complaint(
        text, channel="whatsapp", reporter_phone=phone, image_urls=images
    )
    await hub.broadcast("complaint.created", c)
    if phone:
        send_whatsapp(phone, c["acknowledgement"])
        _maybe_voice_reply(phone, c, inbound_had_audio=bool(audio))
    return {"ok": True, "ticket": c["ticket_number"]}


@router.post("/webhooks/twilio/sms")
async def twilio_sms(request: Request) -> dict:
    form = dict(await request.form())
    phone = str(form.get("From", "")).strip()
    body = str(form.get("Body", ""))
    images, audio = media_intake.extract_twilio_media(form)
    text = _with_audio(body, audio) or "[media received]"
    c = svc.create_complaint(
        text, channel="sms", reporter_phone=phone, image_urls=images
    )
    await hub.broadcast("complaint.created", c)
    if phone:
        send_sms(phone, c["acknowledgement"])
    return {"ok": True, "ticket": c["ticket_number"]}


@router.post("/webhooks/forms")
async def google_form(request: Request) -> dict:
    """Google Forms -> Apps Script -> here. Accepts JSON or form-encoded
    {raw_text, phone}. No JWT (Apps Script can't mint one)."""
    raw_text = ""
    phone = None
    try:
        payload = await request.json()
    except Exception:
        payload = dict(await request.form())
    raw_text = str(payload.get("raw_text") or payload.get("description") or "")
    phone = (payload.get("phone") or payload.get("reporter_phone") or None)
    c = svc.create_complaint(
        raw_text or "[empty form submission]",
        channel="form",
        reporter_phone=str(phone).strip() if phone else None,
    )
    await hub.broadcast("complaint.created", c)
    return {"ok": True, "ticket": c["ticket_number"]}


async def _handle_inbound_email(request: Request) -> dict:
    """Shared SendGrid Inbound Parse handler."""
    form = dict(await request.form())
    sender = _email_addr(str(form.get("from", "")))
    subject = str(form.get("subject", "")).strip()
    body = str(form.get("text", "")).strip()
    if not body:
        body = _strip_html(str(form.get("html", "")))
    # subject often carries the gist (e.g. "5B AC kharab hai")
    raw = (f"{subject}. {body}" if subject and body else subject or body
           or "[email with no body]")
    c = svc.create_complaint(raw, channel="email", reporter_email=sender)
    await hub.broadcast("complaint.created", c)
    if sender:
        lines = [c["acknowledgement"], "", f"Ticket: {c['ticket_number']}"]
        if c.get("contractor_id"):
            con = svc.get_contractor(c["contractor_id"])
            if con:
                lines.append(f"Assigned to: {con['name']}")
        if c.get("estimated_completion_date"):
            lines.append(
                f"Estimated completion: {c['estimated_completion_date']}"
            )
        if not c.get("unit_number"):
            lines.append(
                "Note: please reply with your unit number so we can "
                "locate the issue faster."
            )
        send_email(
            sender,
            f"Re: Your Complaint {c['ticket_number']} Received",
            "\n".join(lines),
        )
    return {"ok": True, "ticket": c["ticket_number"]}


@router.post("/webhooks/sendgrid/email")
async def sendgrid_email(request: Request) -> dict:
    return await _handle_inbound_email(request)


@router.post("/webhooks/sendgrid/inbound-email")
async def sendgrid_inbound(request: Request) -> dict:
    # backwards-compatible alias
    return await _handle_inbound_email(request)
