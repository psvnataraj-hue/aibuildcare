# E1 — Enterprise core: staff / escalation / SLA / routing

_2026-05-20. Built on the Foundation (tenancy + RBAC). Synchronous
parts only — the cron/auto-escalation/reminder jobs are E2._

## Phased delivery
| Sub-phase | Scope | Risk |
|---|---|---|
| **E1a** | Additive schema only (5 new tables + complaint escalation columns). Behaviour-neutral. | Very low |
| **E1b** | `routing_service` (category → staff_categories → contractor fallback, workload-aware) + tests. Replaces the current "contractor only" auto-router. | Medium (touches assignment) |
| **E1c** | Escalation: sync `POST /escalate` endpoint, escalation timestamp tracking, `respond` & extended `resolve`, notifications via the existing engine + tests. | Medium |

E1a is independent and shippable on its own — it's just data plumbing.

## Schema (additive — `CREATE TABLE IF NOT EXISTS` + `ADD COLUMN IF NOT EXISTS`)

1. `staff_members` (society-scoped) — name, primary/secondary phone,
   whatsapp/sms toggles, email, shift_pattern, active, hire_date,
   emergency_contact, notes.
2. `staff_categories` (M:N) — `(staff_id, category)` with
   `primary_category` + `skill_level (junior/senior/expert)`.
3. `contractor_categories` (M:N for the existing `contractors`) —
   `(contractor_id, category)` with `primary_category`,
   `average_rating`, `completed_jobs`.
4. `escalation_hierarchy` (per society) — `role_name` (manager /
   sr_manager / secretary / chairman / committee_member), person_name,
   phone, whatsapp_enabled, email, `escalation_level` (1..N),
   `response_time_target_minutes`, active.
5. `category_sla_config` (per society + category) —
   `target_response_time_minutes`, `target_resolution_time_hours`,
   `priority_high_multiplier`, `escalation_levels` (JSON, per the
   spec).
6. `complaints` additive columns —
   `escalated_to_{manager,sr_manager,secretary,chairman}_at`,
   `last_complainant_update_at`, `last_assigned_staff_update_at`,
   `assigned_staff_id` (FK staff_members), `reminder_sent_count`.

## Design decisions — RECOMMENDED defaults (flag if you want different)

| # | Decision | Recommendation | Reason |
|---|---|---|---|
| **1** | Are staff a separate table or just `users` with role='staff'? | **Separate `staff_members` table** (spec design). | Most staff (gardeners, guards) have **phone-only identities**, no login. A user account is optional via `staff_members.user_id` (added in E1c when staff dashboards arrive). |
| **2** | Are `categories` per-society or globally shared? | **Keep `categories` global for E1** — 7 well-known names everywhere. Per-society customization lives in `category_sla_config` (SLA + escalation rules vary per society). Reshape categories table to be per-society **only when a society needs a different category set** (defer). | Additive-only on prod; avoids changing the existing `UNIQUE(name)` constraint; matches "no breaking changes" rule. |
| 3 | Routing order | staff (primary cat first) → contractor (primary cat first) → unassigned ("needs_assignment" flag) | Spec Part 3.1. |
| 4 | SLA escalation_levels storage | JSON column on `category_sla_config` | Spec Part 3.2. Avoids an extra normalized table; mutations rare. |
| 5 | Escalation triggering | E1 = manual endpoint only; E2 = the 30-min auto-cron evaluator | Keeps deploy/test surfaces separate. |

Decisions 3–5 are well-specified in the spec and not really forks. **Decisions 1 and 2 are the ones worth your glance** — both have my recommendation.

## What E1a ships today
- 5 new tables + complaint escalation columns (additive, idempotent, both sqlite and pg).
- Seed backfill: a sensible `category_sla_config` row per (default society, category) using sane SLAs (Plumbing 60min/4h, Electrical 30min/2h, Elevator 15min/30m, etc.).
- A few unit tests proving tables/columns exist and the seed populated.

No service code, no endpoint, no behaviour change. Safe to deploy whenever.
