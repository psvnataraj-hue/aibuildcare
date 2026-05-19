# Morning brief — 2026-05-20 (overnight autonomous work)

## What shipped (all pushed to `main`, NOT deployed to Render)
| Commit | What | Tests |
|---|---|---|
| `209b153` | Foundation **F1**: RBAC matrix (`services/rbac.py`, 11 roles, spec Part 1.2) + `current_society()` / `require()` deps + identity carries `society_id`. Behaviour-neutral scaffolding. | 153 |
| `22e647b` | Foundation **F2**: tenant isolation on the complaint path + 2-society isolation suite (the merge gate). | **157** |

Full suite green at every commit. Prod Supabase **untouched**; **no Render deploy** (your reviewed action). Branch is ahead of deployed — review before deploying.

## Why I stopped before F3 (honest call)
I told you "F2 + F3 then stop." On reaching F3 I judged it deserves your eye first: **F3 attaches `require(permission)` to endpoints — that encodes access *policy*, not just mechanism.** The mechanism is built and unit-tested (F1); the *mapping* of which permission guards which endpoint is a set of policy decisions I shouldn't finalize unreviewed. So I stopped at a clean, fully-tested checkpoint and propose the mapping below for a 2-minute approval.

## F3 — proposed endpoint → permission mapping (approve/adjust)
Seed admin = `admin` = all permissions, so existing flows are unaffected; this only restricts lower roles (relevant once E1 adds real staff/managers).

| Endpoint | Proposed permission |
|---|---|
| `GET /complaints`, `GET /complaints/{id}`, `/messages` (GET), contractors list/analytics/performance | `view_all` |
| `POST /complaints` (dashboard create) | `file_complaint` |
| `POST /complaints/{id}/assign` | `assign` |
| `POST /complaints/{id}/status`, `POST /complaints/{id}/messages` | `resolve` |
| `POST /complaints/{id}/rate` | `file_complaint` (resident-side action; broadly allowed) |
| `GET /admin/config` | `view_all` |
| `POST /admin/config/{key}` | `modify_config` |

Open question for you: should **rate** be tighter, and should dashboard **create** be `view_all` (staff-on-behalf) rather than `file_complaint`? Your call.

## Flagged design fork (needs your decision) — strict vs interim scoping
F2 threads an **optional** `society_id` (None → default society) for back-compat so the 153 existing tests + webhooks kept working without a mass rewrite. The design doc's ideal is a **mandatory** `society_id` on every service fn (no silent default). Recommendation: keep the interim now (pilot is 1–few societies); schedule **F2b "strict hardening"** = make the arg mandatory + migrate the ~older tests, once E1 lands real multi-society data. Low risk today; flagged so it isn't forgotten.

## Flagged residual (not a leak for the pilot)
Contractor/analytics/`system_config` reads are **not yet society-scoped** (still global). Lower-risk (vendor roster, not resident PII) and tied to E1's per-society contractor model. Scope them in **F2b/E1**. Documented, not silently skipped.

## Exact next steps (in order)
1. **You:** approve/adjust the F3 permission table above + the rate/create question.
2. Me: implement **F3** (attach `require()` per the approved table) + RBAC endpoint tests (low-priv token → 403).
3. Me: **F2b** — society-scope contractor/analytics + strict-arg hardening.
4. Then **E1** (staff/escalation/SLA schema + routing) — its own design pass with you.
5. Deploy decision: once Foundation (F1–F3) is complete & reviewed, Manual Deploy to Render and re-run the live smoke (Google Form + WhatsApp voice still work; new tenant scoping is transparent for the single pilot society).

Nothing is half-done; every commit is independently green and revertable.
