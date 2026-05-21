# Finding 006 — Email-webhook security gaps: no auth, no `to:` validation, attachments silently dropped

**Discovered**: 2026-05-22, while verifying whether
`complaints@carimotech.in` is fully live end-to-end. The DNS layer
(no MX record) was the headline failure, but auditing the webhook
handler underneath turned up three security and silent-data-loss
gaps that activate the moment DNS is wired.

**Severity**: HIGH (security) for gaps (a) and (b); MEDIUM (silent
data loss) for gap (c).

**Status today**: dormant only because `carimotech.in` has no MX
record — no real mail reaches SendGrid, no real SendGrid POST reaches
our endpoint. The gaps activate immediately on DNS fix unless they
are addressed.

---

## Gap (a) — Webhook is unauthenticated

`backend/app/routers/webhooks.py:215-260` — `_handle_inbound_email()`
mounts at `POST /webhooks/sendgrid/email` (and the alias
`/webhooks/sendgrid/inbound-email`) with **no auth dependency** in
the function signature. The intent is explicit, not accidental —
`backend/tests/test_webhooks.py:49` literally contains
`def test_webhook_no_auth_required(client):` confirming the design.

### Why this is the wrong default

SendGrid Inbound Parse does not sign its POSTs by default. Our
endpoint accepts any HTTP POST that matches the route shape — there
is no shared-secret header, no HMAC verification, no source-IP
allowlist. Once `https://aibuildcare-api.onrender.com/webhooks/sendgrid/email`
is reachable (which it is today — we just don't have DNS routing
mail to it), anyone who guesses or finds the URL can POST forged
multipart form data and create unlimited tickets.

The URL is not secret. It will be discoverable from network
metadata, log lines, monitoring tools, even simple URL-bruteforce
of common webhook paths.

### Risk vectors that this opens

1. **Spam tickets** — an attacker hits the endpoint with N POSTs;
   our DB gets N rows; Twilio (once wired with real credentials) gets
   N WhatsApp messages to send; SendGrid (once configured) gets N
   auto-reply emails to send. Each is a real cost.
2. **Auto-reply abuse** — an attacker POSTs with
   `from=victim@example.com`. Our auto-reply
   (`webhooks.py:243-247`) fires an email to the victim. We become
   an unwilling part of a reflection-amplification attack against
   third parties.
3. **Auto-assignment abuse** — POSTs that parse to high-priority
   categories trigger real WhatsApp escalations to real staff,
   potentially escalating to L4 (chairman) on persistent
   ignored-complaint patterns.

### Remediation paths

**Option A — Shared-secret header** (cheapest, ~2 hours):
- Add `AIBUILDCARE_SENDGRID_INBOUND_SECRET` env var.
- Configure SendGrid Inbound Parse to send a custom header (SendGrid
  supports `Header Name`/`Header Value` in the Inbound Parse
  configuration).
- The webhook handler verifies the header using
  `secrets.compare_digest` (same pattern as the existing
  `internal_jobs_secret` check in `routers/internal_jobs.py:30-37`).
- Returns 403 on mismatch.

Cons: SendGrid still has to be the ONLY caller; if SendGrid's own
account is breached, the secret is exposed.

**Option B — SendGrid IP-allowlist + secret header** (Option A + ~1
hour):
- SendGrid publishes their Inbound Parse source IPs.
- Whitelist them at the FastAPI layer or via a Render Network
  Service rule.
- Belt + suspenders with Option A.

**Option C — Webhook signing via HMAC** (proper, ~half day):
- Both sender (SendGrid via a custom `X-Webhook-Signature` header) and
  receiver compute HMAC-SHA256 of the request body using a shared
  secret.
- Receiver rejects if signatures don't match.
- The SendGrid Inbound Parse UI doesn't natively support HMAC
  signing — would need an intermediary (CloudFlare Worker, AWS
  Lambda, etc.) to wrap SendGrid's POST in an HMAC layer. Overkill
  for the threat model.

**Recommendation**: Option A is the right default. Implement before
the DNS MX record is added so the activation order is "secure first,
route mail second." Roughly 2 hours of work; 1 line of FastAPI
dependency + 1 env var.

---

## Gap (b) — Handler ignores the `to:` field; can be made to attribute mail to any domain

`backend/app/routers/webhooks.py:218-220` extracts the form data as
`sender = _email_addr(form.get("from"))`, etc. The recipient
address (`to:`) is read NOWHERE.

### Why this matters

Even after Gap (a) is closed (shared secret), if SendGrid is
configured to inbound-parse multiple domains (or if a misconfigured
SendGrid Inbound Parse rule covers more than just `carimotech.in`),
our handler will accept the mail regardless of which domain it was
addressed to. A POST with the right secret and arbitrary
`to=anything@otherdomain.com` creates a ticket.

This is not exploitable from outside (you'd need the shared secret
from Gap (a)) but it's a defense-in-depth weakness. SendGrid's
multi-tenant nature makes it possible for an accidentally-broad
Inbound Parse rule to route unrelated mail to us.

### Remediation

In the handler:

```python
to_addr = _email_addr(form.get("to"))
ALLOWED_DOMAINS = {"carimotech.in"}  # or env-configured
if to_addr and not any(to_addr.endswith(f"@{d}") for d in ALLOWED_DOMAINS):
    log.warning("inbound-email rejected: to=%s not in allowed domains", to_addr)
    return {"status": "rejected", "reason": "domain_not_allowed"}
```

15 minutes of work. No external dependency.

---

## Gap (c) — Attachments silently dropped

SendGrid Inbound Parse delivers attached files as additional
multipart fields (`attachment1`, `attachment2`, etc., plus a JSON
metadata field `attachment-info`). Our handler at
`backend/app/routers/webhooks.py:215-260` reads the form data and
extracts only `from`/`subject`/`text`/`html` — **never**
`attachment1` or `attachment-info`.

### Why this is bad

A resident emails `complaints@carimotech.in` with "Burst pipe in
my unit — see photo" and a JPEG of the flooded room attached. Our
system:
- Receives the email (good, once DNS is fixed)
- Creates a ticket with the text body (good)
- **Silently drops the photo** — no message log entry, no warning,
  no link in the ticket

This breaks Finding 005 Gap 1 even harder: the photo-elevates-
priority claim was already partial (worked on WhatsApp/SMS but not
on dashboard). Email channel makes it three-fold partial: photos
are dropped here too, with no signal.

### Remediation

When the SendGrid form contains `attachment*` fields:
1. Read each attachment as bytes from the form
2. Upload to R2 via the existing `r2_client.upload_bytes()` helper
3. Store the returned URLs as the complaint's `media_urls`
4. Pass image URLs to the parser so vision-priority elevation can
   run (matching the WhatsApp/SMS intake path)

~2 hours including a test case using a forwarded photo from a real
inbox.

---

## Bottom line + sequencing

The DNS MX record activation (cheapest fix, ~30 min) must NOT happen
until Gap (a) is closed. Sequence:

1. **Today**: close Gap (a) — secret header check. Code change +
   add `AIBUILDCARE_SENDGRID_INBOUND_SECRET` env on Render.
2. **Today (also)**: close Gap (b) — `to:` domain allowlist. Same
   PR as Gap (a).
3. **This week**: add MX record at Hostinger. Configure SendGrid
   Inbound Parse with the secret header. Test with a real email.
4. **Next week** (or whenever you're ready to claim "email +
   attachments work"): close Gap (c) — wire attachment handling.
   Until then, edit any pitch line about "emailing complaints with
   photos" to clarify "text-only emails today, photos via WhatsApp."

Activating the email channel BEFORE closing Gap (a) means publishing
an open-spam endpoint to the internet. The 2 hours of secret-header
work is not optional.
