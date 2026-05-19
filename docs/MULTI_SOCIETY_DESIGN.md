# Multi-society tenancy — design plan (gap #2 = level C)

_2026-05-19. Approve architecture + the inbound-routing fork before
implementation. Estimated 1–2 weeks, phased._

## Goal
Every society's data is isolated. A logged-in user only ever sees/acts
on their society's complaints, contractors, config, analytics. Inbound
complaints (WhatsApp/SMS/email/form) are routed to the correct society.

## Scope of change (every domain query)
Add `society_id` to: `complaints`, `contractors`, `categories`,
`system_config`, `units`, `users`. Today these are global. Backfill the
existing seed rows to a default society (complaints table is already
empty — clean). Then **filter every read and stamp every write** by the
caller's society.

## The pivotal decision — inbound channel → society routing
Dashboard requests carry a user → society is known. **Inbound resident
messages have no user.** A resident WhatsApps a number — *which
society?* Options:

| Option | How | Pilot fit |
|---|---|---|
| **R1. Per-society inbound identifiers** | Each society gets its own Google Form + email alias (`<society>@complaints…`) + (later) its own WhatsApp/SMS number. Webhook resolves society from the destination. | **Recommended** — Form/email are free & trivial per society; matches how you'd onboard a society anyway |
| R2. Sender registry | Map resident phone/email → unit → society. Unknown senders rejected/queued. | Heavier; fails for first-time senders; needs a resident directory |
| R3. Single inbox + manual triage | All inbound lands unassigned; staff pick society | Defeats automation |

**Recommendation: R1.** Per-society Form + email now; per-society
WhatsApp/SMS number when Twilio goes live (until then WhatsApp can map
via a default society or the sandbox per-society keyword). This also
makes the existing per-society `official_summary_languages` natural.

## Auth/identity model
- Each `user` belongs to one `society_id` (pilot). A `superadmin` role
  may span societies (optional, later).
- JWT already carries the user; resolve `society_id` from the user on
  each request via a FastAPI dependency `current_society()`.
- This **subsumes multi-user/RBAC** (level B) — multi-society implies
  multiple users per society, so we also add: staff invite/list,
  `admin`/`staff` roles, RBAC guard on mutating endpoints.

## Enforcement strategy (anti-leak)
- A single `scoped(conn, society_id)` query helper / mandatory
  `society_id` arg on every service function — no service reads
  complaints/contractors without it.
- The dashboard never passes society_id from the client; it is derived
  server-side from the token. Client cannot request another society.
- **Isolation test suite**: seed 2 societies, assert society A's
  token cannot read/list/get/mutate any of society B's complaints,
  contractors, config, analytics (the gate for "done").

## Phased build (each phase = its own tests, independently shippable)
1. **Data model + migration**: add `society_id` cols (idempotent ADD
   COLUMN IF NOT EXISTS for prod), backfill seed → default society,
   `societies` CRUD seed. No behaviour change yet.
2. **Auth scoping (dashboard side)**: `current_society()` dependency;
   every read/write in `complaint_service`/`contractor_router`/
   analytics/`system_config` takes & enforces `society_id`. Isolation
   tests go green here.
3. **Inbound routing (R1)**: per-society Form/email/number → society
   resolution in webhooks; default-society fallback + audit log.
4. **Users & RBAC**: staff invite/list endpoints, roles, RBAC guard;
   frontend society context + user-management UI + real `/me` identity
   (kills the hard-coded admin).
5. **Per-society config**: `system_config` keyed by society (incl.
   `official_summary_languages`); migrate the global key.
6. **Hardening**: full isolation test matrix, docs, status report.

## Risks
- Cross-society leak via a missed query — mitigated by the mandatory
  society_id arg + isolation suite as the merge gate.
- Inbound mis-routing → a complaint in the wrong society. Mitigated by
  R1 + default-society quarantine + audit.
- Prod migration on Supabase (idempotent ALTER, empty complaints).

## Decisions — LOCKED 2026-05-19
1. **R1 approved** — per-society inbound identifiers (Form/email now,
   per-society WhatsApp/SMS number when Twilio is live).
2. **Per-society contractors & categories** — each society has its own
   roster and category/SLA set. (Implies categories uniqueness becomes
   `(society_id, name)` and `system_config` becomes society-keyed —
   these constraint/PK reshapes are deferred to the phases that need
   them; Phase 1 is additive nullable columns only, to stay idempotent
   and behaviour-neutral on prod.)
3. Phased order approved — Phase 1 starts now.
