import re

from fastapi import APIRouter, Request

from ..services import complaint_service as svc
from ..services import audio_transcriber, media_intake
from ..services.ws_hub import hub
from ..services.notify import send_whatsapp, send_sms, send_email

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TAG_RE = re.compile(r"<[^>]+>")


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


@router.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp(request: Request) -> dict:
    form = dict(await request.form())
    phone = str(form.get("From", "")).replace("whatsapp:", "").strip()
    body = str(form.get("Body", ""))
    images, audio = media_intake.extract_twilio_media(form)
    text = _with_audio(body, audio) or "[media received]"
    c = svc.create_complaint(
        text, channel="whatsapp", reporter_phone=phone, image_urls=images
    )
    await hub.broadcast("complaint.created", c)
    if phone:
        send_whatsapp(phone, c["acknowledgement"])
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
