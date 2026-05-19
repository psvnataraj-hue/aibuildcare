-- Phase 5: additive, idempotent. Safe to run on the live Supabase DB.
-- (Fresh DBs already get these via 001_init*.sql.)

CREATE TABLE IF NOT EXISTS system_config (
    config_key   TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

INSERT INTO system_config (config_key, config_value) VALUES
    ('max_pending_jobs_per_contractor', '10'),
    ('load_balancing_enabled', 'true')
ON CONFLICT (config_key) DO NOTHING;

ALTER TABLE complaints ADD COLUMN IF NOT EXISTS estimated_completion_date TEXT;

-- SQLite equivalents for an existing local dev DB (no IF NOT EXISTS):
--   ALTER TABLE complaints ADD COLUMN estimated_completion_date TEXT;
--   (system_config is created by CREATE TABLE IF NOT EXISTS above)
