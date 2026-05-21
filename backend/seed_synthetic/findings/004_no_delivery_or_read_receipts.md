# Finding 004 — No delivery or read-receipt proof for outbound messages; inbound timestamps are complaint-level not message-level

**Discovered**: 2026-05-22, while auditing what delivery / read-receipt
proof we can honestly claim to customers. The pitch line "you'll see
when each message was delivered and read" turns out to be marketing
wishful thinking today.

**Severity**: HIGH for customer-facing accountability claims.

**Status today**: outbound messages are fire-and-forget at the
application layer — Twilio is called, the SID is discarded, no
callback is wired, no row is persisted to record subsequent delivery
status. Inbound timestamps exist but only at the complaint-creation
level, not per-message.

---

## What the audit found

### 1. Outbound status callback — NOT WIRED

Every `client.messages.create()` call in `backend/app/services/notify.py`
(lines 117-127, 148-160, 181-192, send_whatsapp / send_whatsapp_media /
send_sms) omits the `status_callback=` parameter. Twilio supports a
per-send `StatusCallback` URL that fires with progressive status
updates (`queued → sent → delivered → read → failed / undelivered`).
We're not registering for any of those.

The webhooks router (`backend/app/routers/webhooks.py`) has 5 endpoints
— inbound WhatsApp, inbound SMS, inbound email, SendGrid email,
generic forms — and **zero** for accepting Twilio status callbacks. Even
if a callback URL were registered, there's no endpoint to receive it.

### 2. Per-message status persistence — NO TABLE

The `complaint_messages` table at `migrations/001_init.sql:97-103` has
only 4 columns: `id, complaint_id, sender, body, created_at`. No
`provider_message_id` (Twilio SID), no `status`, no `delivered_at`, no
`read_at`. We do not persist the SID returned by Twilio's API on send,
so even if a status callback fired we couldn't correlate it to a
specific message.

Searched every `migrations/*.sql` for: `outbound_messages`,
`message_deliveries`, `notification_log`, `whatsapp_messages`,
`provider_message_id`, `delivered_at`, `read_at`. **Zero matches.** No
table exists for this.

### 3. Sandbox vs WhatsApp Business API

Configured default at `backend/app/config.py:41`:
`twilio_whatsapp_from = "whatsapp:+14155238886"` — Twilio sandbox.
Production override `twilio_whatsapp_number` defaults empty.

Sandbox capabilities (Twilio docs):

  - ✓ Delivery callbacks (`sent`, `delivered`, `failed`,
    `undelivered`) DO work on the sandbox when `StatusCallback` is
    registered.
  - ✗ Read receipts (`read` event) do NOT work on the sandbox. Read
    receipts require Twilio's WhatsApp Business API
    (paid, requires WhatsApp Business account verification + Facebook
    Business Manager approval).

So: even if we wire callbacks today, only delivery proof is achievable.
Read receipts require both a code change AND a Twilio account upgrade
AND WhatsApp Business approval.

### 4. Inbound message timestamping — COMPLAINT-LEVEL ONLY

`backend/app/routers/webhooks.py:147-175` `twilio_whatsapp()` receives
the form data, extracts phone + body, and calls
`complaint_service.create_complaint(text, channel="whatsapp", ...)`.
That inserts a row into `complaints` with `created_at = datetime('now')`.
The original inbound message body becomes `complaints.raw_text` — it is
NOT stored as a separate row in `complaint_messages` with its own
timestamp.

So:

  - ✓ A customer can be shown "your ticket was logged at 10:42:13" with
    server timestamp accuracy (depends on Render clock).
  - ✗ A customer cannot be shown "your WhatsApp message arrived at the
    Twilio webhook at 10:42:11" as a distinct timestamp from
    ticket-creation (the two happen in the same request handler, but we
    only record the latter).
  - ✗ For subsequent inbound messages on the same thread (a resident
    replying to a follow-up question), we do store them as
    `complaint_messages` rows with `created_at` — so those DO have
    per-message timestamps. But the *first* message is conflated with
    the complaint.

---

## What we can honestly claim today (verbatim phrasing)

**SAFE to say (true and provable):**

  - "When you message our number, we log your ticket with a server
    timestamp."
  - "All messages we send go through Twilio, an enterprise-grade
    messaging provider."
  - "Subsequent messages within a ticket conversation are timestamped
    individually."

**UNSAFE to say (cannot prove today):**

  - "You'll see when each message was delivered."
  - "You'll see when each message was read."
  - "Our system has a complete audit trail of message delivery
    confirmation."
  - "Read receipts are tracked per-message."

If any of those four lines are in customer-facing copy or a pitch deck
they should be removed BEFORE the next prospect demo, even if the
remediation in the next section ships shortly after.

---

## Remediation paths

Three escalating options. Each is its own change-set; none belongs on
the synthetic-data + diagnostics branch.

### Option A — Delivery proof only (~2 days, no Twilio upgrade)

Adds delivery + failure tracking; read receipts deliberately out of
scope. Sandbox-compatible (works today, no Twilio account change
needed).

  1. New migration: `outbound_messages` table
     ```
     id, complaint_id, provider, provider_message_id, recipient,
     channel (whatsapp|sms|email), status (sent|delivered|failed|undelivered),
     sent_at, status_updated_at, raw_callback_meta
     ```
  2. Update `services/notify.py` to:
     - register `status_callback=<base_url>/webhooks/twilio/status` on
       every `client.messages.create()` call
     - capture the returned `MessageSid` and persist to
       `outbound_messages` immediately on send
  3. New endpoint `routers/webhooks.py:POST /webhooks/twilio/status` —
     receives form data, updates the matching `outbound_messages` row
     by SID
  4. Dashboard: show delivery state on each outbound message in the
     complaint thread (✓ delivered / ⚠ undelivered / ❌ failed)

After Option A you can honestly say: "Each message we send is tracked
through delivery; you'll see ✓ delivered or ⚠ undelivered states on
every notification."

### Option B — Option A + read receipts (~3 days + Twilio + WA Business)

Builds on Option A. Adds read-receipt tracking by also accepting `read`
status callback events.

  5. (One-time, external) Apply for Twilio WhatsApp Business API access.
     Requires Facebook Business Manager verification of CARIMO. Lead
     time: 2-6 weeks for WhatsApp approval.
  6. Once approved, update env: `twilio_whatsapp_number` set to the
     verified production number (not the sandbox `+14155238886`).
  7. Read events flow through the same `/webhooks/twilio/status`
     endpoint; the `outbound_messages` table already has `status` and
     `read_at` slots — extend the update logic to recognize `read`.
  8. Note: read receipts depend on the recipient's WhatsApp privacy
     setting. If they have read receipts disabled in WhatsApp settings,
     no `read` event ever fires for them — that's a WhatsApp protocol
     fact, not our limitation. The dashboard should show "delivered;
     read receipt unavailable for this recipient" in that case.

After Option B you can honestly say: "Each message tracked through
delivery; read receipts shown when the recipient has them enabled in
WhatsApp."

### Option C — Option B + inbound-message timestamps (~half day more)

Marginal addition: store inbound messages as discrete
`complaint_messages` rows even for the first message of a complaint,
not just subsequent ones.

  9. Update `create_complaint()` to also insert a `complaint_messages`
     row carrying the original inbound text + a `received_at` timestamp
     at the moment the webhook handler entered.
  10. Dashboard: thread view shows the original inbound on the same
      timeline as later replies, with its own timestamp distinct from
      "ticket created at."

After Option C, a customer can see a true millisecond-grained timeline
of who said what and when — both directions.

---

## Recommendation

**Option A is the critical-path remediation** — it lifts the marketing
claim from "no proof" to "delivery proof" without waiting on the
WhatsApp Business API approval cycle. Schedule before the next
non-Palms paying customer signs.

**Option B should run in parallel as a procurement track**: someone
starts the WhatsApp Business API application now even while the rest
of the team works elsewhere. The 2-6 week approval window is the
binding constraint, not the code.

**Option C is nice-to-have polish** — bundle with whatever the next
inbox UX revision is.

---

## Critical-path timing

- Customer-facing copy claiming delivery / read tracking should be
  edited TODAY to match what we actually do (or the claim removed).
- Option A code should ship before the first non-Palms paying customer.
- Options B + C have longer external dependencies; schedule
  accordingly.

This finding is HIGH severity not because anything is broken — the
existing send path works fine — but because **the gap between what we
claim and what we prove is large enough to embarrass us at a customer
audit**. The fix is straightforward; the discipline is to fix it before
selling the capability, not after.
