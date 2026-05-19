-- Test data: 30 fictitious contractors across 6 service categories.
-- All share the CARIMO test WhatsApp number +919082397027 so assignment
-- notifications can be received during pilot testing; the message names
-- the contractor so they are distinguishable.
--
-- NOTE: the live schema column is `specialty` (not `categories`). The
-- comma-separated category list is stored in `specialty`.
-- One-time script; re-running will create duplicates (no UNIQUE on name).

INSERT INTO contractors (name, phone, specialty) VALUES
-- HVAC (AC/Cooling/Heating)
('CARIMO HVAC', '+919082397027', 'AC/Cooling,Heating'),
('Urban HVAC Solutions', '+919082397027', 'AC/Cooling,Heating'),
('Adani Climate Control', '+919082397027', 'AC/Cooling,Heating'),
('TATA HVAC Systems', '+919082397027', 'AC/Cooling,Heating'),
('Voltas Air Systems', '+919082397027', 'AC/Cooling,Heating'),
-- Electricals
('CARIMO Electricals', '+919082397027', 'Electrical,Wiring,Lighting'),
('Urban Power Solutions', '+919082397027', 'Electrical,Wiring,Lighting'),
('Adani Electrical Works', '+919082397027', 'Electrical,Wiring,Lighting'),
('TATA Electrical Industries', '+919082397027', 'Electrical,Wiring,Lighting'),
('Havells Service Center', '+919082397027', 'Electrical,Wiring,Lighting'),
-- Plumbing & Waterproofing
('CARIMO Plumbing & Waterproofing', '+919082397027', 'Plumbing,Water Supply,Waterproofing'),
('Urban Water Solutions', '+919082397027', 'Plumbing,Water Supply,Waterproofing'),
('Adani Plumbing Works', '+919082397027', 'Plumbing,Water Supply,Waterproofing'),
('TATA Pipe Systems', '+919082397027', 'Plumbing,Water Supply,Waterproofing'),
('Godrej Waterproofing', '+919082397027', 'Plumbing,Water Supply,Waterproofing'),
-- Lift Maintenance
('CARIMO Lift Maintenance', '+919082397027', 'Lift/Elevator,Mechanical'),
('Urban Lift Services', '+919082397027', 'Lift/Elevator,Mechanical'),
('Adani Elevator Solutions', '+919082397027', 'Lift/Elevator,Mechanical'),
('TATA Lift Systems', '+919082397027', 'Lift/Elevator,Mechanical'),
('Schindler Maintenance', '+919082397027', 'Lift/Elevator,Mechanical'),
-- Civil Works & Structural
('CARIMO Civil Works', '+919082397027', 'Civil,Structural,Concrete'),
('Urban Construction', '+919082397027', 'Civil,Structural,Concrete'),
('Adani Building Solutions', '+919082397027', 'Civil,Structural,Concrete'),
('TATA Structural Engineers', '+919082397027', 'Civil,Structural,Concrete'),
('L&T Civil Services', '+919082397027', 'Civil,Structural,Concrete'),
-- Maintenance Office (General/Admin)
('CARIMO Maintenance Office', '+919082397027', 'General,Common Area,Security'),
('Urban Maintenance Team', '+919082397027', 'General,Common Area,Security'),
('Adani Maintenance Services', '+919082397027', 'General,Common Area,Security'),
('TATA Building Maintenance', '+919082397027', 'General,Common Area,Security'),
('Facilities Management Pro', '+919082397027', 'General,Common Area,Security');
