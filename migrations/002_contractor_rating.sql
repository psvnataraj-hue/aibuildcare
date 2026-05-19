-- Phase 4.5: add average_rating to an EXISTING contractors table
-- (fresh DBs already get it via 001_init*.sql). Additive + idempotent;
-- safe to run on the live Supabase database.
-- Postgres:
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS average_rating NUMERIC(3,2) NOT NULL DEFAULT 5.0;
-- SQLite has no ADD COLUMN IF NOT EXISTS; for existing local dev DBs run:
--   ALTER TABLE contractors ADD COLUMN average_rating REAL NOT NULL DEFAULT 5.0;
-- (or just delete the dev .db; it is rebuilt from 001_init.sql)
