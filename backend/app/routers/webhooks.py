from fastapi import APIRouter, Form, Request

from ..services import complaint_service as svc
from ..services.ws_hub import hub
from ..services.notify import send_whatsapp, send_sms, send_email

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp(
    From: str = Form(default=""), Body: str = Form(default="")
) -> dict:
    phone = From.replace("whatsapp:", "").strip()
    c = svc.create_complaint(Body, channel="whatsapp", reporter_phone=phone)
    await hub.broadcast("complaint.created", c)
    if phone:
        send_whatsapp(phone, c["acknowledgement"])
    return {"ok": True, "ticket": c["ticket_number"]}


@router.post("/webhooks/twilio/sms")
async def twilio_sms(
    From: str = Form(default=""), Body: str = Form(default="")
) -> dict:
    c = svc.create_complaint(Body, channel="sms", reporter_phone=From.strip())
    await hub.broadcast("complaint.created", c)
    if From:
        send_sms(From.strip(), c["acknowledgement"])
    return {"ok": True, "ticket": c["ticket_number"]}


@router.post("/webhooks/sendgrid/inbound-email")
async def sendgrid_inbound(request: Request) -> dict:
    form = await request.form()
    sender = str(form.get("from", "")).strip()
    text = str(form.get("text") or form.get("subject") or "")
    c = svc.create_complaint(text, channel="email", reporter_email=sender)
    await hub.broadcast("complaint.created", c)
    if sender:
        send_email(sender, f"Complaint {c['ticket_number']}",
                   c["acknowledgement"])
    return {"ok": True, "ticket": c["ticket_number"]}
