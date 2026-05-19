# AIBuildCare — Session Handoff (resume after break)

_Last updated: 2026-05-19. Repo: `psvnataraj-hue/aibuildcare`, branch `main`._

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
