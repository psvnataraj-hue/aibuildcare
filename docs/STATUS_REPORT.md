# AIBuildCare — System Status Report (for independent review)

_Generated 2026-05-19. Repo: `psvnataraj-hue/aibuildcare`, branch `main`,
latest commit `6930431`._

## Purpose
AIBuildCare is an AI-assisted complaint-management system for residential
societies / building maintenance & security. Residents report issues
through everyday channels (WhatsApp, email, Google Form, voice notes);
the system parses each complaint with an LLM, classifies and prioritizes
it, auto-assigns a contractor, sends a language-matched acknowledgement,
and exposes a management dashboard with analytics.

## Architecture
- **Backend:** Python, FastAPI, ~2,400 LOC. Raw-SQL service layer behind
  a thin DB shim that runs **SQLite** (local/tests) or **Postgres/
  Supabase** (production) with byte-identical behavior.
- **Frontend:** Vue 3 + TypeScript + Vite SPA, ~2,500 LOC, Tailwind +
  reka-ui design system, Pinia state, Chart.js, WebSocket live updates.
- **Hosting:** Render (free tier) — `aibuildcare-api` (web service) +
  `aibuildcare-web` (static site). Supabase Postgres (session pooler).
  Cloudflare R2 for media. Render free tier cold-starts (~20–40s) after
  idle.
- **Test suite:** 129 tests passing (pytest), forced onto SQLite for
  isolation.

## Intake channels
- *Implemented & **verified live** end-to-end:* **WhatsApp** (Twilio –
  text/image/voice), **Email** (SendGrid Inbound Parse), **Google Form**
  (Apps Script → webhook).
- *Implemented & unit-tested but **NOT yet verified against the live
  provider**:* **SMS** (`/webhooks/twilio/sms` + alphanumeric-sender send
  path). **Deferred for the pilot:** India SMS requires TRAI DLT
  registration (entity + template pre-approval); WhatsApp covers the
  same need far better in India. Do not represent SMS as working until
  DLT is registered and a live phone test passes.
- *Also:* Dashboard / API.

## AI / ML usage
- **Complaint parsing:** Claude Haiku 4.5 extracts `unit_number`,
  `category`, `priority`, `detected_language`, and a warm acknowledgement
  written in the resident's own language/script. Deterministic
  rule-based fallback if the LLM is unavailable (never hard-fails).
- **Image understanding:** complaint photos rehosted to R2; Claude
  vision assesses severity/safety and can escalate priority.
- **Speech-to-text:** Sarvam AI (saarika) for 9+ Indian languages +
  Hinglish; local Whisper fallback; graceful no-op if neither available.
- **Text-to-speech (new):** Sarvam AI (bulbul) synthesizes the
  acknowledgement to an MP3 voice note delivered over WhatsApp media.
  Text acknowledgement is always sent first; the voice note is additive
  and silently skipped on any failure. MP3 chosen to match WhatsApp's
  accepted codecs (server has no ffmpeg → no transcoding).
- Multilingual: 10 languages, language-mirrored acknowledgements.

## Complaint-management features
- Smart **auto-assignment**: contractor chosen by rating +
  load-balancing, configurable via a `system_config` table.
- **Estimated completion date** per category SLA.
- Status lifecycle with full **status-history** audit trail and
  per-complaint message log.
- Contractor **ratings** and post-resolution feedback.
- Analytics APIs + CSV export; contractor performance views.
- Contractor WhatsApp notification on assignment/reassignment.

## Dashboard / UI
- Overview with click-through KPI cards (Open / In-Progress / Completed
  / Overdue), recent-complaints feed, live WebSocket refresh.
- Complaints list with sort/filter/pagination, complaint detail with
  image lightbox, contractors, contractor analytics, settings.
- Light/dark mode, responsive mobile drawer, bilingual EN/हिंदी, toasts.

## Data model (Postgres/SQLite parity)
`societies, units, users, contractors, categories, complaints,
complaint_messages, complaint_status_history, complaint_ratings,
auth_sessions, system_config`. Auth via JWT with server-side session
table. Production seed: 7 categories, 34 rated contractors.

## Current state
- Backend live and healthy; production DB at a clean pilot slate (0
  complaints; 7 categories, 34 contractors, 2 config rows preserved).
- Google Form intake verified end-to-end (Form → Apps Script trigger →
  webhook → AI parse → ticket + auto-assign + ack).
- Voice-reply feature implemented, unit-tested (129/129), committed and
  pushed; activates on next Render deploy with existing keys + a live
  Twilio WhatsApp number.

## Known gaps / risks (please scrutinize)
1. **Render free-tier cold start** (~40s measured) — mitigation is an
   external 5-min uptime ping (UptimeRobot/cron-job.org) keeping the
   instance warm; affects dashboard login + interactive channels, not
   just webhooks. No in-repo cron (private-repo Actions-minute cost).
2. **Single hard-coded admin identity** in the UI; no user management,
   RBAC, or multi-society tenancy isolation. **Largest gap** — design
   work, not a patch; appropriate to scope as "single-society pilot".
3. **Partial i18n** — many UI strings are hard-coded bilingual rather
   than fully localized.
4. ~~`VITE_API_BASE` pending~~ **RESOLVED & verified**: deployed SPA
   bundle points at `aibuildcare-api.onrender.com/api/v1`; live
   dashboard reaches the live API.
5. ~~Raw-SQL injection risk~~ **REVIEWED — clean**: all queries
   parameterized (`?`/`%s` bound); only dynamic SQL is whitelisted
   `ORDER BY` + hardcoded WHERE clause assembly; no user input is
   string-interpolated into SQL anywhere.
6. SQLite-for-tests vs Postgres-for-prod parity relies on a hand-written
   shim — review correctness risk.
7. Analytics charts degrade with sparse data; some trend/rating charts
   intentionally omitted.
8. Free-tier single-instance; no queue/retry for outbound notifications
   beyond best-effort try/except.
9. **SMS channel is unproven & deferred** — code complete and
   unit-tested, but never exercised against a real provider; India SMS
   additionally blocked on TRAI DLT registration. Not a pilot channel.
10. **Voice reply (Sarvam TTS → WhatsApp)** — implemented + 17 unit
   tests; live verification pending Twilio WhatsApp number.
11. **Staff-facing summaries** — parser emits per-configured-language
   complaint summaries for officials who don't read the resident's
   language (`official_summary_languages`, default Hindi).

## Requested review focus
Architecture soundness, security (auth, raw SQL, webhook endpoints with
no JWT), the graceful-degradation pattern across AI/notification
failures, production-readiness for a small pilot, and the
highest-leverage hardening before scaling beyond one society.
