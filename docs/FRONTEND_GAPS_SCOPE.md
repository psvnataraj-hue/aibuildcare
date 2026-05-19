# Frontend gaps #2 & #3 — scope before code

_2026-05-19. Decide pilot needs before implementation._

## Gap #2 — identity / users / RBAC / multi-society

Current reality: the UI hard-codes `Nataraj (Admin)` /
`admin@aibuildcare.app`; one shared login; no user management; no
per-society scoping (every query is global). Backend has `users`
(role column) and `societies`/`unit.society_id` tables, but auth
issues one admin token and nothing scopes by society.

Three honest scope levels:

| Level | What it adds | Effort | Pilot fit |
|---|---|---|---|
| **A. Single-admin (explicit)** | Stop hard-coding identity (read `/me`), add change-password. No new users, no RBAC. | ~0.5 day | OK only if exactly one operator |
| **B. Multi-user, single-society** | Staff invite/list, roles admin vs staff, RBAC guard on mutating endpoints, real per-user identity in UI | ~2–3 days | **Recommended** — a society has multiple managers/guards |
| **C. Multi-society tenancy** | `society_id` scoping on every query + society switcher + per-society config (incl. `official_summary_languages`) + data isolation | ~1–2 weeks, touches every query | Post-pilot; do when 2nd society signs |

**Recommendation:** **B** for the pilot. A real society has more than one
person (manager + watchmen); single shared admin is operationally weak
and a security smell, but full multi-tenancy (C) is premature before a
second customer. C is a deliberate post-pilot project, not a patch.

## Gap #3 — i18n completeness

Current: nav/headers/key labels are hard-coded bilingual
(`"Open · खुली"`); not driven by the i18n layer; not every string
covered; Marathi not offered though residents/staff may want it.

| Level | What it adds | Effort | Pilot fit |
|---|---|---|---|
| **A. Defer** | Keep pragmatic inline EN·HI | 0 | Acceptable for a Hindi-belt pilot |
| **B. Full pass** | Extract all strings to i18n dicts, complete EN+HI, optional MR | ~1–2 days | Polish, not blocker |

**Recommendation:** **Defer #3** for the pilot. The dashboard is already
readable in EN+HI; full localization is polish that competes with
higher-value work (#2, voice/Twilio go-live). Revisit if a society
explicitly needs Marathi UI or full Hindi.

## Proposed decision
- #2 → **B** (multi-user single-society), scheduled as its own focused
  build with its own tests.
- #3 → **defer**, tracked as known polish.
- #2-C (multi-society) → explicit post-pilot roadmap item.
