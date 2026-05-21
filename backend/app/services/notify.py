"""Outbound notifications.

Single chokepoint for every WhatsApp / SMS / email send. Layered guards:

  1. ★ SEEDING_LOCK (Part 0-B Layer 3). If AIBUILDCARE_SEEDING_LOCK=1,
     ALL outbound sends become operator-logged no-ops. Used while seeding
     synthetic historical complaints to guarantee no message flood.

  2. ★ TEST-PHONE SKIP (Part 0-B Layer 2). Phone numbers matching the
     reserved test-range prefixes (default `+919900` — covers the entire
     +91 99000 XXXXX block used by synthetic-data Part 2) short-circuit
     to a logged operator event with no Twilio call attempted.
     Env-overridable via AIBUILDCARE_TEST_PHONE_PREFIXES (comma-separated).

  3. Graceful no-op when provider keys are absent. Pre-existing behaviour.

  4. Try/except wrapping every actual provider call. Failure logs an
     operator event with severity=error, returns False, never raises.

Operator-events written here:

    test_phone_skipped            (severity=info)    — Layer 2 short-circuit
    seeding_lock_active           (severity=info)    — Layer 3 short-circuit
    external_call_succeeded       (severity=info)    — successful send
    external_call_failed          (severity=error)   — provider raised
    external_call_no_credentials  (severity=warn)    — env var missing

The function signatures and return shapes are unchanged from the
pre-Part-4 version — every caller in the codebase keeps working.
"""

from __future__ import annotations

import logging
import os

from ..config import get_settings
from . import operator_events

log = logging.getLogger("aibuildcare.notify")


_DEFAULT_TEST_PHONE_PREFIXES = "+919900"


def _test_phone_prefixes() -> tuple[str, ...]:
    """Resolve from env var, comma-separated. Falls back to the +91 99000
    block (which covers the +91 99000 XXXXX synthetic-data test range)."""
    raw = os.getenv("AIBUILDCARE_TEST_PHONE_PREFIXES") or _DEFAULT_TEST_PHONE_PREFIXES
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def _is_test_phone(to: str) -> bool:
    """True if `to` is in the reserved test range. Operator log will tag
    the event so it's visible in the diagnostics tile."""
    return any(to.startswith(p) for p in _test_phone_prefixes())


def _seeding_lock_active() -> bool:
    """Layer 3 cron-safety guard. When AIBUILDCARE_SEEDING_LOCK=1 every
    outbound send short-circuits — used during the seed-and-verify
    window to prevent any accidental message flood."""
    return os.getenv("AIBUILDCARE_SEEDING_LOCK", "") == "1"


def _short_circuit(
    kind: str, service: str, to: str, body_or_subject: str,
) -> bool:
    """Common skip path. Logs to operator_events + stdlib logger,
    returns False (no-send). `kind` is one of:
        'seeding_lock', 'test_phone', 'no_credentials'."""
    if kind == "seeding_lock":
        operator_events.log_event(
            "seeding_lock_active",
            f"{service} send skipped — AIBUILDCARE_SEEDING_LOCK active",
            service=service, severity="info",
            metadata={"to": to, "body_preview": body_or_subject[:120]},
        )
        log.info("[seeding-lock] %s send skipped to %s", service, to)
    elif kind == "test_phone":
        operator_events.log_event(
            "test_phone_skipped",
            f"{service} send skipped — recipient {to} in test range",
            service=service, severity="info",
            metadata={"to": to, "body_preview": body_or_subject[:120]},
        )
        log.info("[test-phone] %s send skipped to %s", service, to)
    elif kind == "no_credentials":
        operator_events.log_event(
            "external_call_no_credentials",
            f"{service} not configured; send to {to} skipped",
            service=service, severity="warn",
            metadata={"to": to},
        )
        log.info("[no-credentials] %s skipped to %s", service, to)
    return False


def _log_success(service: str, to: str, kind: str) -> None:
    operator_events.log_event(
        "external_call_succeeded",
        f"{service} {kind} sent to {to}",
        service=service, severity="info",
        metadata={"to": to, "kind": kind},
    )


def _log_failure(service: str, to: str, kind: str, exc: Exception) -> None:
    operator_events.log_event(
        "external_call_failed",
        f"{service} {kind} send to {to} failed: {type(exc).__name__}: {exc}",
        service=service, severity="error",
        metadata={"to": to, "kind": kind, "exc_type": type(exc).__name__,
                  "exc_str": str(exc)[:300]},
    )


def send_whatsapp(to_phone: str, body: str) -> bool:
    if _seeding_lock_active():
        return _short_circuit("seeding_lock", "twilio", to_phone, body)
    if _is_test_phone(to_phone):
        return _short_circuit("test_phone", "twilio", to_phone, body)

    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        return _short_circuit("no_credentials", "twilio", to_phone, body)

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
        _log_success("twilio", to_phone, "whatsapp")
        return True
    except Exception as exc:
        _log_failure("twilio", to_phone, "whatsapp", exc)
        log.warning("whatsapp send failed: %s", exc)
        return False


def send_whatsapp_media(to_phone: str, media_url: str, body: str = "") -> bool:
    if _seeding_lock_active():
        return _short_circuit("seeding_lock", "twilio", to_phone, media_url)
    if _is_test_phone(to_phone):
        return _short_circuit("test_phone", "twilio", to_phone, media_url)

    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        return _short_circuit("no_credentials", "twilio", to_phone, media_url)

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
        _log_success("twilio", to_phone, "whatsapp_media")
        return True
    except Exception as exc:
        _log_failure("twilio", to_phone, "whatsapp_media", exc)
        log.warning("whatsapp media send failed: %s", exc)
        return False


def send_sms(to_phone: str, body: str) -> bool:
    if _seeding_lock_active():
        return _short_circuit("seeding_lock", "twilio", to_phone, body)
    if _is_test_phone(to_phone):
        return _short_circuit("test_phone", "twilio", to_phone, body)

    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        return _short_circuit("no_credentials", "twilio", to_phone, body)

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
        _log_success("twilio", to_phone, "sms")
        return True
    except Exception as exc:
        _log_failure("twilio", to_phone, "sms", exc)
        log.warning("sms send failed: %s", exc)
        return False


def send_email(to_email: str, subject: str, body: str) -> bool:
    if _seeding_lock_active():
        return _short_circuit("seeding_lock", "sendgrid", to_email, subject)
    # Email addresses don't use the +91 99000 test range; instead we
    # treat anything ending in @aibuildcare.app's reserved subdomain
    # @example.invalid (RFC 2606 reserved) as a test address.
    if to_email.endswith(".invalid") or to_email.endswith("@example.com"):
        return _short_circuit("test_phone", "sendgrid", to_email, subject)

    s = get_settings()
    if not s.sendgrid_api_key:
        return _short_circuit("no_credentials", "sendgrid", to_email, subject)

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
        _log_success("sendgrid", to_email, "email")
        return True
    except Exception as exc:
        _log_failure("sendgrid", to_email, "email", exc)
        log.warning("email send failed: %s", exc)
        return False
