# Finding 005 — Two pitch claims are PARTIAL: dashboard cannot attach photos; voice reply only on WhatsApp channel

**Discovered**: 2026-05-22, during the pre-Part-6 verification pass of 8
brochure claims against actual code. 6 of 8 claims came back fully
built. 2 came back partial — both are real gaps with a "true for some
channels, not all channels" shape.

**Severity**: MEDIUM for accountability. These claims are not false in
general — they're false for specific channels the customer might choose
to use first.

**Status today**: active. Both gaps surface immediately on the first
customer interaction that picks the wrong channel.

---

## Gap 1 — Dashboard cannot attach photos; photo-based urgency flagging only works on WhatsApp / SMS inbound

### What the brochure claims
"Customers attach a photo of a flooded room or broken pipe; the system
sees the photo and elevates the priority to urgent automatically."

### What the code actually does

  - `routers/webhooks.py:169, 186` — the inbound Twilio webhook DOES
    pass `image_urls=images` to `complaint_service.create_complaint()`.
    A WhatsApp photo flows through to Claude Haiku 4.5 vision.
  - `services/haiku_parser.py:316-320, 348-350` — Claude is asked
    explicitly to "raise priority if a photo shows severe/unsafe
    damage" and the parser takes `max(llm_priority, rule_priority)`.
    This is the vision-elevates-urgency path, and it works.
  - `routers/complaints.py:93-102` — the **dashboard** POST /complaints
    endpoint accepts a `ComplaintCreate` pydantic model. That model has
    no `image_urls` field. So a resident filing via the dashboard
    cannot attach a photo at all, and therefore cannot trigger the
    vision-elevates-urgency path.

### Honest claim split

  - **SAFE**: "Photos sent via WhatsApp or SMS are analysed by Claude
    Haiku 4.5 vision and priority is elevated automatically when
    damage looks severe."
  - **UNSAFE**: "Customers can attach a photo through the dashboard and
    have priority elevated automatically." — false today; the
    dashboard's `ComplaintCreate` has no image field.

If the brochure assumes the dashboard is a primary intake channel for
residents (it isn't, today — primary intake is WhatsApp) this gap is
mostly cosmetic. If the brochure shows a dashboard screenshot with an
"attach photo" button, that screenshot is aspirational.

### Remediation path (do not build now)

  1. Add `image_urls: list[str] | None` to the `ComplaintCreate`
     pydantic schema (`schemas.py`).
  2. Add a multipart upload route (or accept R2 pre-signed URL refs)
     so the frontend can POST images to R2 and pass the URLs through.
  3. The downstream chain (`create_complaint` → `parse_complaint`)
     already accepts `image_urls` — no service-layer change needed.

Estimate: ~half day backend + a frontend image-upload widget.

---

## Gap 2 — Voice-note spoken reply only works on WhatsApp; SMS gets text-only; TTS silently falls back to text if Sarvam fails

### What the brochure claims
"Send a voice note in Hindi; you'll get a spoken reply back in Hindi."

### What the code actually does

  - `services/audio_transcriber.py:44-76` — Sarvam STT transcribes
    voice notes and returns `language_code`. Works.
  - `services/tts.py:64-101` — Sarvam TTS synthesizes audio reply in
    the same language as the inbound. Works.
  - `routers/webhooks.py:135-142` — TTS audio is sent via
    `notify.send_whatsapp_media()` on the WhatsApp inbound path. Works.
  - **Gap A — SMS path**: SMS is a text-only protocol. A voice-note via
    SMS doesn't exist (SMS doesn't carry audio). The brochure claim is
    silently false for SMS — but this is a protocol fact, not a code
    gap. Acceptable, but worth saying explicitly: "voice replies happen
    on WhatsApp only, because SMS does not support audio."
  - **Gap B — Graceful fallback to text-only**: `services/tts.py:100-101`
    returns `None` on Sarvam failure (no API key, network failure,
    unsupported language code). The webhook handler then skips
    `send_whatsapp_media` and only the text acknowledgement goes out.
    The resident sees the text reply (in their language, that part
    works) but no voice. They cannot tell the difference between "this
    system never sends voice replies" and "TTS silently failed for my
    message" without checking the operator event log.

### Honest claim split

  - **SAFE**: "Voice notes sent via WhatsApp are transcribed in the
    sender's language and replied to with both a text and (when
    available) a spoken voice-note in the same language."
  - **UNSAFE**: "Every voice note gets a spoken reply." — false when
    TTS fails. The customer gets text; we no-op the audio.
  - **UNSAFE**: "Voice replies on all channels." — false for SMS by
    protocol.

### Remediation path (do not build now)

  1. (Gap A) Update brochure wording to say "WhatsApp voice replies" not
     "voice replies", or add a single-sentence footnote.
  2. (Gap B) When TTS fails on a voice-note-originated complaint, log
     an operator event with severity=warn so the operator can see how
     often the silent fallback fires; consider falling back to a text
     reply that explicitly says "[voice reply unavailable today]" so
     the resident at least knows audio was attempted. Already partially
     in place — `operator_events` will log `external_call_failed` for
     Sarvam from the chokepoint wrap in Part 4.

Estimate: ~1-2 hours for the text-acknowledgement clarification; the
operator-event logging is already there courtesy of Part 4.

---

## Six other claims came back BUILT (no finding needed)

For the record — the verification pass confirmed all six of these can
be claimed honestly today, with concrete evidence:

| # | Claim | Evidence |
|---|---|---|
| 1 | Auto-routing by category AND workload | `routing_service.py:47-51, 75-79` — sort key `(primary_category, skill_level, workload)` for staff, `(primary_category, -rating, workload)` for contractors. Workload via `_staff_workload(...)` open-complaint count. |
| 2 | Auto-escalation L1→L2→L3→L4 with timestamps + WhatsApp | `escalation_service.py:28-35, 91-94`; `complaints` table has all 4 timestamp columns; `jobs_service.py:110-137` runs the level-advance + WhatsApp send. |
| 5 | Sunday weekly digest + auto-flagged major incidents | `weekly_summary.py:228-280` (Sunday-gated, computes stats, sends email); `incident_flagging.py:44-104` (5 heuristics: rapid escalation, safety-urgent, repeat unit, category surge, repeat parking offender). |
| 6 | Acknowledgements in the resident's language | `haiku_parser.py:225-226` prompt explicitly instructs Claude to write in the same language and script; `complaint_service.py:154` propagates Claude's reply verbatim. |
| 7 | Non-admin cannot see another tenant's data | Every service-layer query filters `c.society_id = ?`; cross-society reads return 404/empty. (Note: this is non-admin only; admin still has cross-tenant reach per finding 001.) |
| 8 | Real-time status to requester | `GET /complaints/mine` returns all open complaints for the caller; per-complaint endpoint includes the messages thread (incl. system messages for each escalation event) and current status. |

---

## Critical-path timing

Both partial-claim gaps are pre-customer-pitch issues:

  - Gap 1 (dashboard photo upload) should be edited out of any brochure
    line that implies "dashboard intake" today, OR fixed before the
    first prospect demo that shows the dashboard as the primary intake
    channel. If dashboard is being positioned as "operator-only and
    residents use WhatsApp", this gap is cosmetic.
  - Gap 2 (voice replies) needs one-word brochure tweaks ("WhatsApp
    voice replies" not "voice replies") before any non-WhatsApp pitch.

Neither is on the "must-fix-before-customer-#2" path (that path is
finding 001 — admin cross-tenant leak). These are honesty-of-marketing
fixes, not architectural ones.
