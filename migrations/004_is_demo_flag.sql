-- Phase 6 (004): additive, idempotent. Safe to run on the live Supabase DB.
-- Adds `is_demo` flag to societies for structural separation of synthetic
-- demo tenants (sid 100-103) from real pilot tenants (sid 1 = Palms Residency).
--
-- Fresh DBs already get this via 001_init*.sql (column added inline).
-- This file exists so existing prod DBs (Supabase) can be brought in line
-- without recreating tables.
--
-- After applying, real societies retain is_demo=0 (the DEFAULT). Demo
-- societies are inserted by the Part 1 seeder with is_demo=1. The wipe
-- utility refuses to operate on any society where is_demo != 1, and
-- additionally hard-refuses on sid=1 as an independent second guard.

ALTER TABLE societies ADD COLUMN IF NOT EXISTS is_demo INTEGER NOT NULL DEFAULT 0;

-- SQLite equivalent for an existing local dev DB (no IF NOT EXISTS support):
--   ALTER TABLE societies ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;
