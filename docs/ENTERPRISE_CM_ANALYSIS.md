# Enterprise Community Management — analysis & integrated plan

_2026-05-20. Analysis before code (per spec Part 0/11). Reconciles the
Enterprise CM spec with the already-locked multi-society tenancy work.
Approval required before implementation._

## 1. The central reconciliation

Enterprise CM **Part 1 (role hierarchy + RBAC)** and multi-society
**Phase 2 (identity + tenant isolation + RBAC)** are the *same
subsystem*. Building them separately = building auth/identity/RBAC
twice. **Decision: merge them into one Foundation phase**, designed
forward-compatible with everything downstream (staff/escalation,
parking).

Revised unified roadmap (supersedes the old "Phase 2 / Phase 7a-c"
split):

| Phase | Content | Depends on |
|---|---|---|
| **F. Foundation** | users↔society↔role; 10-role enum; RBAC permission matrix enforced via one dependency; `current_society()`; every query scoped; isolation+RBAC test suite | Phase 1 (done) |
| **E1. Enterprise core** | staff_members, staff_categories, contractor_categories, escalation_hierarchy, category_sla_config; routing_service; escalation state + escalate/respond/resolve endpoints (synchronous only) | F |
| **E2. Automation** | scheduler + escalation/reminder/complainant jobs; weekly summary; major-incident flagging | E1 + scheduler decision |
| **E3. Role dashboards** | Vue per-role dashboards; staff mobile view | E1/E2 |
| **P. Parking** | parking workflow on the E1/E2 escalation+notification engine | E1/E2 |

Parking is deliberately last: repeat-offender tracking = a
major-incident-flagging variant; owner notification = the notification
engine; clamping authorization = an RBAC level. Building it before the
engine means building parking-specific escalation that gets refactored
away.

## 2. Foundation phase — schema (additive)

- `users`: add `role` (already has a role col — widen to the 10-role
  enum), `society_id` (Phase 1 added). Add `phone` (resident/staff
  identity by phone), `is_active`.
- New `role` enum: resident, staff, contractor, manager, sr_manager,
  secretary, chairman, committee_member, enforcement_officer, viewer.
- RBAC = a single source-of-truth permission matrix (code constant) +
  one FastAPI dependency `require(permission)`; every mutating endpoint
  declares its permission. No per-endpoint ad-hoc checks.
- `current_society()` dependency derives society_id from the token's
  user; **clients never pass society_id**. Every read filters and
  every write stamps society_id.
- Isolation + RBAC test suite is the merge gate (society A token
  cannot read/mutate society B; a `staff` token cannot assign/escalate;
  etc.).

## 3. Enterprise E1 — schema

Per spec Part 2/3: `staff_members`, `staff_categories`,
`contractor_categories`, `escalation_hierarchy`, `category_sla_config`
(all `society_id`-scoped). Extend `complaints` with escalation
timestamps (Part 4.2) — additive, idempotent `ADD COLUMN IF NOT
EXISTS`. `routing_service` extends the existing `contractor_router`
(category → staff-then-contractor, workload-aware).

## 4. HONEST RISKS / GAPS (spec asked for these)

These are real and shape scope. None are blockers; several need a
decision.

1. **Background scheduler — biggest gap.** The spec's heart (escalation
   every 30 min, reminders hourly, weekly report) needs a scheduler.
   Render free = ONE web service, **no worker, no cron**. In-process
   APScheduler dies whenever the free instance sleeps (unreliable even
   with the UptimeRobot ping). **Recommended:** a secured internal
   endpoint `POST /internal/jobs/tick` (shared-secret header) hit by a
   free external cron (cron-job.org) every 15 min; the endpoint runs
   due escalations/reminders idempotently. Free, reliable enough for a
   pilot, no new infra. **Needs your approval** — it's an
   architectural choice.
2. **SMS to staff is the same India DLT wall.** Spec leans on
   "WhatsApp + SMS parallel" for staff. SMS to Indian numbers is
   DLT-blocked (already established for residents). **Recommend:**
   WhatsApp-first for staff too; SMS fallback is code-ready but
   dormant until DLT; "voice call escalation" deferred.
3. **Residents have no accounts.** RBAC lists `resident` with "view
   own complaints" (implies login). Today residents are phone
   identities via WhatsApp, no auth. A resident auth/portal is a large
   sub-project. **Recommend:** pilot keeps residents on WhatsApp only;
   `resident` role exists in the model but **no resident login/portal
   in MVP**; resident dashboard deferred out of E3.
4. **PDF weekly reports.** Chart.js is browser-side; server-side
   chart→PDF on a free instance is heavy. **Recommend MVP:** an HTML
   email summary (SendGrid) + the committee dashboard; defer
   PDF/charts to post-pilot.
5. **Real-time (spec 7c "Supabase Realtime").** App already has a
   WebSocket hub; reuse it. Do **not** add Supabase Realtime — avoid a
   second realtime stack.
6. **`system_config` per-society.** Foundation makes config
   society-scoped (already planned); `category_sla_config` and
   escalation hierarchy are inherently per-society.
7. **Test/infra load.** 141 → 185+ tests is fine; the cost is the
   scheduler + RBAC matrix correctness (the isolation/RBAC suite is
   the safety net).

## 5. Honest effort estimate (working sessions, not calendar)

| Phase | Scope | Estimate |
|---|---|---|
| F. Foundation | identity+tenant+RBAC+isolation suite | 2–3 focused sessions |
| E1. Enterprise core | 5 tables, routing, escalation sync, APIs, tests | 3–4 sessions |
| E2. Automation | cron endpoint + jobs + summary + flagging | 2–3 sessions |
| E3. Dashboards | per-role Vue + staff mobile (resident deferred) | 3–4 sessions |
| P. Parking | on top of the engine | 1–2 sessions |

This is a multi-week program. Each phase is independently shippable,
tested, and deployed before the next.

## 6. Decisions — LOCKED 2026-05-20
A. ✅ **Merge approved** — multi-society Phase 2 + Enterprise Part 1 =
   one Foundation phase. Order F→E1→E2→E3→P approved.
B. ✅ **Scheduler = external cron → secured `/internal/jobs/tick`**
   (shared-secret), free external trigger, idempotent. For E2.
C. ✅ **Resident login/portal DEFERRED** — residents stay WhatsApp-only
   for the pilot; `resident` role exists in the model, no portal.
D. ✅ **MVP reports = HTML email + dashboard**; PDF/charts post-pilot.
E. Pilot effectively 1–few societies near-term; Foundation first
   regardless.
