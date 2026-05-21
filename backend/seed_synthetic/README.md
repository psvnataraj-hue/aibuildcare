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
| 100 (overlay) | Parking scenario | overlays Greenwood — parking-specific data | `parking_scenario.json` |

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

2. **Reserved test-phone range:** all synthetic people use phone numbers
   in the prefix range `+919900000xx`, `+919900001xx`, `+919900002xx`
   (env-overridable via `AIBUILDCARE_TEST_PHONE_PREFIXES`). The Twilio /
   SendGrid chokepoint in `backend/app/services/notify.py` short-circuits
   to a logged `TEST_PHONE_SKIPPED` event for any number in this range.

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

## Hospital DPDP design decision (Sunrise Nursing Home)

**Patients are deliberately not modeled.** The config tracks rooms, beds,
and departments; complaints route on `(room, bed, department)` — never
on patient name or ID.

Reasoning:

- DPDP Act 2023 classifies patient health information as sensitive personal
  data with stricter consent + retention requirements
- Routing on physical infrastructure (rooms/beds) is sufficient — a
  complaint says "ICU-101-B2 nurse-call button broken" not "patient X's
  call button broken"
- Patient names/IDs are never sent to Anthropic (parser), Sarvam (STT/TTS),
  or stored in `complaints.text` — eliminates a whole class of compliance
  surface
- Eliminates patient-churn modeling entirely (we don't seed admissions,
  discharges, or patient transfers — these are out of scope for a
  facilities-management platform)

This decision is restated in `sunrise_nursing_home.json` under
`_meta.design_notes`.

## Editing a config file

Each config is a single JSON document with these top-level sections:

```
_meta              { vertical, description, design_notes, is_demo, sid }
society            { name, address, timezone }
structure          { vertical-specific: towers/units, rooms/beds, events, suites }
categories         [ { name, priority_default, common, sla_override? } ]
staff_roles        [ { role_key, title, count, category_specialty?, in_chain? } ]
escalation_chain   [ { level, role_key } ]
sla_config         { default, overrides }
contractor_specialties [ { category, vendor_name, rating, count } ]
```

Hand-edit freely. The seeder (Part 6, not yet built) will read these and
produce DB inserts. No code changes needed when you tweak counts,
categories, vendor names, or SLA values.

## What this directory does NOT contain

- **Synthetic people records** — those are Part 2 (`synthetic_people.py`
  or similar, generated deterministically from these configs)
- **Historical complaints** — those are Part 3
- **The seeder itself** — Part 6 (`runner.py`)
- **The wipe utility** — Part 6 (`wipe_society.py`)
- **Diagnostics / health-monitoring code** — Part 4 (separate location)
- **Tester support** — Part 5 (separate location)
