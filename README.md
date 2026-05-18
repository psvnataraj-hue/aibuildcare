# AIBuildCare — Phase 1

AI-powered building complaint management. Residents report issues over
WhatsApp / SMS / Email; Claude Haiku 4.5 parses each into structured data
(unit, category, priority, acknowledgement); staff manage the lifecycle on a
Vue dashboard.

## Stack
- Backend: FastAPI + Python 3.12 + SQLite
- Frontend: Vue 3 + TypeScript + Vite + Tailwind
- LLM: Claude Haiku 4.5 (`anthropic` SDK) with deterministic rule-based fallback
- Messaging: Twilio sandbox + SendGrid
- Deploy: Render.com (`render.yaml`)

## Backend — local run
```
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python app/main.py              # http://127.0.0.1:8000/health
pytest                          # test suite
```
Default admin: `admin@aibuildcare.app` / value of `SEED_ADMIN_PASSWORD`.

## Frontend — local run
```
cd frontend
npm install
npm run dev                     # http://localhost:5173
npm run build                   # -> dist/
```

## Configuration
Copy `.env.example` to `.env`. With no `ANTHROPIC_API_KEY`, the rule-based
parser is used so the system runs fully offline. Provider keys (Twilio,
SendGrid) are optional; outbound notifications no-op without them.

## API
| Method | Path | Notes |
|--------|------|-------|
| GET  | `/health` | liveness |
| POST | `/api/v1/auth/login` | JWT |
| GET/POST | `/api/v1/complaints` | list / create |
| GET | `/api/v1/complaints/{id}` | detail + thread |
| POST | `/api/v1/complaints/{id}/assign` | assign contractor |
| POST | `/api/v1/complaints/{id}/status` | advance status |
| GET/POST | `/api/v1/complaints/{id}/messages` | thread |
| GET | `/api/v1/analytics` | top-line metrics |
| WS | `/api/v1/ws` | live updates |
| POST | `/webhooks/twilio/whatsapp` `/twilio/sms` `/sendgrid/inbound-email` | intake |
