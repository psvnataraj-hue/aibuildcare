"""Outbound notifications. No-ops gracefully when provider keys are absent
so the complaint flow never fails on a delivery problem."""
import logging

from ..config import get_settings

log = logging.getLogger("aibuildcare.notify")


def send_whatsapp(to_phone: str, body: str) -> bool:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        log.info("twilio not configured; would WhatsApp %s: %s", to_phone, body)
        return False
    try:
        from twilio.rest import Client

        client = Client(s.twilio_account_sid, s.twilio_auth_token)
        wa_from = (
            f"whatsapp:{s.twilio_whatsapp_number}"
            if s.twilio_whatsapp_number
            else s.twilio_whatsapp_from
        )
        client.messages.create(
            from_=wa_from,
            to=f"whatsapp:{to_phone}",
            body=body,
        )
        return True
    except Exception as exc:  # delivery failure must not break intake
        log.warning("whatsapp send failed: %s", exc)
        return False


def send_whatsapp_media(
    to_phone: str, media_url: str, body: str = ""
) -> bool:
    """Send a WhatsApp message carrying media (e.g. an MP3 voice note).
    media_url must be publicly fetchable by Twilio (R2 public URL)."""
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        log.info(
            "twilio not configured; would WhatsApp media %s: %s",
            to_phone, media_url,
        )
        return False
    try:
        from twilio.rest import Client

        client = Client(s.twilio_account_sid, s.twilio_auth_token)
        wa_from = (
            f"whatsapp:{s.twilio_whatsapp_number}"
            if s.twilio_whatsapp_number
            else s.twilio_whatsapp_from
        )
        client.messages.create(
            from_=wa_from,
            to=f"whatsapp:{to_phone}",
            body=body,
            media_url=[media_url],
        )
        return True
    except Exception as exc:  # media delivery must not break intake
        log.warning("whatsapp media send failed: %s", exc)
        return False


def send_sms(to_phone: str, body: str) -> bool:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        log.info("twilio not configured; would SMS %s: %s", to_phone, body)
        return False
    try:
        from twilio.rest import Client

        client = Client(s.twilio_account_sid, s.twilio_auth_token)
        sms_from = (
            s.twilio_sms_number
            or s.twilio_whatsapp_number
            or s.twilio_whatsapp_from.replace("whatsapp:", "")
        )
        client.messages.create(
            from_=sms_from,
            to=to_phone,
            body=body,
        )
        return True
    except Exception as exc:
        log.warning("sms send failed: %s", exc)
        return False


def send_email(to_email: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not s.sendgrid_api_key:
        log.info("sendgrid not configured; would email %s", to_email)
        return False
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        msg = Mail(
            from_email=s.sendgrid_from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
        )
        SendGridAPIClient(s.sendgrid_api_key).send(msg)
        return True
    except Exception as exc:
        log.warning("email send failed: %s", exc)
        return False
