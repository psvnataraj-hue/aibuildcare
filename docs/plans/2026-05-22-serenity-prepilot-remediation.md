# Serenity Pre-Pilot Remediation Plan

> **For Claude:** Execute finding-by-finding. Each finding = its own branch + PR.
> Tests stay green after every PR. Pause and report at each checkpoint.
> Detailed bite-sized TDD steps are worked out at the START of each PR's
> execution, not here — this document is the consolidated approve-once plan.

**Goal:** Close all 6 known findings (+ 1 UX gap surfaced during seeding)
so AIBuildCare is code-complete for the Serenity pre-pilot.

**Architecture:** 6 sequential PRs against `main`, ordered by dependency.
Finding 001 (tenant isolation) is foundational and goes first; everything
after is verified against correctly-scoped multi-tenant behaviour using the
now-live demo tenants (sid 100-103).

**Tech stack:** FastAPI + Python 3.12 + raw parameterised SQL; Vue 3 + TS +
Vite + Tailwind; Supabase Postgres; Render (manual-sync deploy).

**Test gate:** 413 passing today. Every PR must keep that green (count may
rise as new tests are added). No CI on the repo — `pytest --no-cov` locally
is the gate.

---

## Execution order + dependency reasoning

| PR | Finding | Why this position |
|----|---------|-------------------|
| 1 | 001 — tenant-scoped admins + `platform_operator` | Architectural, touches ~9 files. Everything else should be verified against a correctly-scoped system. Demo tenants are live → the fix is verifiable against real multi-tenant data. |
| 2 | 006 — email-webhook security | HIGH severity. Also gates the email-channel wiring (item 8) — must land before any MX record. |
| 3 | 002 — orphan-work surfacing | Low risk, additive. Its new endpoint folds into `diagnostics.py`, which PR 1 also edits — so it goes *after* 001 to build on the corrected scoping pattern. |
| 4 | 004 — delivery proof (Option A) | New table + endpoint. Independent; touches `webhooks.py` + `config.py` (so does PR 2 — PR 4 rebases on PR 2). |
| 5 | 005 — dashboard photo upload + voice-fallback signal | Frontend + schema. Independent. |
| 6 | 003 + society-name — terminology + tenant display | Frontend polish. Bundled (both are small user-facing-text changes). Last because cosmetic. |

This matches the order you suggested. The only dependency note: **002 after
001** (shared `diagnostics.py`), and **003 + society-name bundled** into one PR.

---

## PR 1 — Finding 001: tenant-scoped admins + `platform_operator` role

**Severity:** HIGH. **Risk:** HIGH (architectural; most likely to break tests).

### Decision made (yours)
`admin` becomes tenant-scoped — a customer admin sees only their own
society. A new `platform_operator` role is added for Nataraj's legitimate
cross-tenant access.

### Scope — the audit found 11 leaks, not 3
The finding doc named `/analytics`, `/contractors`, `/admin/permissions*`.
The full audit found **eight more**:

1. `GET /api/v1/analytics` — `complaint_service.analytics()` runs 4 queries with no `WHERE society_id`
2. `GET /api/v1/contractors` — inline query, no society filter
3. `GET /api/v1/contractors/analytics/summary` — global contractor counts
4. `GET /api/v1/contractors/{cid}/analytics` — no society check, any cid
5. `GET /api/v1/contractors/by-category` — no society filter
6. `GET /api/v1/contractors/performance` — global
7. `GET /api/v1/contractors/{cid}/performance` — no society check
8. `GET/POST /api/v1/admin/config[/{key}]` — `system_config` not society-scoped
9. `WS /api/v1/ws` — `ws_hub.broadcast` is global: **every connected client receives every society's complaint events** (real-time cross-tenant leak)
10. `GET/PUT/DELETE /api/v1/admin/permissions*` (4 routes) — `_target_society()` lets admin pass `?society_id=`
11. `GET /api/v1/diagnostics/events` (admin branch) + `POST /events/seen` — gated on `admin`, should be `platform_operator`

### Files
- **Modify** `backend/app/services/rbac.py` — add `platform_operator` to `ROLES` + `ROLE_PERMISSIONS` (= `ALL_PERMISSIONS`); **delete both `if role == "admin"` short-circuits** (`permissions_for()`, `has_permission()`). `admin` then resolves through the normal matrix — still `ALL_PERMISSIONS`, but now scoped by `society_id` at the router layer like every other role.
- **Modify** `backend/app/deps.py` — add a `target_society()` dependency: returns `user.society_id` for normal roles (ignores any `?society_id=`), but for `platform_operator` returns the requested `?society_id=` (or an all-societies sentinel). Make `current_society` tolerate a `platform_operator` with NULL society_id.
- **Modify** `backend/app/routers/complaints.py` — the contractor sub-endpoints (lines ~121-156) gain `sid = Depends(current_society)` and pass it through; `/analytics` + `/contractors` likewise.
- **Modify** `backend/app/services/complaint_service.py` — `analytics()`, `analytics_summary()`, `contractor_performance()`, `contractor_analytics()` gain a `society_id` param + `WHERE society_id = ?`.
- **Modify** `backend/app/services/contractor_router.py` — `contractors_by_category()` / `_candidates()` gain society filter.
- **Modify** `backend/app/routers/admin.py` — `_target_society()`'s privileged branch checks `platform_operator`, not `admin`.
- **Modify** `backend/app/routers/diagnostics.py` — events endpoints gate on `platform_operator`.
- **Modify** `backend/app/services/ws_hub.py` + `routers/complaints.py:349` — per-society broadcast rooms (clients only receive their own society's events).
- **Modify** `backend/app/seed.py` — seeded `admin@aibuildcare.app` → role `platform_operator`; exclude it from the society backfill so it stays cross-tenant.
- **Migration** `007_*.sql` — a one-line data migration if prod's `admin@aibuildcare.app` has a non-NULL `society_id` (the seed backfill may have pinned it to society 1); set role = `platform_operator`.
- **Tests** — new `rbac` tests for `platform_operator`; per-society isolation tests for all 11 endpoints (now verifiable against demo tenants 100-103).

### Risk / test impact
- **Biggest test-breaker:** if `platform_operator` ends up with NULL `society_id`, every test that logs in as the seed admin and hits a `current_society` endpoint will 403. Mitigation is part of the `target_society` design — verify the 413-suite after the deps change before going further.
- Tests asserting *global* analytics totals will shift to per-society — expected; update them.
- WS broadcast contract changes — WS integration tests need a society context.

### Decisions needed → see consolidated list (D1, D2, D3)

---

## PR 2 — Finding 006: email-webhook security

**Severity:** HIGH (security). **Risk:** MEDIUM (breaks 2 existing webhook tests).

### Scope
The inbound-email webhook is unauthenticated, ignores the `to:` domain, and
drops attachments. Fix all three.

### Files
- **Modify** `backend/app/config.py` — add `sendgrid_inbound_secret: str = ""` and `inbound_email_allowed_domains: str = "carimotech.in"`.
- **Modify** `backend/app/routers/webhooks.py` — `_handle_inbound_email`:
  - (a) shared-secret check at handler entry (model on `internal_jobs.py`'s `secrets.compare_digest` pattern; 403 on mismatch, 503 if unset)
  - (b) read `to:`, reject if domain not in the allowlist
  - (c) iterate `attachment\d+` form fields, upload each via `r2_client.upload_bytes()`, pass URLs to `create_complaint(image_urls=...)`
- **Tests** — rewrite `test_webhook_no_auth_required` (asserts removed behaviour); update `test_sendgrid_inbound_email` to send the secret header; add 403-on-bad-secret, domain-rejection, attachment→R2 tests; `conftest.py` sets `AIBUILDCARE_SENDGRID_INBOUND_SECRET`.

### Risk / test impact
2 existing webhook tests break and must be updated **in this PR**. No migration.

### Decisions needed → D7 (minor, recommendations given)

---

## PR 3 — Finding 002: orphan-work surfacing (Option A)

**Severity:** MEDIUM. **Risk:** LOW (purely additive — one read-only cron sub-job + one GET endpoint).

### Scope
Surface both orphan classes: (Gap 1) complaints assigned to deactivated
staff/contractors; (Gap 2) unassigned complaints sitting past N hours.
**Option A = surface + notify, no auto-reassignment.**

### Files
- **Modify** `backend/app/services/jobs_service.py` — add `surface_orphaned_complaints(now)` sub-job (~50 lines, modelled on `run_due_staff_reminders`); register it in the `run_tick` job loop; emit an `operator_events` row (`event_type='orphaned_complaints_detected'`) so the diagnostics tile picks it up.
- **Modify** `backend/app/routers/diagnostics.py` — add `GET /api/v1/diagnostics/orphaned-complaints` (society-scoped via the post-PR-1 pattern). Detection = a UNION query: assigned-to-inactive-staff/contractor OR unassigned-past-N-hours.
- **Tests** — new `test_orphaned_complaints.py`: seed an inactive-staff assignment + a stale unassigned complaint, assert both surface, assert society-scoping.

### Risk / test impact
LOW — additive, read-only, inside the per-job try/except. No migration.

### Decisions needed → D4 (Option A vs B), D8 (minor)

---

## PR 4 — Finding 004: delivery proof (Option A — status callbacks, NO read receipts)

**Severity:** HIGH (accountability). **Risk:** LOW-MEDIUM.

### Scope
Persist per-message delivery status for outbound WhatsApp/SMS. Read receipts
are explicitly out of scope (need production WhatsApp Business API).

### Files
- **Migration** `008_outbound_messages.sql` (standalone, idempotent) **+ inline `CREATE TABLE IF NOT EXISTS` in both `001_init.sql` and `001_init_pg.sql`** (the established pattern — `init_db()` only loads `001_init*`). Columns: `id, complaint_id, society_id, provider, provider_message_id (indexed), recipient, channel, status, error_code, sent_at, status_updated_at, raw_callback_meta`.
- **Modify** `backend/app/config.py` — add `public_base_url: str = ""`.
- **Modify** `backend/app/services/notify.py` — the 3 `client.messages.create()` calls gain `status_callback=<public_base_url>/webhooks/twilio/status`; capture the returned `MessageSid`; insert an `outbound_messages` row **inside its own inner try/except** so a logging-DB failure can never break a send.
- **Modify** `backend/app/routers/webhooks.py` — add `POST /webhooks/twilio/status`, validated via `X-Twilio-Signature`. Updates the matching `outbound_messages` row by SID.
- **Tests** — new `test_outbound_messages.py`: SID persisted on send (mock Twilio), status webhook updates the row.

### Migration-number note
Latest standalone migration is `005`. PR 1 may add `007`. So this is `008` —
the executor confirms the next free number at PR-4 start.

### Decisions needed → D9, D10 (minor, recommendations given)

---

## PR 5 — Finding 005: dashboard photo upload + voice-fallback signal

**Severity:** MEDIUM. **Risk:** MEDIUM (file upload + R2 + multipart).

### Scope
- Add an image-upload field to the dashboard complaint-creation form.
- Signal to the user when a voice-note TTS reply silently fell back to text.

### Files
- **Modify** `backend/app/schemas.py` — `ComplaintCreate` gains `image_urls: list[str] | None = None`. (The service layer `parse_complaint(raw_text, image_urls)` already accepts it — only the schema + the dashboard call path are missing.)
- **Modify** `frontend/src/views/Complaints.vue` — the create form (a single text input today) gains a file/image upload control; uploaded files go to R2; URLs passed to `api.createComplaint`.
- **Modify** `frontend/src/api.ts` — `createComplaint` signature gains `image_urls`.
- **Modify** `backend/app/routers/webhooks.py` `_maybe_voice_reply()` — when `tts.synthesize()` returns `None`, insert a `system`-sender `complaint_messages` row ("voice reply unavailable — text sent instead") so it shows in `ComplaintDetail.vue`.
- **Tests** — schema test for `image_urls`; voice-fallback signal test.

### Decisions needed → D11, D12 (minor, recommendations given)

---

## PR 6 — Finding 003 + society-name: terminology + tenant display

**Severity:** LOW (cosmetic) but high-impact at non-housing demos. **Risk:** LOW.

### Scope
- Rename user-facing "complaint/complainant" → "request/requester" (UI text + WhatsApp/email message strings). Internal identifiers, routes, DB columns STAY.
- Show the logged-in user's society name on the dashboard.

### Files (Finding 003)
- **Modify** `frontend/src/lib/i18n.ts` — 4 dict entries (`en` + `hi`), the highest-leverage change.
- **Modify** ~6 view components — `Complaints.vue`, `Dashboard.vue`, `ComplaintDetail.vue`, `MyWork.vue` (≈10 visible strings).
- **Modify** `backend/app/services/haiku_parser.py` — reword the system prompt so LLM-generated acknowledgements say "service request"; `weekly_summary.py` email strings.

### Files (society-name)
- **Modify** `backend/app/routers/auth.py` — `/api/v1/auth/me` returns `society_name` (join `societies`), not just `society_id`.
- **Modify** `frontend/src/api.ts` — `CurrentUser` interface + `frontend/src/App.vue` header to display the society name; also un-hardcode the `"Nataraj (Admin)"` profile-dropdown text → bind to `currentUser`.

### Decisions needed → D5, D6 (Hindi term, rename scope)

---

## Research item 7 — Indian WhatsApp BSP

**Question:** which BSP integrates cleanest with our Twilio-built layer, how
much rework, any Twilio-compatible API.

### How our messaging layer is built (the thing that determines rework)
All outbound goes through **one chokepoint**: `notify.py` — 4 functions
(`send_whatsapp`, `send_whatsapp_media`, `send_sms`, `send_email`). Inbound is
parsed in `webhooks.py`. Delivery-status (after PR 4) is one endpoint. So a
BSP switch rewrites the *insides* of those — **not** the callers
(`complaint_service`, `escalation_service`, `jobs_service` are untouched).

### The four BSPs
| BSP | Shape | Developer API for send + inbound webhook + delivery-status webhook |
|-----|-------|--------------------------------------------------------------------|
| **MSG91** | CPaaS (SMS+WhatsApp+email+OTP) | **Yes — full.** "Send Template" + "Send Message" APIs; webhook events incl. *On Outbound Report Received* = Sent/Delivered/Read/Failed, *On Inbound Request Received*. Maps cleanly onto PR 4's delivery-tracking. |
| **Gupshup** | Enterprise BSP | **Yes — full.** The most developer-focused of the four (its own comparison page calls the UI "developer-focused, limited visual tools"). Audit-grade logs. Own REST API. |
| **AiSensy** | Marketing/broadcast tool | Partial — API exists but campaign/broadcast-shaped, not raw CPaaS. |
| **Interakt** | CRM / e-commerce tool | Partial — API exists but catalog/Shopify/CRM-shaped. |

### Answers
- **Twilio-compatible drop-in API?** No — none of the four mimics Twilio's
  `client.messages.create` shape. (Twilio's API is distinctive.) But this
  matters little because of the chokepoint design.
- **Cleanest integration:** **MSG91 or Gupshup** — both are true CPaaS-grade
  with the three primitives we need (programmatic send, inbound webhook,
  delivery-status webhook). MSG91's *On Outbound Report Received* event model
  is a near-direct fit for the `outbound_messages` table PR 4 builds.
  AiSensy/Interakt are marketing/CRM tools — usable but a worse fit for a
  ticketing backend.
- **Rework estimate:** rewrite the 4 `notify.py` function bodies + the inbound
  parser in `webhooks.py` + the status-callback endpoint. **~1-3 days**
  depending on BSP. Callers untouched. If PR 4 (delivery proof) lands first,
  the `outbound_messages` table + status endpoint already exist — the BSP
  switch just repoints them.
- **Worth knowing:** most BSPs now provision a number on **Meta's WhatsApp
  Cloud API** and let you talk to that directly. Going Cloud-API-direct
  avoids BSP lock-in entirely. A BSP that supports this (MSG91 and Gupshup
  both do) is the most future-proof.

**Recommendation:** shortlist **MSG91 vs Gupshup**, pick on cost + the
number-provisioning experience. Defer the actual migration to its own scoped
step *after* the 6 fix PRs — do NOT fold it into this pass.

---

## Note item 8 — email-channel wiring (after PR 2)

Once PR 2 (Finding 006) lands, going live on `complaints@carimotech.in` needs
the ~30-min ops step:
1. MX record at Hostinger → `mx.sendgrid.net`
2. SendGrid Inbound Parse: host `carimotech.in` → `https://aibuildcare-api.onrender.com/webhooks/sendgrid/email`, **with the shared-secret header** PR 2 adds
3. Test with a real email

**Sequencing rule:** the MX record must NOT be added before PR 2 is deployed —
until the webhook has auth, a public URL = an open spam endpoint. Lower
priority overall: the pre-pilot is WhatsApp-only.

---

## Consolidated decisions for approval

Approve all, or override specific ones by number.

| # | Decision | My recommendation |
|---|----------|-------------------|
| D1 | Existing `admin@aibuildcare.app` → role `platform_operator` (your cross-tenant login) | ✅ Yes |
| D2 | `platform_operator` tolerates NULL `society_id`; cross-tenant endpoints use a new `target_society` dep that honours `?society_id=` only for that role | ✅ Yes |
| D3 | Fix the WebSocket per-society broadcast leak **inside PR 1** (it's a 001-class leak, just not in the original doc) | ✅ Yes — include it |
| D4 | Finding 002 = **Option A (surface + notify)**, not Option B (auto-reassign). Your task said "reassign OR surface+notify" — Option A is the lower-risk pre-pilot choice; Option B can follow post-pilot | ✅ Option A |
| D5 | Hindi rename: शिकायत (*shikayat* = complaint) → अनुरोध (*anurodh* = request) | ✅ Yes — confirm the word |
| D6 | Terminology rename covers **all** user-facing text incl. staff-facing weekly-summary email (not just resident-facing) | ✅ Yes |
| D7 | 006: inbound-secret as inline header check (not a FastAPI dependency); domain allowlist as env CSV | ✅ recommend, minor |
| D8 | 002: Gap-2 staleness threshold = env-configurable, default 4h | ✅ recommend, minor |
| D9 | 004: status-callback auth via `X-Twilio-Signature` HMAC (Twilio signs natively) | ✅ recommend, minor |
| D10 | 004: `outbound_messages` insert in its own inner try/except so a logging failure never breaks a send | ✅ recommend, minor |
| D11 | 005: voice-fallback signal as a `system` thread message (visible in ComplaintDetail) | ✅ recommend, minor |
| D12 | 005: image upload widget lives in the dashboard create-form (Complaints.vue) | ✅ recommend, minor |

D1-D6 are the ones that genuinely shape behaviour. D7-D12 are implementation
defaults — flagged for visibility; I'll proceed on the recommendation unless
you say otherwise.

---

## Per-PR checkpoint protocol (STEP 3)

For each PR: branch off `main` → detailed TDD steps → implement test-first →
`pytest --no-cov` green → self-review → push → open PR → report to you →
pause. Next PR rebases on the merged previous one.

After all 6: **STEP 4** — updated walkthrough so you can walk the seeded
dashboard and catch any remaining UX gaps.
