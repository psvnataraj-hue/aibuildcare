# Walkthrough — synthetic demo tenants

Audience: an evaluator (Nataraj for QA, Sravya for usability testing, or
a prospect during a demo). The reader does NOT need to read code or run
the repo — they log in with a tester credential and click around.

## Before you start

1. The branch `claude/synthetic-data-and-diagnostics-2026-05-22` must
   be seeded into the target environment. See "Seeding" below.
2. You'll need the tester password (whatever was passed via
   `AIBUILDCARE_TESTER_PASSWORD` at seed time).

## Seeding

```bash
# From the repo root (the venv is in backend/.venv).
AIBUILDCARE_TESTER_PASSWORD=<password> \
  ./backend/.venv/Scripts/python -m backend.seed_synthetic.runner seed
```

This inserts (or upserts, on re-runs) ~290 historical complaints + 145
users + 80 staff + 39 contractors + 137 vehicles + 12 tester accounts
across the 4 demo societies. Idempotent: re-running is safe and
produces 0 new inserts.

To wipe and reseed a single demo tenant:

```bash
python -m backend.seed_synthetic.runner wipe --sid 100      # full wipe
python -m backend.seed_synthetic.runner wipe --sid 100 --dry-run   # preview
python -m backend.seed_synthetic.runner seed --sid 100      # re-fill
```

`wipe` refuses sid=1 unconditionally (hardcoded guard) AND refuses any
society with `is_demo=0` (data guard). Real Palms data is structurally
unreachable.

## Login URLs and credentials

Production (the live deployed app, after Manual Deploy of this branch):
`https://aibuildcare-web.onrender.com/login`

Local development:
`http://localhost:5173/login`

**Tester credentials** (after seeding with `AIBUILDCARE_TESTER_PASSWORD`
set; the bcrypted env-var value is the password for all 12 accounts):

Users table stores each tester as `email+sid<sid>@…` to keep
society-scoped sessions distinct. Log in with the encoded email format:

| Email at login | Role | Society | What this account is for |
|---|---|---|---|
| `sravya.resident+sid100@aibuildcare.app` | resident | Greenwood (100) | File complaints as a Greenwood resident |
| `sravya.resident+sid101@aibuildcare.app` | resident | Sunrise (101) | File as a Sunrise ward staffer |
| `sravya.resident+sid102@aibuildcare.app` | resident | Stellar (102) | File as a Stellar event-client contact |
| `sravya.resident+sid103@aibuildcare.app` | resident | Meridian (103) | File as a Meridian tenant employee |
| `sravya.ops+sid100@aibuildcare.app` | secretary | Greenwood | Operate Greenwood — assign, resolve, escalate, clamp |
| `sravya.ops+sid101@aibuildcare.app` | secretary | Sunrise | Operate Sunrise |
| `sravya.ops+sid102@aibuildcare.app` | secretary | Stellar | Operate Stellar |
| `sravya.ops+sid103@aibuildcare.app` | secretary | Meridian | Operate Meridian |
| `nataraj.ops+sid100..103@aibuildcare.app` | secretary | each demo | Nataraj's per-demo operator login, separate from the Palms admin |

★ The Palms admin (`admin@aibuildcare.app`) is unchanged; do not log in
as Palms admin for demo walkthroughs — its cross-tenant reach
(finding 001) would surface mixed data on the analytics tile.

## Walkthrough — Greenwood Residency (sid=100, housing society)

Use this first; it's the most-developed vertical and the best baseline.

1. **Log in** as `sravya.resident+sid100@aibuildcare.app`.
2. **Dashboard** — should show: an "AC not cooling" -style ticket
   landed at unit D-1B with status "resolved" and a 4-star rating.
   This is one of the 120 historical Greenwood complaints.
3. Click **/complaints/mine** in nav — confirm the list shows the
   resident's own complaints. Tenant-scoped: Sravya as Greenwood
   resident never sees Sunrise / Stellar / Meridian / Palms data.
4. **Log out, log in** as `sravya.ops+sid100@aibuildcare.app` (the
   operator persona).
5. **Dashboard analytics tile** — should show a breakdown of complaint
   status with a meaningful spread (~65% resolved, ~20% closed, ~15%
   open including the 8 deliberately-seeded zombie complaints + a
   handful of in-progress).
6. **Complaints list** — sort by priority. Notice high-priority
   complaints assigned to the deactivated plumber, in-house
   electrician, and retired AC contractor. These are the **expected
   orphan/zombie cases** (Finding 002 surfaces here, deliberately).
7. **Vehicles page** (`/vehicles`) — 53 registered vehicles. Search
   for plate `MH-12-ZZ-0001`, `MH-12-XX-0007`, `MH-12-ZX-0013` — the
   three deterministic repeat-offender plates. Each should show
   3 violations in the past 30 days.
8. **Complaint detail** — open one of the repeat-offender parking
   complaints. Verify the `major_incident` badge is set on the 3rd
   violation; clamping audit trail visible for the MH-12-XX-0007
   plate's fire-lane violation.
9. **Diagnostics health tile** (`/api/v1/diagnostics/health`
   accessible via secretary role) — should show:
   - `db: ok`
   - `cron: ok` (or `warn` if no cron has run in this dev instance yet)
   - `twilio: informational` (no real Twilio configured in dev)
   - `quota_warnings: []`
10. **Trigger escalation manually** (`POST /api/v1/diagnostics/trigger-tick`)
    — secretary role can hit this endpoint on demo tenants only.
    Refuses on Palms. Combined with Greenwood's demo SLA (L1=2min,
    L2=4min, L3=6min) this is the fastest possible escalation-loop
    test: file a fresh complaint, wait 2 minutes, trigger tick,
    verify L1 fires.

## Walkthrough — Sunrise Nursing Home (sid=101, hospital)

Hospital vertical demonstrates the **DPDP-safe data boundary**.

1. Log in as `sravya.ops+sid101@aibuildcare.app`.
2. **Complaints list** — open any complaint. Verify the complaint is
   keyed to a room/bed (e.g. `B-ICU-101-B1`, `A-GW-204-B2`,
   `C-PHARM`), never to a patient name. The `raw_text` describes
   infrastructure ("nurse-call button broken", "AC dripping on bed",
   "BP monitor reading high"). No patient identity appears in any
   complaint.
3. **Show prospect the message thread on a complaint** — confirm the
   thread shows the ward-staff reporter + system messages, no
   clinical content of any kind.
4. **Escalation chain** — view hierarchy: ward_admin → nursing_supervisor
   → medical_superintendent → hospital_director. Confirm the
   complaint that was escalated to L2 stops at the nursing supervisor,
   not the patient's doctor.
5. **The orphan story** — surface the deactivated biomedical engineer
   who left holding a high-priority Equipment Calibration ticket
   already at L2. This is the worst-case scenario the system makes
   visible.
6. **Demo line to use**: "The platform's role is to make the DPDP
   boundary easy to honor — by routing on rooms and equipment alone,
   we don't need to engineer redaction layers around clinical content
   because clinical content never enters the system."

## Walkthrough — Stellar Events (sid=102, event company)

This is the **22% orphan ratio** demo. **Frame it as the product
working, not a defect.** See
`walkthrough_notes/stellar_orphan_ratio_framing.md` for full coaching;
key lines:

1. Log in as `sravya.ops+sid102@aibuildcare.app`.
2. **Dashboard tile** — shows 9 of 40 complaints flagged as orphan-
   assigned (departed runner with 4 backstage tickets; departed AV
   lead with 2 AV tickets including one at L1; departed catering lead
   with 2 catering complaints, one at L2 already; retired pyro
   contractor with 1 urgent).
3. **The pitch line** (verbatim): *"22% of Stellar's complaints are
   flagged as orphaned — meaning the original assignee left while
   the work was still open. In most event companies these just
   disappear. AIBuildCare surfaces them so the operations head sees
   exactly what was left undone, by whom, and at what escalation
   level. The system makes the chaos visible. That's the product."*
4. **Anchor by comparison**: switch to Greenwood (low-churn housing
   society) — orphan rate under 7%. *"The ratio itself tells you
   something about the vertical — high-churn industries get high
   orphan rates and need to see them."*
5. **Active events** — the 5 ongoing/recent events from the config:
   Worli wedding 2026-05-25, BKC AGM 2026-05-22, Symbiosis college
   fest, NCPA launch, Goa sangeet. Each event maps to a unit_number
   so per-event complaint flow is visible.

## Walkthrough — Meridian Estate Office (sid=103, office estate)

Office vertical demonstrates **per-tenant-suite parking** (different
from residential) + **tenant-company scoping**.

1. Log in as `sravya.ops+sid103@aibuildcare.app`.
2. **Suites list** — 50 occupied suites across B1 (North Tower) +
   B2 (South Tower), holding 15 fictitious tenant companies
   (Stratus Analytics, Northwind Logistics, ByteStream Software, etc.).
3. **Vehicles page** — 84 vehicles. Search `WB-02-ZZ-0101` — repeat
   offender from Stratus Analytics with 3 wrong_tenant_slot
   violations. `WB-02-ZX-0313` — cab driver with 4 violations
   including cab_zone_loiter (a violation type that doesn't exist on
   residential parking).
4. **Major-incident badge** — Meridian has 5 major-incident-flagged
   complaints (from repeat-offender threshold breaches). Higher than
   Greenwood (3) because one of the deterministic plates is the cab
   driver with 4 violations not 3.

## Operator-only diagnostics (Nataraj's view)

Use `nataraj.ops+sid100@aibuildcare.app` (secretary on each demo).
This is *separate from the Palms admin* — purpose-built so you can
demo a tenant without showing Palms data.

- `GET /api/v1/diagnostics/health` — full at-a-glance health.
- `GET /api/v1/diagnostics/events?severity=warn` — operator log,
  scrollable. Filter by `service=twilio` to see `TEST_PHONE_SKIPPED`
  events that fired during seeding (none, since seeding lock skipped
  them).
- `GET /api/v1/diagnostics/quotas` — full quota report with the
  programmatic-vs-estimated breakdown.

## Reseed / wipe during testing

If Sravya's test session corrupts the data (a real possibility — that
IS what testing is for), the operator can wipe and re-seed one tenant
in seconds:

```bash
python -m backend.seed_synthetic.runner wipe --sid <100|101|102|103>
AIBUILDCARE_TESTER_PASSWORD=<...> python -m backend.seed_synthetic.runner seed --sid <100|101|102|103>
```

Each tenant resets independently. Real Palms data is structurally
unreachable from this script.

## Confusing-or-broken flags

Surface for QA review:

| Where | What might be confusing / broken |
|---|---|
| `/analytics` viewed by admin | Cross-tenant data mixed in (Finding 001). Avoid logging in as Palms admin during demos. |
| Stellar dashboard | 22% orphan ratio looks alarming without framing — see coaching note. |
| Dashboard complaint-create form | No image upload field (Finding 005). Demonstrate photo-elevates-priority via WhatsApp intake, not dashboard. |
| Voice-note reply on SMS channel | Doesn't work (protocol fact). Demonstrate voice replies via WhatsApp only. |
| Delivery / read receipts | Not wired (Finding 004). Don't make claims about delivery proof in pitch copy until Option A ships. |
| "Complaint / complainant" labels | Read wrong in non-housing demos (Finding 003). Hospital especially. Edit pitch copy to "request / requester" before non-Greenwood prospects. |

These five gaps are documented in `findings/` and listed in the final
report.
