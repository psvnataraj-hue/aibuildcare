# Synthetic test-data system

Permanent, isolated demo tenants for end-to-end testing and demos.
**Real pilot data (Palms Residency, society_id=1) is structurally
protected** — see *Isolation guarantees* below.

## Tenants

| society_id | name | vertical | config file |
|---|---|---|---|
| 1 | Palms Residency | real pilot — **never touched by this system** | (none — production data) |
| 100 | Greenwood Residency | residential society | `greenwood_residency.json` |
| 101 | Sunrise Nursing Home | hospital (rooms + beds, **no patients**) | `sunrise_nursing_home.json` |
| 102 | Stellar Events | event management company | `stellar_events.json` |
| 103 | Meridian Estate Office | office estate | `meridian_estate_office.json` |
| 100 (overlay) | Parking — Greenwood | residential parking — per-unit slots, 9 violation types | `parking_scenario_greenwood.json` |
| 103 (overlay) | Parking — Meridian | office parking — per-tenant-suite slots, cab-zone, exec-reserved, after-hours rules | `parking_scenario_meridian.json` |

Each config doubles as a real-onboarding template. To onboard a real
society/hospital/event-co/estate, copy the matching file, change `sid` +
identity fields, set `_meta.is_demo = 0`, switch `sla_config` to realistic
hours, and feed it through the seeder. Same shape, different values.

## Isolation guarantees (Part 0-A)

Two **independent** guards prevent demo data from ever touching real data,
and prevent the wipe utility from ever destroying real data:

1. **`societies.is_demo` flag** — added via migration `004_is_demo_flag.sql`.
   Demo societies are inserted with `is_demo=1`. The wipe utility refuses
   to operate on any society where `is_demo != 1`.

2. **Hardcoded `sid == 1` refusal** — a second, independent guard. Even if
   someone manually flips `societies.is_demo = 1` for sid=1, the wipe
   utility *also* checks `if sid == 1: refuse` and aborts. Both guards
   must fail simultaneously for real data to be at risk.

Real data is protected by `(is_demo == 1) AND (sid != 1)` — defense in depth.

## Cron safety (Part 0-B)

Synthetic data must never trigger a flood of real WhatsApp messages.
Three independent layers — any one alone is sufficient:

1. **Status-based skip (already in cron):** historical seeded complaints
   are inserted with `status IN ('resolved','closed','cancelled')` plus
   correct historical timestamps (`created_at`, `resolved_at`,
   `escalated_to_*_at`). The cron's `_OPEN_STATES` filter at
   `backend/app/services/jobs_service.py:24` skips them entirely.

2. **Reserved test-phone range:** all synthetic people use 10-digit
   Indian mobiles in the test range `+91 99000 XXXXX`. The 5-digit
   local part is banded by role for operator log readability:
   `+91 99000 0NNNN` users, `+91 99000 1NNNN` staff, `+91 99000 2NNNN`
   contractors, `+91 99000 3NNNN` vehicle owners (non-user). Within each
   band, society-offset blocks of 250 keep numbers globally unique
   (Greenwood 0000-0249 / Sunrise 0250-0499 / Stellar 0500-0749 /
   Meridian 0750-0999). The chokepoint in
   `backend/app/services/notify.py` (Part 4) will short-circuit to a
   logged `TEST_PHONE_SKIPPED` event for any number whose prefix matches
   `AIBUILDCARE_TEST_PHONE_PREFIXES` (default: `+919900`).

3. **Seeding lock env (`AIBUILDCARE_SEEDING_LOCK=1`):** when set, the
   `/internal/jobs/tick` route returns 202 immediately without running
   any cron work. Set BEFORE seeding; unset AFTER verifying all seeded
   historical complaints are in non-open status. Insurance against bugs.

## Per-tenant SLAs (Part 0-C)

Demo tenants get ultra-short SLAs so escalation is testable in minutes:

| Level | Demo (sid 100-103) | Real (sid 1, Palms) |
|---|---|---|
| L1 (manager) | 2 min | 2 h |
| L2 (sr manager) | 4 min | 4 h |
| L3 (secretary) | 6 min | 8 h |
| Resolution | 3 min | 4-24 h |
| Response | 1 min | 15-120 min |

SLAs live per-(society_id, category) in `category_sla_config`, so a single
cron tick correctly handles Palms (8h L3) and Greenwood (6min L3)
side-by-side without code changes. The cron itself still runs every 15 min
(cron-job.org cadence) — testers use the "trigger escalation check now"
button (Part 5-2) for faster loops.

## Hospital data boundary (Sunrise Nursing Home — designed, not omitted)

This deployment processes facility operations only. The boundary below is
an **architectural property** of the platform, not a coverage gap.

**What the platform sees, by design:**

- the physical location of a complaint — wing / department / room / bed
- the operational request — *"AC not cooling"*, *"nurse-call button broken"*,
  *"linen not changed"*, *"lift stuck at 3rd floor"*
- the staff handling the request (assignee + escalation chain)
- any photos of physical infrastructure attached to the complaint

**What never enters the platform, by design:**

- patient identity — name, MRN, admission number, bed-occupant linkage
- diagnoses, conditions, medications, procedures, treatment history
- any clinical content of any kind
- insurance, billing, consent forms
- patient lifecycle events — admissions, discharges, transfers

Nothing in the above list is written to `complaints.text`, sent to
Anthropic (parser), traversed by Sarvam (STT/TTS), stored in Supabase,
emitted via Twilio / SendGrid, or recorded in the audit log. The platform
is built so the hospital does not have to engineer redaction layers
around it — routing on infrastructure alone is sufficient for the
facility-management use case.

**Why this matters legally.** Under DPDP Act 2023, patient health
information is *sensitive personal data* with stricter consent,
purpose-limitation, and retention requirements. By keeping clinical
content out of the system entirely, this deployment stays cleanly within
the act's operational-data category — no special handling, no
patient-consent flows, no cross-border data concerns.

**What the hospital is responsible for.** Intake. If a resident-facing
WhatsApp message attempts to include clinical content ("patient in 304
with diabetic emergency, AC not working"), the hospital's intake process
must redact the clinical portion before submission. The platform's role
is to make that redaction trivial — by only needing the location + the
infrastructure problem, never the patient context — not to attempt
clinical-content detection itself.

This boundary is restated in `sunrise_nursing_home.json` under
`_meta.design_notes` so it travels with the config file.

## Editing a config file

Each config is a single JSON document with these top-level sections:

```
_meta              { vertical, description, design_notes, is_demo, sid }
society            { name, address, timezone }
structure          { vertical-specific: towers/units, rooms/beds, events, suites }
categories         [ { name, priority_default, common, sla_override? } ]
staff_roles        [ { role_key, title, count, category_specialty?, in_chain? } ]
churn_seeds        { deactivated_staff[], retired_contractor }
escalation_chain   [ { level, role_key } ]
sla_config         { default, overrides }
contractor_specialties [ { category, vendor_name, rating, count } ]
```

Hand-edit freely. The seeder (Part 6, not yet built) will read these and
produce DB inserts. No code changes needed when you tweak counts,
categories, vendor names, or SLA values.

**Catch-all guarantee.** Every vertical's `categories` array ends in an
`"Other"` row — when the parser's category-confidence is below threshold
or the complaint doesn't match any known category, routing falls through
to `"Other"` rather than failing. This is verified across all four
configs (Greenwood, Sunrise, Stellar, Meridian).

## What this directory does NOT contain

- **Synthetic people records** — those are Part 2 (`synthetic_people.py`
  or similar, generated deterministically from these configs)
- **Historical complaints** — those are Part 3
- **The seeder itself** — Part 6 (`runner.py`)
- **The wipe utility** — Part 6 (`wipe_society.py`)
- **Diagnostics / health-monitoring code** — Part 4 (separate location)
- **Tester support** — Part 5 (separate location)
