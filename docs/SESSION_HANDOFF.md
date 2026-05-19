# AIBuildCare — Session Handoff (resume after break)

_Last updated: 2026-05-19 (session 3 close). Repo:
`psvnataraj-hue/aibuildcare`, branch `main`._

## SESSION 3 CLOSE — what changed
- **Prod Supabase cleared to a clean pilot slate**: `complaints = 0`;
  `categories(7)`, `contractors(34)`, `system_config(2)` preserved.
  Reusable guarded tool: `scripts/clear_test_tickets.py` (self-aborts
  unless the table is exactly the 5 named test tickets).
- **Sarvam TTS -> WhatsApp voice reply SHIPPED** (`backend/app/services/
  tts.py` + `notify.send_whatsapp_media` + `_maybe_voice_reply` in
  `webhooks.py`). MP3 from Sarvam (`output_audio_codec=mp3`) -> R2 ->
  Twilio WhatsApp media; **no ffmpeg/transcoding**. Text ack is always
  sent first; voice note is an additive best-effort message that
  silently skips on any failure (no key / TTS error / R2 off / Twilio
  off). Reuses `AIBUILDCARE_SARVAM_API_KEY`.
- Tests **129/129** (112 + 17 new in `tests/test_voice_reply.py`).
- **Go-live needs (no code, just env on Render `aibuildcare-api`):**
  `AIBUILDCARE_SARVAM_API_KEY` (already set), R2_* vars (already set
  for photos), live Twilio WhatsApp number. Optional overrides:
  `AIBUILDCARE_SARVAM_TTS_MODEL` (def `bulbul:v2`),
  `_SARVAM_TTS_SPEAKER` (def `anushka`),
  `_WHATSAPP_VOICE_REPLY_ENABLED` (def `true`). Then Manual Deploy.
- Google Form intake: backend ready; user has the create-Form +
  Apps Script + trigger steps (in this session's chat + DEPLOYMENT.md
  section 4). Pending: user creates the Form, submits one real test,
  asks Claude to scoped-delete it.

## SESSION 2 CLOSE — what changed
- **Sarvam AI speech-to-text LIVE & verified** across Hindi, Telugu,
  English, Hinglish (native scripts, urgency detection, auto-assign
  all working). Set on Render via `AIBUILDCARE_SARVAM_API_KEY`.
- Tests **112/112**. Commits this session: `f12e890` (Twilio sms
  sender) → `62d3479` (SendGrid email) → `ed3cbb1` (handoff) →
  `c92c9ab` (Sarvam audio).
- Prod Supabase currently holds **5 audio test tickets**
  (SER-2026-00001..00005) — clear them for a clean pilot start
  (scoped-delete by id; preserve categories/contractors/system_config).

## NEXT SESSION — priorities (user requested)
1. **Google Form intake** — backend `/webhooks/forms` ALREADY built
   + tested; Apps Script + fields already in `DEPLOYMENT.md`. Task =
   guide user to CREATE the Form + paste Apps Script (their action),
   optionally polish. NOT a big build — set expectations.
2. **Sarvam TTS → WhatsApp audio reply** (NEW feature): generate
   speech from the acknowledgement via Sarvam Text-to-Speech →
   upload to R2 (public URL) → send as Twilio WhatsApp **media**
   message. Design caveats: WhatsApp audio codec (use OGG/Opus or
   WhatsApp-accepted MP3 — verify Sarvam TTS output format & convert
   if needed), Twilio media-send needs public URL (R2 ✔), added
   latency/cost, must stay in 24-h session window (acks are reactive
   → ok). Keep graceful: if TTS fails, still send the text ack.
   Fetch current Sarvam TTS API docs (endpoint/auth/params/limits)
   before coding — don't guess the contract.
3. Deferred: add more complaint categories (e.g. map noise/neighbour
   → Security) + fallback contractor for "Other"/unmatched so such
   tickets don't sit unassigned (SER-2026-00005 was the example).

## Current state — WORKING & LIVE
- Backend live on Render `https://aibuildcare-api.onrender.com` (manual-sync).
  `/health` → `{"status":"ok"}`.
- DB: **Supabase Postgres** (session pooler) — persistence verified.
  **Production complaints table is now EMPTY (clean pilot slate)**;
  categories(7), contractors(34, rated), system_config(2) preserved.
- Tests: **110/110 passing** (`cd backend && .venv/Scripts/python -m pytest`).
- Latest commit: `62d3479` (SendGrid email intake). All work pushed.

## Intake channels (all built, parse via Claude Haiku 4.5 + rule fallback)
- **WhatsApp** `/webhooks/twilio/whatsapp` — verified live end-to-end.
- **SMS** `/webhooks/twilio/sms` — code ready; SMS sender uses
  `AIBUILDCARE_TWILIO_SMS_NUMBER` (alphanumeric e.g. CARIMO).
- **Email** `/webhooks/sendgrid/email` (+ `/inbound-email` alias) —
  **verified live**: real email → ticket + auto-assign + ack email.
  Working address pattern: `<anything>@complaints.carimotech.in`
  (NOT `complaints@carimotech.in` — apex has no MX).
- **Google Form** `/webhooks/forms`.

## Features delivered (Phases 1–5 + UI)
Dual DB (sqlite tests / Postgres prod) · images (Cloudflare R2 +
Haiku vision) · audio (local Whisper, lazy/graceful) · multilingual
(10 langs, language-mirrored acks) · smart auto-assignment (rating +
load-balancing, configurable via `system_config`) · completion
forecasts (`estimated_completion_date`) · contractor ratings ·
analytics APIs · post-resolution ratings · contractor WhatsApp
notify on assign/reassign. Frontend: Vue3 + shadcn-vue (real
components), vibrant theme, toasts, dark mode, bilingual EN/हिंदी,
mobile hamburger, profile menu, sort/filter, pagination, analytics
tabs + CSV export + Chart.js charts. `pytest` 110/110.

## ⚠️ PENDING — PART 2 (user actions, do after break)
1. **SendGrid → Inbound Parse**: host `complaints.carimotech.in`,
   URL `https://aibuildcare-api.onrender.com/webhooks/sendgrid/email`
   (POST). `/inbound-email` also works if already set. (MX already
   propagated + verified; webhook verified live — this is just to
   confirm the host/URL row is correct.)
2. **Render `aibuildcare-api` env**: ensure
   `AIBUILDCARE_SENDGRID_API_KEY` and
   `AIBUILDCARE_SENDGRID_FROM_EMAIL=contact@carimo.tech` set →
   **Manual Deploy** `62d3479`.
3. Test: email `…@complaints.carimotech.in`, Subject "5B AC kharab
   hai", Hindi body → expect Supabase ticket unit=5B,
   category=AC/Cooling, channel=email, ack from contact@carimo.tech,
   contractor WhatsApp if auto-assigned.
   → Then ask Claude to run a live deployed-webhook parse test
   (simulated SendGrid payload, no real inbox spam).

Also still pending from earlier:
- Render `aibuildcare-web`: set
  `VITE_API_BASE=https://aibuildcare-api.onrender.com` + Manual Deploy
  (so the live dashboard reaches the API).
- Twilio Part 1/Part 3: buy WhatsApp number, register "CARIMO"
  sender ID, set webhook URLs, set
  `AIBUILDCARE_TWILIO_WHATSAPP_NUMBER` / `_SMS_NUMBER` on Render.

## Requested next feature (not yet built)
**"Email in → also reply on WhatsApp"**: extract phone from email
(From/body); if found also `send_whatsapp(num, ack)`. Caveat: WhatsApp
policy — delivers only if that number joined the sandbox / messaged
the business within 24 h, else needs an approved template; email ack
always works. ~15 min, graceful fallback. Trigger phrase next
session: **"build the email→WhatsApp reply"**.

## Honest known gaps (not failures)
- F4 i18n: nav/headers/key labels translated; not 100% of strings.
- Trend line/rating charts omitted (data too sparse); stacked
  "complaints over time" bar + category pie are built.
- Per-contractor full complaint list needs a new backend endpoint.
- Local `.env` has DB→Supabase (prod); running backend locally hits
  prod data. Tests are safe (forced sqlite). SendGrid key NOT in
  local .env (only Render) — can't call SendGrid API locally.

## Repo conventions learned
- `.gitignore` (Python) ignores `lib/` → `frontend/src/lib/*` needed
  a negation (`!frontend/src/lib/`). Watch for Python-ignore traps.
- Source must stay ASCII (Windows cp1252 import) — use `\uXXXX`
  (e.g. `ACK_TICK="✅"`), no raw non-ASCII in .py.
- All env vars are `AIBUILDCARE_`-prefixed (pydantic env_prefix).
- Render is **manual-sync** (push ≠ deploy; user clicks Manual Deploy).
- Test data on prod Supabase: always scoped delete by id, never
  blanket `DELETE FROM complaints`.
