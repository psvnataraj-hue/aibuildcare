# AIBuildCare — PROJECT PAUSED (Resume Notes)

> **Status:** Project paused. May not continue in the near future. These notes
> are the complete state-capture so future-you (or future-Claude) can resume
> cold months or years later.
>
> **First action on resume:** read this file end-to-end, then check the
> "WHAT MIGHT HAVE EXPIRED" section before assuming any external service
> still works.

---

## 1. What AIBuildCare is

AI-assisted community-management platform for Indian residential societies,
hospitals, event companies, and office estates. Complaints in
(WhatsApp / SMS / email / Google Form), tickets out, intelligent multilingual
parsing, society-scoped tenancy, RBAC, staff + contractor routing, automatic
SLA escalation, vendor self-service directory, major-incident auto-flagging,
weekly committee summaries, parking enforcement with clamping authorization,
mobile staff work-list.

**Tech**: FastAPI (Python 3.12) + Vue 3 + TypeScript + Vite + Tailwind +
Pinia + Chart.js. Supabase Postgres (session-pooler). Render free tier
(manual-sync deploys). Twilio (WhatsApp + SMS, sandbox), SendGrid (email),
Anthropic Haiku 4.5 (parsing + vision), Sarvam (STT + TTS for Indian
languages), Cloudflare R2 (media). cron-job.org pings `/internal/jobs/tick`
every 15 min.

**Pre-pilot customer**: Serenity (housing society). Hospital prospect met
with Dr. Patil 2026-05-23.

---

## 2. Where everything lives

### Code

| | Location |
|---|---|
| **GitHub** (canonical) | `psvnataraj-hue/aibuildcare` (private) |
| **Local clone** | `C:\Users\psvna\OneDrive\Documents\aibuildcare` |
| **Triple-backup** | `E:\CARIMO\aibuildcare_backup\repo\` (full `.git`, 211 files, 2.19 MB) |

OneDrive cloud-syncs the local copy automatically. So the repo is on
**GitHub + OneDrive cloud + OneDrive local + E drive** — four locations,
three independent failure modes.

### Live deployment (may have expired — see §7)

| | URL |
|---|---|
| API | https://aibuildcare-api.onrender.com |
| Web dashboard | https://aibuildcare-web.onrender.com |
| Custom domain (configured) | https://aibuildcare.carimotech.in |
| Database | Supabase Postgres (account: psvnataraj-hue) |
| Cron pinger | cron-job.org "AIBuildCare tick" every 15 min |

### Secrets backup

| | Location |
|---|---|
| Render env vars template (blank, fill in by hand) | `E:\CARIMO\aibuildcare_backup\RENDER_ENV_VARS_TEMPLATE.md` |
| Filled-in secrets (if you completed the task) | should be at `E:\CARIMO\_SECRETS\aibuildcare_RENDER_env_<date>.md` |
| Local `.env` (dev defaults, includes some keys) | `E:\CARIMO\aibuildcare_backup\repo\.env` |

### Supabase data backup ✅ COMPLETE

| | Location |
|---|---|
| Tool (Python script) | `scripts/backup_supabase.py` in the repo |
| **Output** | **`E:\CARIMO\aibuildcare_backup\aibuildcare_supabase_<UTC-timestamp>.sql`** — confirmed run at pause-time: **14,613 rows / 20 tables / 6.49 MB**. Contains demo tenants (sid 100-103) AND Palms real pilot data (sid=1). |
| To restore | `psql <any_postgres_url> < aibuildcare_supabase_*.sql` — replays schema + data into any Postgres |

---

## 3. What was built

### Foundation (shipped, on `main`)

- 17+ live dashboard pages, full E1-E3 + Parking P1-P5 verticals
- 11-role RBAC matrix with per-society overrides (`backend/app/services/rbac.py`)
- Auto-routing (category + workload — `routing_service.py`)
- 4-level escalation chain with timestamps + WhatsApp (`escalation_service.py`)
- Major-incident auto-flagging (5 heuristics)
- Weekly Sunday email summary
- Multilingual acknowledgements (Haiku writes in resident's detected language)
- Parking vertical with vehicle registry + clamping + 5th-major-incident heuristic
- 413 tests passing on main

### Synthetic-data + diagnostics build (shipped, PR #17 + #18)

`backend/seed_synthetic/` — comprehensive demo-data + diagnostics layer:

- 4 demo tenant configs (Greenwood housing, Sunrise hospital, Stellar events,
  Meridian office)
- Deterministic generator producing 145 users + 80 staff + 39 contractors +
  137 vehicles + 290 historical complaints
- Idempotent seeder with dual-guard wipe utility
- Operator-events log + cron heartbeat + dead-man's-switch alerting
- `/api/v1/diagnostics/{health,events,quotas,trigger-tick}` endpoints
- TEST_PHONE_SKIPPED + SEEDING_LOCK chokepoints in `notify.py`
- Quota monitor with honest programmatic-vs-estimated split
- Walkthrough + final report docs

### Demo tenants seeded LIVE in prod (Supabase)

| sid | Tenant | Vertical |
|---|---|---|
| 1 | Palms Residency | Real pilot (housing) |
| 100 | Greenwood Residency | Demo housing |
| 101 | Sunrise Nursing Home | Demo hospital (rooms/beds, no patients) |
| 102 | Stellar Events | Demo event company |
| 103 | Meridian Estate Office | Demo office estate |

12 tester accounts (`sravya.resident+sid{100..103}@aibuildcare.app`,
`sravya.ops+sid{100..103}@...`, `nataraj.ops+sid{100..103}@...`), all
secretary role, password = the value set in `AIBUILDCARE_TESTER_PASSWORD`
when the seeder ran.

---

## 4. What's in flight — PR 1 of 6

Branch: `claude/fix-finding-001-tenant-scoping` (pushed to GitHub).
**9 commits** (8 fix increments + 1 WIP marker for a partial test file).
This was the start of a 6-PR remediation sequence (see §5).

| Done (committed on the branch) | Not done |
|---|---|
| Cycle 1: `platform_operator` role in rbac | **Leak #9: WebSocket per-society broadcast rooms** (hardest one — agent died here) |
| `seed.py`: operator seeded as platform_operator | **Migration 007** (`UPDATE users SET role='platform_operator' WHERE email='admin@aibuildcare.app'`) |
| `deps.py`: `target_society` cross-tenant dependency | The uncommitted test file (saved as a WIP commit) needs review/rewrite |
| Leak #1: `/analytics` society-scoped | **Full pytest suite never verified green** — the 8 committed fixes may have collateral test breakage |
| Leaks #2-7: 6 contractor endpoints scoped | (PR was never opened — the branch is just sitting on GitHub) |
| Leak #8: `/admin/config` → platform_operator | |
| Leak #10: `/admin/permissions` → platform_operator | |
| Leak #11: diagnostics events scoped + `mark_seen` accepts `society_id` | |

To finish PR 1 (~45 min):
1. Run `pytest --no-cov` — see if the 8 fixes broke other tests
2. Review/rewrite the WIP test file (`backend/tests/test_finding_001_tenant_scoping.py`)
3. Implement leak #9 (WebSocket rooms) TDD-style
4. Create `migrations/007_platform_operator.sql`
5. Suite green, push, open PR, merge

---

## 5. The 6-PR remediation plan (approved 2026-05-22)

Full plan at `docs/plans/2026-05-22-serenity-prepilot-remediation.md`.

| PR | Fixes | Status |
|----|---|---|
| **1** | Finding 001 — tenant-scoped admins + `platform_operator` role | Mid-flight (see §4) |
| 2 | Finding 006 — email-webhook security (shared-secret auth + `to:` allowlist + attachment capture) | Not started |
| 3 | Finding 002 — orphan-work surfacing (Option A: surface + notify, no auto-reassign) | Not started |
| 4 | Finding 004 — delivery proof (Option A: Twilio status_callback + outbound_messages table) — read receipts OUT of scope (needs WA Business API) | Not started |
| 5 | Finding 005 — dashboard photo-upload + voice-fallback signal | Not started |
| 6 | Finding 003 — rename "complaint/complainant" → "request/requester" (vertical-defaulted via `/auth/me`) + society-name on dashboard | Not started |

### Approved decisions (D1–D12, +D5 update)

- **D1**: `admin@aibuildcare.app` → role `platform_operator` (Nataraj's cross-tenant login) ✅
- **D2**: `platform_operator` tolerates NULL society_id; new `target_society` dep honors `?society_id=` only for that role ✅
- **D3**: Fix the WebSocket cross-tenant leak inside PR 1 ✅
- **D4**: Finding 002 = Option A (surface + notify), not auto-reassign ✅
- **D5**: Terminology = default-by-vertical, resolved server-side via `/auth/me` (residential → "complaint/shikayat"; non-housing → "request/anurodh") ✅
- **D6**: Rename covers all user-facing text incl. staff weekly-summary email ✅
- D7–D12: Implementation defaults (secret-as-inline-check, env-CSV domain allowlist, env-configurable staleness threshold default 4h, `X-Twilio-Signature` HMAC, `outbound_messages` insert in own try/except, voice-fallback as system thread message, image upload in create form) ✅

---

## 6. The 6 architectural findings

All filed at `backend/seed_synthetic/findings/00{1..6}*.md`. Each has
severity + critical-path-timing + remediation options.

| # | Title | Severity | Status |
|---|---|---|---|
| 001 | Admin role has cross-tenant data reach (11 leaks) | HIGH | Mid-fix in PR 1 |
| 002 | No orphaned-work handling (2 gaps: deactivated assignees + unrouted complaints) | MEDIUM | Documented, planned in PR 3 |
| 003 | "Complaint/complainant" labels read wrong outside housing | LOW cosmetic | Documented, planned in PR 6 |
| 004 | No delivery / read-receipt proof; outbound is fire-and-forget | HIGH | Documented, planned in PR 4 |
| 005 | Dashboard cannot attach photos; voice reply WhatsApp-only | MEDIUM | Documented, planned in PR 5 |
| 006 | Email-webhook security: no auth, no `to:` validation, attachments dropped | HIGH | Documented, planned in PR 2 |

### Companion artifacts in the repo

- `backend/seed_synthetic/FINAL_REPORT.md` — full Part 6 build report
- `backend/seed_synthetic/WALKTHROUGH.md` — click-by-click for evaluators
- `backend/seed_synthetic/findings/README.md` — findings index
- `backend/seed_synthetic/walkthrough_notes/stellar_orphan_ratio_framing.md` — demo coaching note

---

## 7. WHAT MIGHT HAVE EXPIRED

Read this carefully before assuming anything still works on resume.

### High-risk for expiry

| | What to check first |
|---|---|
| **Render free tier** (api + web services) | Log in to dashboard.render.com. If services are suspended for non-payment, the API + web are gone. Code is on GitHub — redeploy elsewhere or pay to restore. |
| **Supabase free tier** (Postgres DB) | Log in to supabase.com. If project is paused/suspended, the DB is read-only or inaccessible. Data is in the `.sql` dump on E drive **if you completed the dump** — otherwise lost (or recoverable via Supabase's data-export tools if account restored). |
| **cron-job.org** (the cron pinger) | Free; rarely expires. If suspended, just re-create the job. |

### Low-risk for expiry

| | |
|---|---|
| **GitHub repo** | Free, permanent. Safe. |
| **carimotech.in domain** | Separate concern — check Hostinger billing if uncertain. |
| **Twilio sandbox** | Free, doesn't expire. Join code may need re-joining. |
| **Anthropic / SendGrid / Sarvam / Cloudflare R2 accounts** | Account-specific; check each console. Keys may need rotating. |

### The data dump WAS completed at pause-time

`E:\CARIMO\aibuildcare_backup\aibuildcare_supabase_<UTC-timestamp>.sql`
— 14,613 rows / 20 tables / 6.49 MB, includes both demo tenants
(sid 100-103) AND Palms real pilot data (sid=1).

To restore: `psql <any_postgres_url> < aibuildcare_supabase_*.sql`
replays schema + data into any Postgres deployment.

If E drive itself is later lost (the dump's single point of failure
right now), see §8 Path C — demo data is regenerable from the
seeder, but Palms data CANNOT be regenerated.

---

## 8. How to resume — step by step

### Path A: Resume with everything intact

1. Read this file. Read `docs/plans/2026-05-22-serenity-prepilot-remediation.md`.
2. `cd C:\Users\psvna\OneDrive\Documents\aibuildcare && git pull && git status`
3. Check Render dashboard — services live? Check Supabase — DB accessible?
4. `git checkout claude/fix-finding-001-tenant-scoping` — the in-flight PR 1 branch
5. Drop the WIP commit if reviewing test file fresh: `git reset --soft HEAD~1` (this also pulls the partial test file back into the working tree as uncommitted)
6. Run `cd backend && .venv/Scripts/python -m pytest --no-cov -p no:cacheprovider` — see if the 8 fixes broke anything
7. Resume PR 1's tail: implement leak #9 (WebSocket per-society rooms), migration 007, finalize tests, verify green, push, open PR
8. After PR 1 merges → tackle PRs 2-6 from the plan, each its own PR

### Path B: Resume cold — Render/Supabase access lost

1. Read this file completely.
2. Restore the secrets you'll need (from `E:\CARIMO\aibuildcare_backup\RENDER_ENV_VARS_TEMPLATE.md` if you filled it in, or regenerate from Anthropic/Twilio/SendGrid/etc. consoles).
3. Spin up a new Supabase project (or any Postgres). Apply the `.sql` dump: `psql <new_db_url> < E:\CARIMO\aibuildcare_backup\aibuildcare_supabase_<timestamp>.sql`
4. Spin up new Render services (or use any FastAPI/Vue hosting). Point them at the new DB. Set the env vars.
5. Run `verify_deploy.py` against the new deployment.
6. Continue from Path A step 4.

### Path C: Resume cold — even the data dump is lost

1. Read this file.
2. Demo data is regenerable from `backend/seed_synthetic/runner.py seed` (deterministic — produces identical output).
3. Palms real pilot data (sid=1) is lost unless backed up elsewhere.
4. Otherwise as Path B from step 4.

---

## 9. Memory / context backup for future Claude sessions

If you resume by spawning a new Claude Code session, the relevant memory
files live at:

```
C:\Users\psvna\.claude\projects\<long-path>\memory\
  ├── project_aibuildcare_prepilot_remediation_resume.md  ← current state
  ├── project_aibuildcare_session_2026-05-22.md           ← synthetic-data build close
  ├── project_aibuildcare_session_2026-05-21.md           ← day-2 history
  ├── reference_aibuildcare_canonical.md                  ← stable architecture
  ├── feedback_aibuildcare_migration_lessons.md           ← Render + Supabase gotchas
  ├── feedback_aibuildcare_session_lessons.md             ← working-style preferences
  └── MEMORY.md                                           ← the index
```

If Claude Code is reinstalled or the memory directory is gone, the
project_aibuildcare_prepilot_remediation_resume.md was the most-current
single file. Its essential contents are duplicated in this file (§4, §5,
§7, §8).

---

## 10. Team + contact

- **Owner**: Dr. P. S. V. Nataraj, founder/director CARIMO Technologies
- **Tester** (would-have-been): Sravya (COO), remote from Toronto
- **Real pilot prospect**: Serenity (housing society) — pre-pilot was being prepared
- **Hospital prospect**: Dr. Patil — first visit 2026-05-23 (happened)
- **Other CARIMO team**: Karan (R&D firmware), Maryam (former intern), Ajit (hardware), Sravya (COO)

---

## 11. The build's most important single insight

> The synthetic-data build's **findings/** directory is the most durable
> artifact. The code in this repo gets rewritten over time. The 6 findings
> capture *architectural decisions that will shape any future version* of
> the multi-tenant pitch. Specifically Finding 001 (admin cross-tenant
> leak) MUST be resolved before any second paying tenant is onboarded —
> or the product's privacy claim breaks the first day customer #2 logs in.

End of resume notes. Good luck, future-self.
