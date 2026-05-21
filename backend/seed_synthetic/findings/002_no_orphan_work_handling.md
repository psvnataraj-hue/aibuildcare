# Finding 002 — No orphaned-work handling: deactivated staff retain assignments AND unroutable complaints have no retry

**Discovered**: 2026-05-21 (Gap 1, during Part 0 design audit
"does the deactivation flow reassign in-flight complaints?");
2026-05-22 (Gap 2, while verifying time-to-assignment of new
complaints).

**Severity**: MEDIUM. Both gaps degrade gracefully (escalation cron
still fires, nothing crashes) but produce confusing operator
experience: complaints in limbo that look like they're being
processed but aren't progressing.

**Status today**: Gap 1 is active (latent on Palms because the
production staff list has had few deactivations to date). Gap 2 is
dormant on the seeded demo data (every demo staff has a
`category_specialty` that matches a real category) but activates
the moment a customer is mid-onboarding with an incomplete staff
roster.

This finding has **two related gaps**:

- **Gap 1**: Deactivating a staff member or contractor leaves their
  existing complaint assignments dangling — no auto-reassignment,
  no surface tile.
- **Gap 2**: When `find_assignee` returns None at complaint creation
  (no eligible staff in the matched category), the complaint
  persists with `assigned_staff_id=NULL` forever — no cron job
  picks up unassigned complaints later.

Both produce the same symptom from the dashboard's perspective:
a complaint that exists, has a category, is "open" — but is not
actually being worked.

---

## Gap 1 — Deactivated staff retain their complaint assignments

### What's missing

When `staff_members.active` is flipped to 0 (or `contractors.is_active`
is flipped to 0):

- `complaints.assigned_staff_id` (or the equivalent contractor link)
  continues to point at the now-inactive person/vendor.
- The complaint's `status` stays in its current open state
  (`received` / `acknowledged` / `assigned` / `in_progress`).
- The escalation cron continues to advance the complaint up the chain
  on SLA breach — so the chain of command does get notified eventually.
- BUT the original assignee, being inactive, never receives reminders
  (`backend/app/services/jobs_service.py:155-166` filters reminders on
  `sm.active = 1`).
- AND nothing surfaces the orphan to a manager. There's no admin tile
  showing "you have 17 complaints assigned to deactivated staff."
- AND there's no `staff_service` hook that fires on deactivation to
  re-route in-flight work.

A search across the codebase for `orphan`, `reassign`, `stale`,
`departed`, `transferred_to` returns **zero hits**. There is no design
in place for this; it's just an unaddressed corner.

---

## Evidence

- `backend/app/services/staff_service.py:177-179` — `deactivate_staff()`
  is a single-table UPDATE flipping `active = 0`. No downstream
  side-effects, no orphan-detection trigger, no cron-job enqueued.
- `backend/app/services/routing_service.py:40,68` — the auto-router
  correctly filters on `active = 1` / `is_active = 1` for both staff
  and contractors, so NEW complaints never get assigned to deactivated
  records. Good. But this filter only applies at assignment time;
  existing assignments are untouched.
- `backend/app/services/jobs_service.py:155-166` — the reminder cron
  joins `staff_members sm ON sm.id = c.assigned_staff_id WHERE …
  AND sm.active = 1`. So reminders STOP for orphaned complaints —
  which makes them silently rot.
- `backend/app/services/escalation_service.py:60-132` — escalation is
  status-driven, not assignee-driven, so it WILL keep climbing the
  hierarchy. This is the silver lining: the chain of command does get
  visibility eventually, just without the original assignee's
  involvement.

---

## How the synthetic data surfaces this

Each demo society's Part 1 config (`*_residency.json`,
`*_nursing_home.json`, etc.) has a `churn_seeds` block specifying
3 deactivated staff + 1 retired contractor, each holding 1-4 open
complaints at deactivation time. At least one deactivated staff member
per society holds a **high-priority complaint that was already
escalated to L1 or L2** before they left — the worst-case orphan
shape.

When Part 3 (historical complaints) seeds, these orphans will be wired
up with the corresponding `assigned_staff_id` / `contractor_id`
pointers to the deactivated records. The walkthrough/demo step
(Part 6) will explicitly point at them in the dashboard so the gap is
visible, not hidden.

Per-society sample (from the configs):

| Society | Worst-case orphan |
|---|---|
| Greenwood | In-house electrician left 2026-04-28 with a high-priority Tower-C wiring complaint already at L2 (sr_manager) |
| Sunrise | Pharmacy assistant left 2026-05-08 with a high-priority stock-out ticket already at L1 (ward_admin) |
| Stellar | Catering lead quit mid-wedding 2026-05-05 with a high-priority Worli food-quality complaint already at L2 (sr_event_manager) |
| Meridian | Security guard terminated 2026-05-12 with a high-priority south-tower lobby security incident already at L2 (operations_manager) |

---

## Gap 2 — Unroutable complaints have no retry path

### What's missing

When a new complaint is created and `routing_service.find_assignee()`
returns `None` (because no staff in `staff_members` has a
`staff_categories` row with the parsed category and `active=1`, AND
no contractor fallback matches either), the complaint persists with
`assigned_staff_id = NULL` and `status = 'received'` forever.

The escalation cron WILL still climb the chain (escalation is
status-driven, not assignee-driven — so chairman eventually gets
WhatsApped), but **the auto-router never retries**. No cron job
picks up unassigned complaints. A human in the dashboard has to
spot the unassigned ticket and manually click Assign.

### Evidence

Grepped across the cron job-loop for any retry path:

- `backend/app/services/jobs_service.py` — searched `find_assignee`,
  `auto_assign`, `assigned_staff_id IS NULL`, `routing_service`.
  **Zero hits.** The tick only runs:
  `run_due_escalations`, `run_due_staff_reminders`,
  `run_due_complainant_updates`, `run_due_incident_flagging`,
  `run_due_weekly_summaries` — none of them re-attempt assignment.
- `backend/app/services/escalation_service.py` — same search, zero hits.
- `backend/app/services/incident_flagging.py` — same, zero hits.

So routing is fundamentally a one-shot, synchronous operation at
complaint creation. If it fails, the failure is permanent until a
human intervenes.

### Why this matters in practice

For Palms (sid=1), the staff roster has been built up over the
pilot period; `find_assignee` rarely returns None today. The gap is
dormant on the seeded demo tenants too (every Part 1 config has
`staff_roles[].category_specialty` matching at least one of its
seeded `categories`).

The gap activates the moment ANY of these is true:

- A real customer is mid-onboarding with their staff list still
  incomplete (e.g., they've added 5 staff but haven't yet entered
  the housekeeping specialty)
- A new complaint category gets parsed for which no staff has a
  matching specialty (e.g., a customer enables "Solar Panel
  Maintenance" as a category but hasn't yet added a solar
  specialist)
- The Haiku parser returns a category that's slightly off
  (e.g., "Air Conditioning" instead of the configured
  "AC/Cooling") — find_assignee returns None for the unmatched
  string, and the complaint silently sits unassigned even
  though there IS an AC plumber on the team

The third case is the most insidious — the data looks correct,
the staff exists, but a single-character category-string mismatch
breaks the routing.

### Adjacent observation

The escalation cron escalating on an unassigned complaint produces
a confusing UX: the system tells the L4 chairman "this complaint
is unresolved, please intervene" — but the chairman opens the
ticket and sees no assignee. The chain of command was alerted but
the work was never started. This is the same shape as Gap 1
(deactivated assignee → orphan) but with a different cause and the
opposite cure: Gap 1 needs reassignment of an existing-but-dead
pointer; Gap 2 needs initial assignment that never happened.

---

## Architectural decisions attached

Three options, escalating in scope:

**Option A — Surface only (cheapest).**

- New cron sub-job: `surface_orphaned_complaints()` runs daily, builds
  an admin tile "N complaints orphaned" with a drill-down list.
  Detects both Gap 1 (assigned_staff_id points to inactive staff) AND
  Gap 2 (assigned_staff_id IS NULL on a complaint older than X hours)
  in a single union query.
- No automatic re-routing. Manager handles each case manually via the
  existing assign endpoint.
- One new endpoint, ~80 lines (Gap 1 + Gap 2 detection), no schema
  change.

Pros: minimal blast radius, ships in half a day. Catches both gaps
with one mechanism.
Cons: doesn't actually FIX the orphans, just makes them visible. Manager
still has to click through each one.

**Option B — Auto-reassign on deactivation + periodic retry for unassigned.**

For Gap 1:

- On `deactivate_staff(sid)`: enqueue all that staff's open complaints
  back through `routing_service.find_assignee()` so a new active
  assignee is picked from the same category specialty.

For Gap 2:

- New cron sub-job `run_due_assignment_retries()` runs every tick:
  picks up all complaints with `assigned_staff_id IS NULL` AND
  `contractor_id IS NULL` older than ~5 min, attempts to re-route
  via `find_assignee()`. If still None after 24 hours, escalate to
  L1 with a `complaint_messages` entry tagged
  "no_eligible_assignee — manual assignment needed".

Both cases:

- Log each reassignment / retry in an `audit_trail` table or in the
  existing message log so the trail is visible.

Pros: actually resolves both gap classes. Audit trail preserves
history.
Cons: requires routing-service work + handling the "no eligible
assignee" edge case + ensuring the cron retry doesn't fight with a
human who's just clicked Assign. ~250-300 lines + audit-log schema.

**Option C — Full departure workflow.**

- `deactivate_staff()` becomes a multi-step flow requiring HR to
  designate a successor before the deactivation completes.
- New schema: `staff_departures` table tracking who left, when, who
  took over their open work.
- Notifications to both the manager and the designated successor.

Pros: production-grade departure handling. Audit-friendly.
Cons: significant UX work + product decisions ("can a deactivation be
done without a successor?"). Probably 3-5 days.

**Recommendation**: **Option A now, Option B before paying customer
#2 onboards**. Surfacing is fast and immediately useful. Auto-reassign
is the right "correct" behavior but it has edge cases that need
testing. Option C is overkill until there are multiple customers with
mature ops teams.

---

## Why this is medium not high severity

Unlike Finding 001 (admin leak), this gap **degrades gracefully**:

- No crash. No silent data loss. No cross-tenant exposure.
- Escalation still fires on the orphaned complaints — the chain of
  command still hears about them, just without the original assignee.
- Customers won't see this as a bug at first; they'll see it as "we
  have some stale assignments" and reassign manually.

The risk is that confidence erodes as the orphan count grows over
time. After 6 months in operation, a small society could easily have
20+ zombie complaints showing "assigned to [departed person]" — that
becomes the kind of thing that makes a customer wonder if the platform
is being maintained.

---

## Recommended next steps (separate change set)

1. Ship Option A (surface tile) as the next non-trivial improvement
   after the synthetic-data + diagnostics work lands. Half a day.
2. Schedule Option B (auto-reassign) before the second paying
   customer is onboarded. Same reasoning as Finding 001 — it doesn't
   matter much with one customer, it matters from the moment ops
   maturity varies between customers.
3. Defer Option C (full departure workflow) until there's at least
   one customer with a real HR ops team to inform the UX.
