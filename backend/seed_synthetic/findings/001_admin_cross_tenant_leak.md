# Finding 001 — Admin role has cross-tenant data reach

**Discovered**: 2026-05-22, during Part 2 (synthetic people) of the
synthetic-data + diagnostics build. The tester (Sravya) was originally
planned to receive a `role='admin'` account on a demo tenant. Auditing
"does admin-on-sid-100 stay scoped to sid=100?" turned up six paths
where the multi-tenancy wall does not hold.

**Severity**: HIGH for production rollout, dormant today.

**Status today**: dormant. There is exactly one `admin` user in the
production DB (the seeded `admin@aibuildcare.app` at sid=1), and exactly
one society (sid=1, Palms Residency). Global aggregates therefore
coincide with Palms-only aggregates — the leak has nothing to leak.

**Activation condition**: the leak activates the moment any of these
becomes true:

- A second society is created (real customer #2 onboarded), AND
- Any admin user exists on either society

The synthetic-data system deliberately avoids creating new admin users
on demo societies (sid 100-103) precisely to keep this dormant. Tester
accounts use `role='secretary'` instead (rbac.py:50 — secretary respects
society_id in queries).

---

## The six bypass paths

### 1. Admin gets ALL_PERMISSIONS unconditionally

- `backend/app/services/rbac.py:79-80` — `permissions_for()` returns
  `ALL_PERMISSIONS` for `role == "admin"` *before* applying any
  society-scoped overrides.
- `backend/app/services/rbac.py:121-122` — `has_permission()` returns
  `True` immediately for admin role.

By itself, "admin has all permissions" is fine — the question is whether
those permissions are scoped to admin's own society or not. The other
five paths show they aren't.

### 2. Admin user has NULL society_id

- `backend/app/seed.py:29-37` — the seeded admin is inserted with no
  `society_id` column set; it defaults to NULL.

A NULL `society_id` on the calling user bypasses the `current_society`
dependency in routers that would otherwise enforce `user.society_id ==
target.society_id`. The admin effectively has "no home society", so no
WHERE-clause is built that constrains it.

### 3. Admin-only endpoints accept arbitrary `?society_id=`

- `backend/app/routers/admin.py:28-40` — `_target_society()` accepts a
  `society_id` query parameter and only enforces the "match caller's
  own society" check when the caller is NOT admin. Admins can target
  any society.
- Endpoints affected (all permit `?society_id=` for admin):
  - `GET /api/v1/admin/permissions?society_id=…`  (admin.py:43-57)
  - `GET /api/v1/admin/permissions/overrides?society_id=…`  (admin.py:60-67)
  - `PUT /api/v1/admin/permissions/overrides?society_id=…`  (admin.py:70-82)
  - `DELETE /api/v1/admin/permissions/overrides?society_id=…`  (admin.py:85-94)

An admin on sid=100 could modify Palms's RBAC overrides by passing
`?society_id=1`.

### 4. Analytics endpoint queries globally, no society_id filter

- `backend/app/services/complaint_service.py:972-996` — `analytics()`
  runs queries of the form `SELECT COUNT(*) FROM complaints` and
  `SELECT status, COUNT(*) FROM complaints GROUP BY status` with **no
  `society_id` filter in the WHERE clause**.
- `backend/app/routers/complaints.py:20-23` — the `/api/v1/analytics`
  route calls `svc.analytics()` without passing a society_id.

This is the most visible of the leaks — the dashboard analytics tile,
viewed by an admin on any society, shows global aggregates.

### 5. Contractors endpoint queries globally

- `backend/app/routers/complaints.py:26-37` — the `/api/v1/contractors`
  route queries all contractors with no society_id filter.

Same shape as #4. Less visible but equally cross-tenant.

### 6. No society-picker UI but query params are public

There is no frontend "switch society" picker today, so a non-admin
cannot accidentally request another society's data via the dashboard.
But the backend's acceptance of `?society_id=…` on admin endpoints
means anyone with `role='admin'` can target any society from a script,
a curl call, or a deliberately-modified frontend request.

---

## Architectural decisions attached

Two clean directions; either is reasonable but they require a product
decision:

**Option A — "Admin" becomes tenant-scoped; a new "platform super-admin"
role is introduced for true cross-tenant operations.**

- Add `platform_super_admin` to `ROLE_PERMISSIONS` in rbac.py.
- Update `permissions_for()` / `has_permission()` to NOT short-circuit
  on `admin` — admin's permissions still come from the matrix, scoped
  to its society.
- Move `_target_society()` admin override behind `platform_super_admin`.
- Add society_id filter to `analytics()` and `/contractors`.
- Migrate the existing `admin@aibuildcare.app` user to
  `platform_super_admin` (so Nataraj keeps current behavior).
- Demo / per-customer admins get the new scoped semantics.

Pros: cleanest separation, customers' admins genuinely can't see other
customers. Matches the typical SaaS multi-tenant pattern.

Cons: requires a schema/role addition + a careful migration of the one
existing admin user.

**Option B — Every endpoint gets explicit society_id filtering;
"admin" remains globally privileged.**

- Add society_id filter to `analytics()` and `/contractors`.
- Restrict `?society_id=` query param on admin endpoints to match the
  admin user's own `society_id` (require non-NULL society_id on admin
  records).
- Seed a per-society admin for each tenant instead of one global admin.

Pros: smaller change set, no new role.

Cons: every NEW endpoint added in future needs the same discipline; the
"admin can see all" affordance has to be replaced with a different
mechanism (an op-tools panel that uses `platform_super_admin` anyway —
so this option tends to converge with Option A over time).

**Recommendation**: Option A. The pattern is mature, well-understood,
and easier to maintain — once `admin` is scoped, future endpoints don't
need to remember to filter, and cross-tenant operations are visibly
gated by an explicit privileged role.

---

## Why this is on the critical path before paying customer #2

Customer #1 (Palms, sid=1) is the only society today, so this finding
has no operational impact yet. The moment a paying customer #2 is
onboarded:

- Their first admin user (and any subsequent admins) will see Palms's
  complaint counts, contractor list, and RBAC config by default.
- Vice versa: Palms admin will see customer #2's data.
- If the product pitch is "your tenants' data stays private", this is
  a hard contradiction — and one that surfaces immediately on the
  customer's first login, not after a usage pattern develops.

For the housing-society and especially the hospital verticals, this is
the kind of issue that, discovered post-launch, ends a deployment.
Discovered now, it's a couple of days of careful work and a migration.

---

## What this build does to avoid activating it

- No new admin users are created on demo societies. Tester accounts use
  `role='secretary'` (rbac.py:50), which carries `_LEADER` permissions
  including `AUTHORIZE_ENFORCEMENT` but DOES respect society_id.
- The existing Palms admin is unchanged.
- The leak therefore remains dormant for the duration of demo / pilot
  work.

---

## Recommended next steps (separate change set)

1. Pick Option A vs Option B (Nataraj decision).
2. Open a tracking issue against the architectural fork.
3. Schedule the change BEFORE customer #2 is onboarded. Specifically,
   before any admin user (current Palms or future) is given access
   simultaneously with another customer's admin.
4. The fix is well-bounded: 6 files touched, ~150 lines of code,
   plus the migration. Estimate: 1-2 days of focused work + a careful
   review.
