# AIBuildCare Phase 1 — Design

Date: 2026-05-18
Author: Dr. Nataraj Paluri (solo)

## Purpose
AI-powered building complaint management. Residents send complaints over
WhatsApp / SMS / Email. Claude Haiku 4.5 parses each into structured data
(unit, category, priority, acknowledgement). Staff manage the lifecycle on a
Vue dashboard.

## Architecture
- Backend: FastAPI + Python 3.12, SQLite (file at ./data/complaints.db),
  raw SQL via sqlite3 (no ORM — keeps free-tier footprint small).
- Frontend: Vue 3 + TypeScript + Vite + Tailwind.
- LLM: `anthropic` SDK, model `claude-haiku-4-5`. Strict-JSON prompt.
- Messaging: Twilio sandbox (WhatsApp/SMS), SendGrid inbound email.
- Deploy: Render.com free tier (render.yaml).

## Components
- `services/haiku_parser` — LLM parse with deterministic rule-based fallback
  when `ANTHROPIC_API_KEY` is absent (keeps pytest green offline).
- `services/auth_service` — bcrypt + HS256 JWT, seeded admin.
- `services/complaint_service` — CRUD, assignment, status transitions,
  message thread, ticket-number generation (`SER-2026-NNNNN`).
- `services/notify` — Twilio/SendGrid send (no-op when keys absent).
- `services/ws_hub` — in-process WebSocket broadcast of complaint events.
- Routers: health, auth, complaints, webhooks.

## Data flow
1. Inbound webhook (Twilio/SendGrid) or dashboard create.
2. Raw text → Haiku parser → structured fields + acknowledgement.
3. Complaint persisted, status `received`, ticket number assigned.
4. Acknowledgement sent back via originating channel.
5. WS event broadcast → dashboard updates live.
6. Staff assign contractor / advance status; each change logged in
   `complaint_status_history`.

## Status lifecycle
`received → acknowledged → assigned → in_progress → resolved → closed`
(transitions validated server-side).

## Error handling
- All endpoints return structured JSON `{detail: ...}` on error.
- Parser failure → fallback parser, never drops a complaint.
- Notification failure → logged, complaint still saved.

## Testing
- pytest + FastAPI TestClient, isolated temp SQLite per test.
- Parser unit tests use a mocked Anthropic client; one live test skipped
  without a key. 50+ cases across health/auth/complaints/webhooks/parser.

## Decisions
- Raw SQL over ORM (footprint, transparency).
- Rule-based fallback parser is first-class, not a stub (offline CI + cost).
- In-process WS hub (no Redis on free tier).
