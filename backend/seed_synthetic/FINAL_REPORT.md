# Final report — synthetic-data + diagnostics build

**Branch**: `claude/synthetic-data-and-diagnostics-2026-05-22`
**Commits**: 7 on top of `36cfc66` (the pre-build main HEAD)
**Tests**: 413 passing, before and after every commit
**Deployed**: NO — branch not pushed, no Render Manual Deploy. Review
required before any production-deploy click.

---

## 1. What was created

### Schema additions (idempotent, additive)

| Migration | What |
|---|---|
| `migrations/001_init.sql` (modified) | Added `societies.is_demo` column inline; added `operator_events` table for fresh DBs; added `cron_last_tick_at` system_config seed |
| `migrations/001_init_pg.sql` (modified) | Same as 001_init for Postgres canonical schema |
| `migrations/004_is_demo_flag.sql` (new) | Standalone ALTER for existing Supabase prod DB (idempotent) |
| `migrations/005_operator_events.sql` (new) | Standalone CREATE TABLE + INSERT for existing Supabase prod DB (idempotent) |

### Demo tenants (in production DB, structurally isolated from Palms)

| sid | name | vertical | residents/users | staff | contractors | vehicles | complaints |
|---|---|---|---|---|---|---|---|
| 1 | Palms Residency | real pilot — **never touched** | (unchanged) | (unchanged) | (unchanged) | (unchanged) | (unchanged) |
| 100 | Greenwood Residency | residential society | 50 | 22 (incl 3 deactivated) | 11 (incl 1 retired) | 53 | 120 |
| 101 | Sunrise Nursing Home | hospital (rooms/beds, NO patients) | 30 | 19 (incl 3 deactivated) | 10 (incl 1 retired) | 0 | 80 |
| 102 | Stellar Events | event company | 15 | 17 (incl 3 deactivated) | 9 (incl 1 retired) | 0 | 40 |
| 103 | Meridian Estate Office | commercial office | 50 | 22 (incl 3 deactivated) | 9 (incl 1 retired) | 84 | 50 |
| **Demo total** | — | — | **145** | **80** (incl 12 deactivated) | **39** (incl 4 retired) | **137** | **290** (+ 150 ratings) |

### Tester accounts (12 in total, on demo tenants only — NO admin role)

| Email format | Role | Society | Purpose |
|---|---|---|---|
| `sravya.resident+sid100..103@aibuildcare.app` | resident | each demo | End-user filer perspective |
| `sravya.ops+sid100..103@aibuildcare.app` | secretary | each demo | Operator perspective with full _LEADER permissions |
| `nataraj.ops+sid100..103@aibuildcare.app` | secretary | each demo | Per-demo operator login, separate from Palms admin |

Plus 2 RESERVED slots (`sravya-primary-live`, `sravya-secondary-live`) on
Greenwood, awaiting Sravya's real phones — seeder skips them until
`phone_to_add` is populated.

All tester passwords come from `AIBUILDCARE_TESTER_PASSWORD` env var at
seed time; bcrypted in `users.password_hash`. The plaintext password is
never stored.

### Code added

| File | Purpose | Lines |
|---|---|---|
| `backend/seed_synthetic/` | Whole directory — see below | — |
| `backend/seed_synthetic/README.md` | Architecture overview, isolation guarantees, cron safety, DPDP boundary | ~180 |
| `backend/seed_synthetic/greenwood_residency.json` etc. (4 + 2) | Tenant configs + parking overlays | ~1500 |
| `backend/seed_synthetic/name_pools.py` | Hand-curated regional Indian names (5 regions, 200 firsts + 125 surnames) + screening lists | ~280 |
| `backend/seed_synthetic/generate_people.py` | Deterministic people generator | ~700 |
| `backend/seed_synthetic/complaint_text_bank.py` | 89 common + 148 vertical-specific complaint templates; multilingual | ~600 |
| `backend/seed_synthetic/generate_complaints.py` | Historical complaint generator | ~700 |
| `backend/seed_synthetic/people/*.json` | Generated people + complaint records (5 + 4 files) | ~14000 lines |
| `backend/seed_synthetic/runner.py` | Seeder + per-tenant wipe utility | ~550 |
| `backend/seed_synthetic/WALKTHROUGH.md` | Click-by-click guide for non-technical evaluators | ~200 |
| `backend/seed_synthetic/FINAL_REPORT.md` | This document | — |
| `backend/app/services/operator_events.py` | Operator log + self-alert dispatch | ~190 |
| `backend/app/services/quota_monitor.py` | Programmatic + estimated quota checks | ~310 |
| `backend/app/services/diagnostics.py` | Health-check composer with cron dead-man's switch | ~210 |
| `backend/app/services/self_alert.py` | Throttled WhatsApp self-alert | ~130 |
| `backend/app/routers/diagnostics.py` | `/api/v1/diagnostics/{health,events,quotas,trigger-tick}` | ~140 |
| `backend/app/services/notify.py` (rewritten) | TEST_PHONE_SKIP + SEEDING_LOCK + operator_events wraps | ~210 |
| `backend/app/services/jobs_service.py` (modified) | Cron heartbeat writes | +30 |
| `backend/app/integrations/r2_client.py` (modified) | Operator-event logging on graceful R2 fallback | +15 |
| `backend/app/services/haiku_parser.py` (modified) | Operator-event logging on graceful parser fallback | +15 |
| `backend/app/routers/internal_jobs.py` (modified) | Seeding-lock check | +20 |
| `backend/app/main.py` (modified) | Wire diagnostics router | +1 |
| `backend/seed_synthetic/findings/` | 5 design-decision documents | ~900 |
| `backend/seed_synthetic/walkthrough_notes/` | Stellar 22% orphan framing note | ~70 |

---

## 2. Part 0-B cron-safety mechanism as implemented

Three independent layers — any one alone is sufficient; together they're
belt + suspenders + rope.

### Layer 1 — Status-based skip (pre-existing, leveraged)

`backend/app/services/jobs_service.py:24` — `_OPEN_STATES = ("received",
"acknowledged", "assigned", "in_progress")`. The escalation cron only
operates on complaints in those four states.

**Every one of the 290 seeded historical complaints is in
`status='resolved'`, `status='closed'`, or `status='rejected'` EXCEPT
the 28 deliberate orphan zombies.** The cron sees the historicals,
sees they're closed, skips them — no escalation fires, no WhatsApp
sent. The 28 zombies have `status='in_progress'` deliberately so they
surface as orphans in the dashboard (Finding 002 made visible by
design).

### Layer 2 — Reserved test-phone range

`backend/app/services/notify.py:_is_test_phone()` short-circuits every
outbound WhatsApp / SMS / email send when the recipient phone matches
the env-configurable prefix list (default `+919900`). The match writes
an `operator_events` row tagged `test_phone_skipped`.

**Every one of the 137 vehicle owners, 145 users, 80 staff, 39
contractors, 12 tester accounts uses a phone in this range** —
generator-allocated via the `+91 99000 XXXXX` banding scheme. If
something inside the cron tried to message any of them, the chokepoint
logs a skip event and returns success-shaped.

### Layer 3 — Seeding-lock env

`AIBUILDCARE_SEEDING_LOCK=1` — when set, `/internal/jobs/tick` returns
202 immediately without running any job. The cron heartbeat is
deliberately NOT written under the lock, so the dead-man's switch
stays armed. If the operator forgets to unset the lock, they get
warned via the silent-cron alert at minute 46.

Set BEFORE running the seeder, unset AFTER verifying the seed.

### Combined cron-safety summary

A single send attempt would need ALL THREE LAYERS to fail
simultaneously: a historical complaint accidentally in an open state
(Layer 1 fails) being assigned to a non-test-range phone (Layer 2
fails) while the seeding lock is unset (Layer 3 not in effect). That
should not happen in practice; defense in depth is intentional.

---

## 3. Quota monitorability — programmatic vs estimated (Part 4-2 honesty)

The dashboard quota tile distinguishes programmatic from estimated:

### Programmatic (real API queries — current numbers)

| Service | What's queried | API |
|---|---|---|
| Twilio | Account balance + today's WhatsApp+SMS count | Twilio REST `client.balance.fetch()` + `client.messages.list(date_sent_after=…)` |
| SendGrid | Today's send count vs free-tier 100/day | SendGrid Stats v3 `/v3/stats?start_date=…` |
| R2 | Bucket size (MB) vs free-tier 10 GB | S3 ListObjects (`boto3` client to `r2_endpoint_url`) |
| Cron | Tick count in last 24h vs free-tier 100/day | Self-monitored — counts `cron_tick_complete` operator_events |

### Estimated (no public API on the free tier)

| Service | What we do | What customer should check directly |
|---|---|---|
| Anthropic | Tracked from response usage headers (roadmap — not yet accumulated locally) | console.anthropic.com |
| Supabase | Derived from our own row counts | Supabase dashboard |
| Render bandwidth | Best-effort from request logs | Render dashboard |

`backend/app/services/quota_monitor.py:monitorability_summary()` returns
this split as a JSON dict so the report or dashboard can render it.
Threshold crossings (80% warn, 90% error) are logged to operator_events
+ trigger throttled self-alert.

---

## 4. Findings (separate change set — DO NOT FIX on this branch)

5 architectural findings surfaced during the build. None are blocking
the demo work; all need separate design conversations.

### Finding 001 — Admin role has cross-tenant data reach (HIGH, dormant)
- `/api/v1/analytics` and `/api/v1/contractors` query globally with no
  society_id filter
- `/api/v1/admin/permissions*` accepts `?society_id=` from admin and
  serves any tenant's RBAC
- Admin role short-circuits to `ALL_PERMISSIONS` ignoring overrides
- Admin user has NULL society_id by default
- **Activation**: the moment a second admin exists on a different
  society. Today only Palms admin exists → dormant.
- **Recommendation in finding doc**: Option A (introduce
  `platform_super_admin` role, scope `admin` to its own society).
  ON THE CRITICAL PATH BEFORE CUSTOMER #2.

### Finding 002 — No orphaned-work handling (MEDIUM, active)
- `deactivate_staff()` only sets `active=0`; complaints with
  `assigned_staff_id` pointing to that staff are not reassigned, not
  surfaced
- Cron reminders stop (joins filter active=1) but cron escalation
  continues (status-based)
- 28 deliberately-seeded zombies make this visible in the dashboard
- **Recommendation**: Option A — daily "surface orphaned complaints"
  cron sub-job + admin tile. Half a day's work.

### Finding 003 — User-facing "complaint/complainant" labels (LOW cosmetic, HIGH at demo time)
- Schema vocabulary is fine; only user-facing labels are wrong outside
  housing
- Hospital especially: "complainant" has an adversarial connotation
  inappropriate for "ward staff reporting that the bedpan needs
  replacing"
- **Recommendation**: Option B — global rename to "request" /
  "requester". One day's frontend + WhatsApp template work.
  Critical-path BEFORE first non-housing prospect demo.

### Finding 004 — No delivery or read-receipt proof (HIGH accountability)
- `notify.py` calls `client.messages.create()` with no
  `status_callback=` param
- No `outbound_messages` table — `MessageSid` returned by Twilio is
  discarded on send
- No webhook endpoint accepts Twilio status callbacks
- Sandbox blocks read receipts entirely; production WhatsApp Business
  API is a separate procurement track (2-6 week approval)
- **Recommendation**: Option A (delivery proof only, 2 days,
  sandbox-compatible) on the critical path before non-Palms customer.
  Option B (+ read receipts) in parallel as a procurement track.

### Finding 005 — Two pitch claims are PARTIAL (MEDIUM accountability)
- Photo-elevates-priority works on WhatsApp/SMS intake but NOT on
  dashboard (no image field on `ComplaintCreate`)
- Voice reply works on WhatsApp only (SMS protocol-incapable); TTS
  silently falls back to text if Sarvam fails
- **Recommendation**: brochure wording tweaks (1-2 hours) +
  half-day dashboard image-upload feature

---

## 5. Other artifacts produced

| File | Purpose |
|---|---|
| `backend/seed_synthetic/walkthrough_notes/stellar_orphan_ratio_framing.md` | Lock the demo narrative for Stellar's 22.5% orphan ratio — frame as feature, not defect. Includes verbatim "say-this / don't-say-this" lines. |
| `backend/seed_synthetic/findings/README.md` | Index of all 5 findings + the discipline rationale (why we report-not-fix) |
| `backend/seed_synthetic/WALKTHROUGH.md` | Per-tenant click-by-click guide |
| `backend/seed_synthetic/FINAL_REPORT.md` | This document |

---

## 6. Test & verification status

- **413 tests passing** (the existing hermetic-SQLite test suite). Run
  after every commit on the branch; no regressions.
- **Seeder dry-run on fresh local SQLite**: clean. All 290 complaints
  + 145 users + 80 staff + 39 contractors + 137 vehicles + 12 tester
  accounts inserted. Idempotent re-seed: 0 new rows.
- **Wipe dual-guard verified**:
  - `wipe --sid 1` → REFUSED on hardcoded guard ✓
  - `wipe --sid 102 --dry-run` → shows counts, no deletion ✓
  - `wipe --sid 102` → 40 complaints + 17 staff + 9 contractors + 5
    units + ... cleared cleanly ✓
- **Reseed-after-wipe**: clean ✓

---

## 7. Commits on this branch

```
e172d7b → 91c1c6f → (Part 6 commit) — Findings 004 / 005 + Part 6
bc525a3   Part 4: diagnostics + health-monitoring (6 essentials)
33f54c3   Part 3: 290 historical complaints + finding 003 + reserved live slots
5b531af   Part 2: synthetic-people generator + findings (admin leak, orphan gap)
2ca1916   Part 1 redlines: DPDP affirmative boundary, Meridian parking, 3x churn
6e43ba1   Part 1: synthetic-data tenant configs (4 verticals) + is_demo flag
```

---

## 8. Next-action checklist (your review)

Before this lands on production:

  - [ ] Read this report end-to-end.
  - [ ] Skim `WALKTHROUGH.md` — does the per-tenant flow match your
        mental model?
  - [ ] Read at least one finding doc end-to-end
        (recommend 001 — admin leak — since it's on the customer-#2
        critical path).
  - [ ] Open a PR against `main` for review (do NOT use `--no-verify`
        or skip CI).
  - [ ] On Render: after merge to main, click Manual Deploy on api
        AND web services. Set `AIBUILDCARE_SEEDING_LOCK=1` in api env
        BEFORE running the seed; unset AFTER `verify_deploy.py` passes
        plus a manual spot-check that all 290 historical complaints
        are in non-open status.
  - [ ] Run the seeder once against prod with
        `AIBUILDCARE_TESTER_PASSWORD=<set>` and verify Sravya can log
        in to `sravya.resident+sid100@aibuildcare.app`.
  - [ ] Send Sravya the WALKTHROUGH document; she begins testing.

Before customer #2:

  - [ ] Resolve finding 001 (admin cross-tenant leak). Option A
        recommended.
  - [ ] Resolve finding 003 (terminology rename) before any non-housing
        prospect demo.
  - [ ] Ship finding 004 Option A (delivery proof) — start the
        WhatsApp Business API approval clock now if read receipts
        are needed in the pitch.
  - [ ] Edit pitch copy per finding 005 (or ship the dashboard
        image-upload).

That's the build.
