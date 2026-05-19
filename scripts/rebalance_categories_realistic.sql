-- Phase 4.5 follow-up: realistic per-category winners (CARIMO should
-- NOT top every category). Competitors win AC / Plumbing / Civil;
-- CARIMO keeps Electrical / Elevator / Security. Small deltas only.
-- Applied live to Supabase 2026-05-19 (1 row each).

UPDATE contractors SET average_rating = 5.0 WHERE name = 'Urban HVAC Solutions';
UPDATE contractors SET average_rating = 4.7 WHERE name = 'CARIMO HVAC';
UPDATE contractors SET average_rating = 5.0 WHERE name = 'Urban Water Solutions';
UPDATE contractors SET average_rating = 4.6 WHERE name = 'CARIMO Plumbing & Waterproofing';
UPDATE contractors SET average_rating = 5.0 WHERE name = 'Adani Building Solutions';
UPDATE contractors SET average_rating = 4.7 WHERE name = 'CARIMO Civil Works';
