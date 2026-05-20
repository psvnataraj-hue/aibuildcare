# Parking violation management — design

_2026-05-20. Built on Foundation + E1 + E2. A vertical workflow that
reuses the existing engines (society scoping, RBAC, escalation,
incident flagging, notifications) rather than reinventing them._

## Key architecture decision (locked recommendation)

**Extend the `complaints` table** with optional parking-specific
columns; do NOT build a parallel `parking_violations` table.

Why: a parking violation already IS a complaint (category =
`Parking Management`). Reusing the table gets us society scoping,
escalation_hierarchy, status history, message threading, major-
incident flagging, weekly summary, and the existing auth/RBAC
plumbing **for free**. A parallel table would mean re-doing all of
that. The marginal cost — a few NULL columns on non-parking
complaints — is negligible.

Plate/owner registry (`vehicles`) is a new table; that one is
genuinely separate because it's a long-lived directory, not a single
ticket.

## Phased delivery

| Sub | Backend / Frontend | Scope |
|---|---|---|
| **P1** | Backend | `vehicles` table + CRUD endpoints (`/api/v1/vehicles*`); society-scoped, gated by `MODIFY_STAFF` for mutations, `VIEW_ALL` for reads |
| **P2** | Backend | New optional `complaints` columns: `vehicle_plate`, `vehicle_id`, `violation_type`, `clamped`, `clamped_at`, `clamping_authorized_by`. On create with category=Parking + plate, auto-link vehicle + WhatsApp the owner |
| **P3** | Backend | Extend `incident_flagging`: 5th heuristic *"repeat parking offender — same plate ≥ 3 violations in 30 days"* |
| **P4** | Backend | `POST /api/v1/complaints/{cid}/authorize-clamping` gated by `AUTHORIZE_ENFORCEMENT` (sr_manager / secretary / chairman / committee / admin in the default matrix) |
| **P5** | Frontend | Parking-specific complaint form (plate input, violation_type select, photo upload); vehicles directory page; clamping button on complaint detail |

P1–P4 are bounded backend chunks; each independently shippable and
testable. P5 sits inside the E3 frontend pass.

## Schema (additive idempotent on prod)

```sql
-- new table
CREATE TABLE IF NOT EXISTS vehicles (
    id              SERIAL/AUTOINCREMENT,
    society_id      INTEGER NOT NULL REFERENCES societies(id),
    plate_number    TEXT NOT NULL,
    owner_unit_number TEXT,
    owner_name      TEXT,
    owner_phone     TEXT,
    vehicle_type    TEXT,                -- car / two-wheeler / etc
    make_model      TEXT,
    color           TEXT,
    registered_at   TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    UNIQUE(society_id, plate_number)     -- plate unique within society
);

-- complaint extensions (ALTER ADD COLUMN IF NOT EXISTS for prod)
ALTER TABLE complaints
  ADD COLUMN vehicle_plate TEXT,
  ADD COLUMN vehicle_id INTEGER,
  ADD COLUMN violation_type TEXT,
  ADD COLUMN clamped INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN clamped_at TEXT,
  ADD COLUMN clamping_authorized_by INTEGER;
```

## Lifecycle (parking complaint)

```
report (with plate)
   │
   ▼
auto-link to vehicle (society + plate match) ──▶ owner found?
   │                                              │ yes
   ▼                                              ▼
existing complaint flow (auto-route /        WhatsApp owner:
  escalate / weekly summary)                 "Your vehicle <plate>
                                              has been reported for
                                              <violation_type>..."
   │
   ├─▶ incident_flagging (P3): same plate ≥ 3 violations / 30d
   │                            → major_incident "repeat offender"
   │
   └─▶ authorize-clamping (P4)
         requires AUTHORIZE_ENFORCEMENT
         sets clamped=1, clamped_at, clamping_authorized_by
         WhatsApp enforcement_officer + owner
```

## Violation types (enum kept lean)
- `no_parking_zone`
- `blocking_fire_exit`
- `double_parked`
- `expired_permit`
- `unauthorized_visitor`
- `wrong_slot`
- `other`

(Like roles, this is whitelisted in code; can be extended in one
place without a migration.)

## Open question for you (just one)

For now, the design assumes a parking violation is **reported by a
staff/resident** (channel = whatsapp/dashboard/form). Some societies
hand out **handheld scanners** to security guards who scan plates
and log violations from a phone app. Is that a near-term need?
If yes, we'd add a `POST /api/v1/parking/quick-report` shortcut and
a mobile-first UI in P5. If no, the regular complaint flow is
sufficient.

## Decisions baked (no fork)
- Reuse complaints table + engines (do not build parallel models).
- enforcement_officer role already in RBAC matrix.
- Notification reuses existing WhatsApp send (with R2 + Sarvam TTS
  if the society has those wired).
- No payment integration in this phase (fine collection is manual).
- Resident "challenge a violation" UI deferred (would need the
  resident portal, which is itself deferred).
