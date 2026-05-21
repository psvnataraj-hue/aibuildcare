-- Phase 6 (005): operator-readable event log + cron heartbeat row.
-- Additive, idempotent. Safe to run on the live Supabase DB.
-- Part 4 of the synthetic-data + diagnostics build.
--
-- Schema added inline in 001_init*.sql so fresh DBs match.

CREATE TABLE IF NOT EXISTS operator_events (
    id           SERIAL PRIMARY KEY,
    ts           TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    event_type   TEXT NOT NULL,
    service      TEXT,
    severity     TEXT NOT NULL DEFAULT 'info',
    message      TEXT NOT NULL,
    metadata     TEXT,
    society_id   INTEGER,
    seen         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_operator_events_ts        ON operator_events(ts);
CREATE INDEX IF NOT EXISTS idx_operator_events_severity  ON operator_events(severity);
CREATE INDEX IF NOT EXISTS idx_operator_events_service   ON operator_events(service);

-- Cron heartbeat (re-uses existing system_config table from 003).
-- The cron writes 'cron_last_tick_at' = ISO timestamp at the start of
-- every tick. A health-check function reads it to detect dead-man's
-- switch (no tick in >45 min = alert).
INSERT INTO system_config (config_key, config_value) VALUES
    ('cron_last_tick_at', '1970-01-01T00:00:00+00:00')
ON CONFLICT (config_key) DO NOTHING;

-- SQLite equivalents for an existing local dev DB (no IF NOT EXISTS support
-- on ALTER, but the CREATE TABLE IF NOT EXISTS above works as-is):
--   The same statements run as-is on SQLite when included in 001_init.sql.
