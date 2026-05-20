# E3 — Role-aware frontend + backend prerequisites

_2026-05-20. Built on Foundation + E1 + E2 (all backend complete).
Surfaces the new capabilities (staff routing, escalation, vendor
directory, major incidents, RBAC overrides) in the dashboard, and
adds the backend pieces still missing for full self-service._

## Honest inventory — what exists vs what's missing

| Capability | Backend | Frontend |
|---|---|---|
| Society scoping (complaints + queries) | ✅ E1b | ✅ via `current_society` token |
| Staff routing (find_assignee) | ✅ E1b | ❌ **no staff CRUD endpoints**, no staff display |
| Complaint shows assigned **contractor** | ✅ | ✅ |
| Complaint shows assigned **staff** | ✅ column exists | ❌ ComplaintDetail still only shows contractor |
| Escalation timestamps + manual escalate | ✅ E1c | ❌ no UI for escalate / hierarchy / level |
| Vendor directory (`/vendors/by-category`) | ✅ E1b' | ❌ no UI page |
| Major-incident flag + reason | ✅ E2d | ❌ no banner / filter / list section |
| RBAC overrides per society | ✅ F3 + admin router | ❌ no UI |
| Per-role dashboards | n/a | ❌ single shared dashboard for everyone |
| Staff mobile-first view | n/a | ❌ |
| Resident portal | n/a (deferred) | n/a (deferred) |

E3 closes the items marked ❌ in **bounded sub-phases**:

| Sub | Scope | Surface |
|---|---|---|
| **E3a** | Staff CRUD endpoints + tests | Backend |
| **E3b** | Manual `/assign` accepts `staff_id` OR `contractor_id` | Backend |
| **E3c** | Show `assigned_staff` + escalation level + major-incident banner on ComplaintDetail & cards | Frontend |
| **E3d** | New page: vendor directory (`/vendors`) | Frontend |
| **E3e** | New page: escalation hierarchy editor | Frontend |
| **E3f** | New page: staff management | Frontend |
| **E3g** | New page: RBAC override editor (OEM) | Frontend |
| **E3h** | Role-flavoured top-nav: hide things a role can't act on | Frontend |
| **E3i** *(optional)* | Staff mobile shortcut view | Frontend |

E3a + E3b are pure backend; the rest are Vue work. **Sub-phases ship independently and are independently testable.**

## Decisions baked in (no fork)
- Resident portal stays deferred (Foundation decision C).
- Reuse existing WebSocket hub for realtime; no Supabase Realtime.
- One Vue app with **role-aware visibility** (hide buttons/pages a role lacks permission for); not separate Vue apps per role.
- Staff mobile view = a responsive variant of the main dashboard, not a separate codebase.

## What ships in this turn
**E3a only** (the smallest valuable, behaviour-neutral backend
prerequisite). Without staff CRUD endpoints, no frontend can list or
add staff. E3b–E3i follow in subsequent turns/sessions.
