-- Finding 001 (007): the seeded operator becomes the cross-tenant
-- `platform_operator` role.
--
-- Additive, idempotent data migration. Safe to run on the live
-- Supabase DB. Fresh DBs are already correct (seed.py inserts the
-- operator with role='platform_operator'); this brings existing prod
-- DBs in line. The operator KEEPS its non-NULL society_id (society 1)
-- — `platform_operator` is bound to a society for `current_society`
-- endpoints and uses `target_society` for cross-tenant reach.
--
-- This is data, not schema — no 001_init*.sql change is needed.

UPDATE users SET role = 'platform_operator'
    WHERE email = 'admin@aibuildcare.app' AND role = 'admin';
