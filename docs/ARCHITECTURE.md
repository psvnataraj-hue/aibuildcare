# AIBuildCare — Architecture & Repo Guide

_Last updated 2026-05-20. Repo: `psvnataraj-hue/aibuildcare`, branch
`main`. Latest commit `fd0ac95`. **306/306 tests** passing._

This doc is the **single entry point** for understanding the
codebase. It is self-contained — you should not need to read other
source files to understand what's where and why.

---

## 1. Product in 4 sentences

AIBuildCare is an AI-assisted **community management platform** for
Indian residential societies — complaints in (WhatsApp / SMS /
email / Google Form), tickets out, with intelligent multilingual
parsing, society-scoped tenancy, role-based access control, staff +
contractor routing, automatic SLA escalation, vendor self-service
directory, major-incident auto-flagging, and weekly committee
summaries. The same Claude Haiku 4.5 model that classifies tickets
also writes a warm acknowledgement in the resident's own language
(Hindi, Tamil, Telugu, Bengali, +6 more); Sarvam AI handles
speech-to-text on voice notes and text-to-speech for an audio reply
back over WhatsApp. The backend is FastAPI + Postgres; the dashboard
is Vue 3 + TypeScript + Tailwind. The whole stack runs on free-tier
hosting (Render web + Supabase Postgres + Cloudflare R2 +
cron-job.org) with a deliberate "no hidden costs" architectural rule.

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend HTTP | FastAPI (Python 3.12) | Async, typed, pydantic schemas |
| ORM | **None** — raw parameterised SQL behind a thin shim | Same code runs on SQLite (tests) and Postgres (prod); injection-audited |
| DB | Supabase Postgres (session pooler); SQLite for tests | Free tier + a real DB |
| Auth | JWT (server-issued via `/api/v1/auth/login`) + a server-side `auth_sessions` table | Revocable |
| LLM | Anthropic Claude Haiku 4.5 (`claude-haiku-4-5`) | Multilingual ticket parsing + acknowledgement |
| STT | Sarvam AI saarika | 10 Indian languages; verified live |
| TTS | Sarvam AI bulbul (MP3 output) | No transcoding; WhatsApp-native |
| Media | Cloudflare R2 (S3 API) | Public URLs for photos + voice notes |
| WhatsApp / SMS | Twilio | Sandbox live |
| Email | SendGrid | Inbound parse + outbound HTML |
| Cron | External — cron-job.org POSTs to `/internal/jobs/tick` every 15 min | Render free has no worker; secret-gated endpoint |
| Frontend | Vue 3 + TS + Vite + Tailwind + Pinia + reka-ui + Chart.js + lucide-vue-next | |
| Hosting | Render (web + static) | Manual-sync deploys (push ≠ deploy) |
| Realtime | A local WebSocket hub (`services/ws_hub.py`) | Not Supabase Realtime |

## 3. Repo tree (top-level)

```
aibuildcare/
├── README.md
├── DEPLOYMENT.md           # Render + Supabase + Twilio + R2 + cron setup
├── TESTING_CHECKLIST.md
├── render.yaml             # API + static-site service definitions
├── backend/
│   ├── requirements.txt
│   ├── requirements-audio.txt   # optional whisper (Sarvam is primary)
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py              # FastAPI factory + router registration
│   │   ├── config.py            # Pydantic Settings, env_prefix=AIBUILDCARE_
│   │   ├── deps.py              # current_user / current_society / require(perm)
│   │   ├── db.py                # get_conn() — sqlite (tests) OR psycopg2 shim
│   │   ├── seed.py              # admin user, default society, SLA defaults
│   │   ├── security.py          # bcrypt + JWT helpers
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── integrations/
│   │   │   └── r2_client.py     # boto3 S3-compatible to Cloudflare R2
│   │   ├── routers/             # FastAPI APIRouters (see §5)
│   │   └── services/            # business logic (see §4)
│   ├── data/                    # local sqlite DB (gitignored)
│   └── tests/                   # 22 test files, 306 tests (see §10)
├── migrations/
│   ├── 001_init.sql             # SQLite schema (fresh test DBs)
│   └── 001_init_pg.sql          # Postgres schema + additive ALTERs for prod
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts
│       ├── App.vue              # shell: sidebar nav + topbar + mobile drawer
│       ├── router.ts
│       ├── api.ts               # typed REST client + WS connect
│       ├── style.css            # Tailwind + design tokens
│       ├── views/               # 8 dashboard pages
│       ├── components/          # ComplaintCard + ui/* shadcn-style
│       └── lib/                 # i18n / theme / toast / utils
├── scripts/
│   └── clear_test_tickets.py    # guarded scoped-delete utility
└── docs/                        # all design + handoff docs (see §11)
```

## 4. Backend services (`backend/app/services/`)

Each file is a focused module with no cross-domain logic.

| File | Lines | Purpose |
|---|---|---|
| **`haiku_parser.py`** | ~210 | The brain. CATEGORIES enum (24). `_KEYWORDS` rule-based fallback. `_llm_parse()` calls Claude Haiku with a strict-JSON prompt; returns `unit_number`, `category`, `priority`, `detected_language`, `acknowledgement`, `official_summaries` (per-language staff summary). |
| `audio_transcriber.py` | ~110 | STT. Sarvam saarika via httpx → falls back to local Whisper → graceful `("", None)`. |
| `tts.py` | ~100 | TTS. Sarvam bulbul → MP3 bytes. Word/ISO/BCP-47 language normalisation. Graceful None on any failure. |
| `media_intake.py` | ~70 | Extracts Twilio `NumMedia` + `MediaUrlX` into (images, audio) tuples. Downloads via httpx Basic Auth, re-hosts to R2. |
| `notify.py` | ~115 | Outbound: `send_whatsapp` / `send_whatsapp_media` / `send_sms` / `send_email`. Every send is graceful-no-op if creds absent. |
| `complaint_service.py` | ~470 | The complaint life-cycle. `create_complaint` (parse → INSERT → auto-route → notify), `list_complaints`, `get_complaint`, `assign_contractor`, `assign_staff`, `update_status`, `add_message`, `list_messages`, `rate_complaint`, contractor analytics. Every read/write society-scoped via `_sid()`. |
| `contractor_router.py` | ~90 | Legacy "best contractor by specialty LIKE" picker; still used as fallback. |
| `routing_service.py` | ~120 | **The new router (E1b).** `find_assignee(category, society_id)` walks staff (primary > secondary; expert > senior > junior; lighter workload) then contractors. |
| `staff_service.py` | ~200 | E3a CRUD over `staff_members` + `staff_categories`. |
| `vendor_directory.py` | ~80 | E1b' — `list_vendors(society_id, category)` returns society-vetted contractors opted-in to `available_for_personal_jobs`, each with a `wa.me` deep link. |
| `escalation_service.py` | ~240 | E1c — manual `escalate(cid, sid)` bumps L1→L4 (manager / sr_manager / secretary / chairman). CRUD over `escalation_hierarchy`. |
| `jobs_service.py` | ~290 | E2 cron orchestrator. `run_tick()` runs four jobs: auto-escalation, staff reminders, complainant updates, weekly summary, incident flagging (delegated to `weekly_summary.py` and `incident_flagging.py`). |
| `weekly_summary.py` | ~250 | E2c — Sundays only, per society at most once per ISO week (idempotency via `weekly_summaries_sent` table). HTML email via SendGrid. |
| `incident_flagging.py` | ~160 | E2d — first-match-wins heuristic: rapid-escalation > safety-urgent > repeat-unit > category-surge. WhatsApps the hierarchy. |
| `rbac.py` | ~90 | The single permission matrix. 11 roles, 11 permissions. `has_permission(role, perm, society_id=None)` consults overrides if society_id given; admin bypass. |
| `rbac_overrides.py` | ~115 | E1c — per-society grant/revoke overrides on top of the default matrix. Admin role is NOT overridable (OEM safety). |
| `auth_service.py` | ~50 | `authenticate(email, password)` → JWT; `user_from_token(token)` → dict (includes `society_id` since F1). |
| `system_config.py` | ~70 | Runtime key/value (DEFAULTS dict + DB row overlay). Keys: `max_pending_jobs_per_contractor`, `load_balancing_enabled`, `official_summary_languages`, `whatsapp_voice_reply_mode`. |
| `ws_hub.py` | ~30 | In-memory WebSocket broadcast hub. |

## 5. Backend routers (`backend/app/routers/`)

| File | Mounted at | Purpose |
|---|---|---|
| `health.py` | `/health` | Liveness — no auth. Returns `{"status":"ok"}`. |
| `auth.py` | `/api/v1/auth` | `POST /login` → JWT. |
| `complaints.py` | `/api/v1` | The big one. List/get/create complaints, /assign (contractor OR staff), /status, /rate, /messages, contractor analytics, /admin/config. All gated by F3 `require()` per the permission matrix. |
| `webhooks.py` | `/webhooks` | Inbound: `/twilio/whatsapp` (text+image+audio, with TTS audio reply + directory intent), `/twilio/sms`, `/sendgrid/email`, `/forms`. Provider-authenticated upstream; no JWT. |
| `vendors.py` | `/api/v1/vendors` | E1b' — `GET /by-category?category=X`. Gated by FILE_COMPLAINT. |
| `escalation.py` | `/api/v1` | E1c — `POST /complaints/{id}/escalate` + CRUD over `/escalation/hierarchy`. |
| `staff.py` | `/api/v1/staff` | E3a — full CRUD + category subresource. |
| `admin.py` | `/api/v1/admin/permissions` | OEM RBAC override management. `?society_id=N` enables cross-society management for admin role only. |
| `internal_jobs.py` | `/internal/jobs/tick` | E2 — header-gated POST endpoint that an external cron hits every 15 min. Disabled (503) until `AIBUILDCARE_INTERNAL_JOBS_SECRET` is set. |

## 6. Database schema

All tables society-scoped where relevant. Migrations are idempotent
(`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS`)
so a deploy applies new schema to existing prod data without manual
steps.

| Table | Purpose |
|---|---|
| `societies` | Tenants. Single demo society "Palms Residency" seeded. |
| `units` | Flat-number registry per society. |
| `users` | Login accounts. Columns: `email`, `password_hash`, `role`, `society_id`, `is_active`. |
| `contractors` | External vendor roster, society-scoped. Columns include `specialty`, `average_rating`, `available_for_personal_jobs`. |
| `contractor_categories` | M:N — vendor ↔ category, with `primary_category` + `average_rating` + `completed_jobs`. |
| `staff_members` | In-house staff (phone-only identity by default). Society-scoped. |
| `staff_categories` | M:N — staff ↔ category, with `primary_category` + `skill_level`. |
| `categories` | Master list of 24 complaint categories + global `sla_hours`. |
| `category_sla_config` | Per (society, category) — `target_response_time_minutes`, `target_resolution_time_hours`, `priority_high_multiplier`, `escalation_levels` (JSON). Seeded for the default society. |
| `escalation_hierarchy` | Per-society escalation contacts: `role_name` (manager / sr_manager / secretary / chairman) × `escalation_level` (1..4) + name/phone/email. |
| `complaints` | The big one. ~30 columns. Includes society_id, AI parse output, channel, status, contractor/staff assignment, official_summaries (JSON), 4 escalation timestamps, last_complainant_update_at, last_assigned_staff_update_at, last_reminder_sent_at, reminder_sent_count, major_incident + flagged_at + reason. |
| `complaint_messages` | Threaded notes on a complaint (resident, staff, system). |
| `complaint_status_history` | Audit trail of every status transition. |
| `complaint_ratings` | Post-resolution star + feedback. |
| `auth_sessions` | Active JWT JTI registry (for revocation). |
| `system_config` | Runtime key/value config. |
| `role_permission_overrides` | Per-society RBAC override matrix (society_id, role, permission, granted). |
| `weekly_summaries_sent` | (society_id, week_start_date) PK — prevents double-send of the weekly summary. |

## 7. RBAC matrix (defaults in `services/rbac.py`)

Permissions: `file_complaint`, `view_own`, `view_all`, `assign`,
`resolve`, `escalate`, `authorize_enforcement`, `modify_staff`,
`modify_config`, `approve_reports`, `view_financial`.

| Role | Allowed by default |
|---|---|
| `resident` | file_complaint, view_own |
| `staff` | file_complaint, view_own, resolve |
| `contractor` | view_own, resolve |
| `manager` | file, view_own, view_all, assign, resolve, escalate, modify_staff |
| `sr_manager` / `secretary` / `chairman` | manager set + authorize_enforcement, modify_config, approve_reports, view_financial |
| `committee_member` | file, view_own, view_all, assign, resolve, escalate, authorize_enforcement, approve_reports, view_financial (NO modify_staff/config) |
| `enforcement_officer` | file, view_own, view_all, resolve |
| `viewer` | view_all only |
| **`admin`** | **ALL** (OEM superuser; NOT overridable per society) |

Each society can grant/revoke any of these per (role, permission)
via the `/api/v1/admin/permissions/overrides` PUT/DELETE endpoints.

## 8. The four cron jobs (run via `POST /internal/jobs/tick`)

Each every ~15 min (cron-job.org); each idempotent + self-throttled.

1. **`run_due_escalations`** — for every open complaint, reads its
   category's `escalation_levels` JSON, computes effective elapsed
   hours (with `priority_high_multiplier` for urgent), walks
   thresholds L1→L4, calls `escalation_service.escalate()` per level.
2. **`run_due_staff_reminders`** — staff assigned a complaint
   >2h ago AND status not yet `in_progress` gets a WhatsApp nudge.
   Throttle column: `complaints.last_reminder_sent_at`.
3. **`run_due_complainant_updates`** — resident gets a status
   reassurance WhatsApp every 4h on open tickets. Throttle column:
   `complaints.last_complainant_update_at`.
4. **`run_due_incident_flagging`** (E2d) — first-match-wins
   heuristic (rapid-escalation > safety-urgent > repeat-unit >
   category-surge) flags `major_incident=1`. WhatsApps the
   escalation_hierarchy.
5. **`run_due_weekly_summaries`** — Sundays only; per society at
   most once per ISO week (DB PK); HTML email via SendGrid to
   committee-role users (fallback: hierarchy emails).

## 9. Deployment + ops

### Live URLs
- API: `https://aibuildcare-api.onrender.com` (Render web service)
- Dashboard: `https://aibuildcare-web.onrender.com` (Render static)
- Currently deployed commit: see `git log` (Render is manual-sync,
  `git push` does NOT auto-deploy).

### Required env vars on Render `aibuildcare-api`
```
AIBUILDCARE_ENVIRONMENT=production
AIBUILDCARE_DATABASE_URL=<supabase postgres URL>
AIBUILDCARE_JWT_SECRET=<32+ char random>
AIBUILDCARE_SEED_ADMIN_EMAIL=<your email>
AIBUILDCARE_SEED_ADMIN_PASSWORD=<strong password>
AIBUILDCARE_ANTHROPIC_API_KEY=<for Haiku ticket parser>
AIBUILDCARE_SARVAM_API_KEY=<for STT + TTS>
AIBUILDCARE_TWILIO_ACCOUNT_SID, _AUTH_TOKEN, _WHATSAPP_NUMBER, _SMS_NUMBER
AIBUILDCARE_SENDGRID_API_KEY, _SENDGRID_FROM_EMAIL
AIBUILDCARE_R2_ENDPOINT_URL, _R2_ACCESS_KEY_ID, _R2_SECRET_ACCESS_KEY,
  _R2_BUCKET, _R2_PUBLIC_BASE_URL
AIBUILDCARE_INTERNAL_JOBS_SECRET=<32+ char random — gates the cron tick>
```

### Test suite
`cd backend && .venv/Scripts/python -m pytest`
→ **306 passed** as of `fd0ac95`.

### Local development
Local `.env` is at the repo root (not `backend/.env`); it points the
local Python process at the **prod Supabase** by default. Tests are
hermetic (sqlite tmp). Local server runs prod data — see the warning
in `SESSION_HANDOFF.md`.

## 10. Test suite (306 tests across 22 files)

| File | # | Covers |
|---|---|---|
| `test_health.py` | 1 | `/health` |
| `test_auth.py` | ~5 | Login + token + auth_sessions |
| `test_complaints.py` | ~20 | CRUD on complaints |
| `test_webhooks.py` | ~6 | Twilio + form + sendgrid intake |
| `test_haiku_parser.py` | ~25 | Rule-based parser regressions for unit/category/priority |
| `test_multilingual.py` | ~12 | 10-language detection + LLM mock |
| `test_media.py` | ~5 | R2 upload + image rehosting |
| `test_audio.py` | ~6 | Sarvam STT + fallback |
| `test_voice_reply.py` | 17 | Sarvam TTS → WhatsApp media, modality-aware modes |
| `test_email.py` | ~4 | SendGrid inbound parse |
| `test_forms.py` | ~2 | Google Form webhook |
| `test_auto_assign.py` | ~7 | Phase-4.5 contractor routing |
| `test_phase5.py` | ~5 | Contractor analytics endpoints |
| `test_contractor_features.py` | ~5 | Performance/ratings |
| `test_official_summary.py` | 6 | Per-language staff summaries |
| `test_multi_society_phase1.py` | 3 | society_id backfill |
| `test_foundation_f1.py` | 12 | RBAC matrix + deps |
| `test_foundation_f2_isolation.py` | 4 | Cross-society isolation |
| `test_foundation_f3_rbac.py` | 15 | Endpoint RBAC + per-society overrides |
| `test_categories_expansion.py` | 20 | 24-category enum + classifier |
| `test_e1a_schema.py` | 4 | New tables + columns + SLA seed |
| `test_e1b_routing.py` | 9 | Staff/contractor routing hierarchy |
| `test_e1b_prime_directory.py` | 12 | Vendor directory + RBAC + isolation |
| `test_e1b_double_prime_directory_intent.py` | 8 | "find a carpenter" intent |
| `test_e1c_escalation.py` | 13 | Manual escalate + hierarchy CRUD |
| `test_e2a_auto_escalation.py` | 12 | Auto-escalation job + cron endpoint auth |
| `test_e2b_reminders_and_updates.py` | 13 | Staff reminders + complainant updates |
| `test_e2c_weekly_summary.py` | 12 | Weekly HTML summary + idempotency |
| `test_e2d_incident_flagging.py` | 12 | Major-incident heuristics |
| `test_e3a_staff_crud.py` | 11 | Staff CRUD + RBAC + routing integration |
| `test_e3b_assign_staff.py` | 8 | Manual /assign accepts staff_id |

## 11. Design docs (chronological)

In `docs/`:
- `SESSION_HANDOFF.md` — running session-to-session state.
- `STATUS_REPORT.md` — external-review-ready report.
- `FRONTEND_GAPS_SCOPE.md` — i18n / RBAC scope decisions.
- `MULTI_SOCIETY_DESIGN.md` — Foundation phase locked decisions
  (R1 routing, per-society contractors, etc.).
- `ENTERPRISE_CM_ANALYSIS.md` — analysis of the full enterprise
  vision with the 4 locked decisions (scheduler, resident portal,
  reports format).
- `E1_DESIGN.md` — staff/escalation/SLA/routing phase plan.
- `E3_DESIGN.md` — role-aware frontend plan (E3a backend done;
  E3c..i Vue work pending).
- `PARKING_DESIGN.md` — Parking vertical on top of E2 engines (5
  sub-phases, one open question).
- `MORNING_BRIEF_2026-05-20.md` — yesterday's morning brief.

## 12. Phase status at a glance (as of `fd0ac95`)

| Phase | State |
|---|---|
| **Foundation (F1+F2+F3)** | ✅ shipped + deployed |
| Categories 7→24 | ✅ shipped + deployed |
| **E1a–c** (schema, routing, escalation) | ✅ shipped + deployed |
| **E1b'/b''** (vendor directory + WhatsApp intent) | ✅ shipped + deployed |
| **E2a–d** (cron + escalation + reminders + summary + incidents) | ✅ shipped + deployed |
| **E3a** (staff CRUD backend) | ✅ shipped — not yet deployed |
| **E3b** (assign staff via /assign) | ✅ shipped — not yet deployed |
| **E3c–i** (frontend role-aware UI) | ⏳ next major chunk |
| **Parking P1–P5** | ⏳ designed, not started |
| Cron pinger live in prod | ⏳ user's action: 5 min |
