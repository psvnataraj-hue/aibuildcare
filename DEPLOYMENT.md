# AIBuildCare — Deployment & Integration Guide

Backend is live on Render (manual-sync Blueprint). This guide covers the
new Phase-2+ pieces: persistent DB, image storage, audio, Google Forms,
dashboard, and custom domain.

## 1. Persistent database — Supabase (free Postgres)

1. supabase.com → New project → wait for it to provision.
2. Project Settings → Database → **Connection string** → **URI**.
   Copy it: `postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres`
3. Render → `aibuildcare-api` → Environment → set:
   ```
   AIBUILDCARE_DATABASE_URL = postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres
   ```
4. Save → redeploy. On boot the app auto-creates all tables (idempotent
   `migrations/001_init_pg.sql`). Tickets now survive restarts.
   Local dev/tests are unaffected — they still use SQLite.

## 2. Image storage — Cloudflare R2 (free 10 GB)

1. Cloudflare dashboard → R2 → Create bucket `aibuildcare-assets`.
2. Bucket → Settings → enable **Public access** (or attach a public
   custom domain). Note the public base URL.
3. R2 → Manage API Tokens → create token (Object Read & Write). Note
   Access Key ID, Secret, and the S3 endpoint
   `https://<accountid>.r2.cloudflarestorage.com`.
4. Render `aibuildcare-api` → Environment:
   ```
   AIBUILDCARE_R2_ENDPOINT_URL    = https://<accountid>.r2.cloudflarestorage.com
   AIBUILDCARE_R2_ACCESS_KEY_ID   = <key id>
   AIBUILDCARE_R2_SECRET_ACCESS_KEY = <secret>
   AIBUILDCARE_R2_BUCKET          = aibuildcare-assets
   AIBUILDCARE_R2_PUBLIC_BASE_URL = <public bucket URL>
   ```
If unset, photo upload is skipped gracefully — tickets still log.

## 3. Audio voice notes — local Whisper (free)

PyTorch is too heavy for Render's 512 MB free tier, so `openai-whisper`
is intentionally **not** in `requirements.txt`. Where you run a host with
≥ ~2 GB RAM (your laptop, a Render paid instance, or any VM):
```
pip install -r backend/requirements-audio.txt
```
Then voice notes are auto-transcribed (`whisper.load_model("base")`).
On Render free, an audio message still creates a ticket
("voice note received — transcription unavailable"); nothing crashes.

## 4. Google Forms intake (free, unlimited)

Create a Form with: Unit, Description, Category, Priority, Phone,
optional Photo. Extensions → Apps Script → paste, save, add an
**On form submit** trigger:

```javascript
function onFormSubmit(e) {
  var r = e.response.getItemResponses();
  var unit = r[0].getResponse(), desc = r[1].getResponse(),
      cat = r[2].getResponse(), pri = r[3].getResponse(),
      phone = r[4].getResponse();
  var payload = {
    raw_text: desc + " (Unit: " + unit + ", Category: " + cat +
              ", Priority: " + pri + ")",
    phone: phone
  };
  UrlFetchApp.fetch(
    "https://aibuildcare-api.onrender.com/webhooks/forms",
    { method: "post", contentType: "application/json",
      payload: JSON.stringify(payload), muteHttpExceptions: true });
}
```
`/webhooks/forms` needs no auth (Apps Script can't mint a JWT).

## 5. Dashboard (frontend) on Render

Already a static site in `render.yaml` (`aibuildcare-web`). Set its env
var so it calls the live API:
```
VITE_API_BASE = https://aibuildcare-api.onrender.com
```
Backend CORS already allows `aibuildcare-web.onrender.com` and
`aibuildcare.carimotech.in` (configurable via `AIBUILDCARE_CORS_ORIGINS`).
Login: `admin@aibuildcare.app` / value of `AIBUILDCARE_SEED_ADMIN_PASSWORD`.

## 6. Custom domain (Hostinger DNS → Render)

- Render `aibuildcare-api` → Settings → Custom Domain → add
  `aibuildcare.carimotech.in`; Render shows a CNAME target.
- Hostinger → carimotech.in DNS → add CNAME:
  `aibuildcare` → `<target>.onrender.com`.
- Repeat for the web app if you want `app.aibuildcare.carimotech.in`.
- After DNS resolves, update Twilio's WhatsApp webhook to the custom
  domain and add it to `AIBUILDCARE_CORS_ORIGINS`.

## Render env var checklist (`aibuildcare-api`)
```
AIBUILDCARE_ANTHROPIC_API_KEY      (set)
AIBUILDCARE_TWILIO_ACCOUNT_SID     (set)
AIBUILDCARE_TWILIO_AUTH_TOKEN      (set)
AIBUILDCARE_DATABASE_URL           Supabase URI        <- §1
AIBUILDCARE_R2_ENDPOINT_URL        Cloudflare R2       <- §2
AIBUILDCARE_R2_ACCESS_KEY_ID
AIBUILDCARE_R2_SECRET_ACCESS_KEY
AIBUILDCARE_R2_PUBLIC_BASE_URL
AIBUILDCARE_JWT_SECRET             (auto-generated)
```
