-- Phase 4.5 rebalance: give the 4 original demo contractors realistic,
-- competitive ratings (not all 5.0) so auto-assignment is realistic.
-- CARIMO stays top in every category; demo contractors remain strong
-- competitors and active (for testing manual override / reassign).
--
-- NOTE: real seeded names are '... Services'/'... Electricals' (the
-- spec's 'CoolAir'/'Voltz' would match nothing). Applied live to
-- Supabase 2026-05-19 (each UPDATE affected exactly 1 row).

UPDATE contractors SET average_rating = 4.6 WHERE name = 'CoolAir Services';
UPDATE contractors SET average_rating = 4.9 WHERE name = 'AquaFix Plumbers';
UPDATE contractors SET average_rating = 4.7 WHERE name = 'Voltz Electricals';
UPDATE contractors SET average_rating = 4.8 WHERE name = 'LiftCare';
