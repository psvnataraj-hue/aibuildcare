# Finding 002 — No orphaned-work handling when staff or contractors deactivate

**Discovered**: 2026-05-21, during Part 0 design audit ("does the
deactivation flow reassign in-flight complaints?"). The synthetic-data
build's Part 0-E scenarios are deliberately seeded so this gap becomes
visible in the walkthrough/demo report rather than papered over.

**Severity**: MEDIUM. Degrades gracefully (escalation cron still fires,
nothing crashes) but produces a confusing operator experience: an "open"
complaint assigned to a person who no longer exists, with no nudge, no
re-assignment, no surfacing.

**Status today**: active. The current production DB has one society and
few deactivation events, so the gap hasn't surfaced operationally. But
the moment a single staff member is deactivated while holding open
work, the orphan exists.

---

## What's missing

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

## Architectural decisions attached

Three options, escalating in scope:

**Option A — Surface only (cheapest).**

- New cron sub-job: `surface_orphaned_complaints()` runs daily, builds
  an admin tile "N complaints assigned to deactivated staff" with a
  drill-down list.
- No automatic re-routing. Manager handles each case manually via the
  existing assign endpoint.
- One new endpoint, ~50 lines, no schema change.

Pros: minimal blast radius, ships in half a day.
Cons: doesn't actually FIX the orphans, just makes them visible. Manager
still has to click through each one.

**Option B — Auto-reassign on deactivation.**

- On `deactivate_staff(sid)`: enqueue all that staff's open complaints
  back through `routing_service.assign()` so a new active assignee is
  picked from the same category specialty.
- Log each reassignment in an `audit_trail` table or in the existing
  message log.
- If no eligible assignee exists (category specialty has no active
  staff left), fall back to escalating to L1 manager + flagging.

Pros: actually resolves the orphans. Audit trail preserves history.
Cons: requires routing-service work + handling the "no eligible
assignee" edge case. ~200 lines + schema for audit log if it doesn't
already exist.

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
