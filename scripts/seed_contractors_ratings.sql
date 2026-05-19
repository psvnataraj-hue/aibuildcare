-- Phase 4.5 reference seed: 30 contractors w/ ratings, 6 categories,
-- shared CARIMO test WhatsApp +919082397027.
--
-- IMPORTANT: on the LIVE database the 30 rows already existed (from the
-- earlier contractor seed), so this was applied as UPDATE-by-name to set
-- average_rating (NOT re-INSERTed) to avoid duplicates. This INSERT form
-- is for FRESH databases / reference. `specialty` is the real column
-- (the spec's `categories` does not exist); is_active uses 1 (the schema
-- column is INTEGER, not boolean).
--
-- Requires the average_rating column (001_init*.sql for fresh DBs, or
-- 002_contractor_rating.sql ALTER for an existing DB).

INSERT INTO contractors (name, phone, specialty, average_rating, is_active) VALUES
('CARIMO HVAC','+919082397027','AC/Cooling,Heating',5.0,1),
('Urban HVAC Solutions','+919082397027','AC/Cooling,Heating',4.8,1),
('Adani Climate Control','+919082397027','AC/Cooling,Heating',4.5,1),
('TATA HVAC Systems','+919082397027','AC/Cooling,Heating',4.2,1),
('Voltas Air Systems','+919082397027','AC/Cooling,Heating',3.9,1),
('CARIMO Electricals','+919082397027','Electrical,Wiring,Lighting',5.0,1),
('Urban Power Solutions','+919082397027','Electrical,Wiring,Lighting',4.8,1),
('Adani Electrical Works','+919082397027','Electrical,Wiring,Lighting',4.6,1),
('TATA Electrical Industries','+919082397027','Electrical,Wiring,Lighting',4.3,1),
('Havells Service Center','+919082397027','Electrical,Wiring,Lighting',4.0,1),
('CARIMO Plumbing & Waterproofing','+919082397027','Plumbing,Water Supply,Waterproofing',5.0,1),
('Urban Water Solutions','+919082397027','Plumbing,Water Supply,Waterproofing',4.7,1),
('Adani Plumbing Works','+919082397027','Plumbing,Water Supply,Waterproofing',4.5,1),
('TATA Pipe Systems','+919082397027','Plumbing,Water Supply,Waterproofing',4.4,1),
('Godrej Waterproofing','+919082397027','Plumbing,Water Supply,Waterproofing',4.1,1),
('CARIMO Lift Maintenance','+919082397027','Lift/Elevator,Mechanical',5.0,1),
('Urban Lift Services','+919082397027','Lift/Elevator,Mechanical',4.9,1),
('Adani Elevator Solutions','+919082397027','Lift/Elevator,Mechanical',4.6,1),
('TATA Lift Systems','+919082397027','Lift/Elevator,Mechanical',4.3,1),
('Schindler Maintenance','+919082397027','Lift/Elevator,Mechanical',4.0,1),
('CARIMO Civil Works','+919082397027','Civil,Structural,Concrete',5.0,1),
('Urban Construction','+919082397027','Civil,Structural,Concrete',4.7,1),
('Adani Building Solutions','+919082397027','Civil,Structural,Concrete',4.5,1),
('TATA Structural Engineers','+919082397027','Civil,Structural,Concrete',4.2,1),
('L&T Civil Services','+919082397027','Civil,Structural,Concrete',3.8,1),
('CARIMO Maintenance Office','+919082397027','General,Common Area,Security',5.0,1),
('Urban Maintenance Team','+919082397027','General,Common Area,Security',4.6,1),
('Adani Maintenance Services','+919082397027','General,Common Area,Security',4.4,1),
('TATA Building Maintenance','+919082397027','General,Common Area,Security',4.1,1),
('Facilities Management Pro','+919082397027','General,Common Area,Security',3.9,1);
