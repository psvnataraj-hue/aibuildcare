-- AIBuildCare Phase 1 — initial schema (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS societies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    address       TEXT,
    is_demo       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS units (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id    INTEGER NOT NULL REFERENCES societies(id),
    unit_number   TEXT NOT NULL,
    owner_name    TEXT,
    phone         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(society_id, unit_number)
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL DEFAULT 'staff',
    society_id    INTEGER REFERENCES societies(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contractors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    phone         TEXT,
    specialty     TEXT,
    average_rating REAL NOT NULL DEFAULT 5.0,
    society_id    INTEGER REFERENCES societies(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    available_for_personal_jobs INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    society_id    INTEGER REFERENCES societies(id),
    sla_hours     INTEGER NOT NULL DEFAULT 24
);

CREATE TABLE IF NOT EXISTS complaints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number   TEXT NOT NULL UNIQUE,
    society_id      INTEGER REFERENCES societies(id),
    unit_id         INTEGER REFERENCES units(id),
    unit_number     TEXT,
    category        TEXT,
    priority        TEXT NOT NULL DEFAULT 'normal',
    status          TEXT NOT NULL DEFAULT 'received',
    channel         TEXT NOT NULL DEFAULT 'dashboard',
    raw_text        TEXT NOT NULL,
    acknowledgement TEXT,
    reporter_phone  TEXT,
    reporter_email  TEXT,
    contractor_id   INTEGER REFERENCES contractors(id),
    media_urls      TEXT,
    detected_language TEXT,
    official_summaries TEXT,
    estimated_completion_date TEXT,
    assigned_staff_id INTEGER,
    escalated_to_manager_at      TEXT,
    escalated_to_sr_manager_at   TEXT,
    escalated_to_secretary_at    TEXT,
    escalated_to_chairman_at     TEXT,
    last_complainant_update_at   TEXT,
    last_assigned_staff_update_at TEXT,
    last_reminder_sent_at        TEXT,
    reminder_sent_count INTEGER NOT NULL DEFAULT 0,
    major_incident               INTEGER NOT NULL DEFAULT 0,
    major_incident_flagged_at    TEXT,
    major_incident_reason        TEXT,
    -- P2: parking-specific columns (matched by pg ALTERs)
    vehicle_plate                TEXT,
    vehicle_id                   INTEGER,
    violation_type               TEXT,
    clamped                      INTEGER NOT NULL DEFAULT 0,
    clamped_at                   TEXT,
    clamping_authorized_by       INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at);

CREATE TABLE IF NOT EXISTS complaint_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id  INTEGER NOT NULL REFERENCES complaints(id),
    sender        TEXT NOT NULL,
    body          TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS complaint_status_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id  INTEGER NOT NULL REFERENCES complaints(id),
    from_status   TEXT,
    to_status     TEXT NOT NULL,
    changed_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS complaint_ratings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id  INTEGER NOT NULL UNIQUE REFERENCES complaints(id),
    rating        INTEGER NOT NULL,
    feedback      TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    token_jti     TEXT NOT NULL UNIQUE,
    expires_at    TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_config (
    config_key   TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS operator_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL DEFAULT (datetime('now')),
    event_type   TEXT NOT NULL,
    service      TEXT,
    severity     TEXT NOT NULL DEFAULT 'info',
    message      TEXT NOT NULL,
    metadata     TEXT,
    society_id   INTEGER,
    seen         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_operator_events_ts       ON operator_events(ts);
CREATE INDEX IF NOT EXISTS idx_operator_events_severity ON operator_events(severity);
CREATE INDEX IF NOT EXISTS idx_operator_events_service  ON operator_events(service);

CREATE TABLE IF NOT EXISTS staff_members (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id    INTEGER NOT NULL REFERENCES societies(id),
    name          TEXT NOT NULL,
    phone_primary    TEXT NOT NULL,
    phone_secondary  TEXT,
    whatsapp_enabled INTEGER NOT NULL DEFAULT 1,
    sms_fallback     INTEGER NOT NULL DEFAULT 1,
    email           TEXT,
    shift_pattern   TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    hire_date       TEXT,
    emergency_contact TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS staff_categories (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id         INTEGER NOT NULL REFERENCES staff_members(id),
    category         TEXT NOT NULL,
    primary_category INTEGER NOT NULL DEFAULT 0,
    skill_level      TEXT NOT NULL DEFAULT 'junior',
    UNIQUE(staff_id, category)
);

CREATE TABLE IF NOT EXISTS contractor_categories (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    contractor_id    INTEGER NOT NULL REFERENCES contractors(id),
    category         TEXT NOT NULL,
    primary_category INTEGER NOT NULL DEFAULT 0,
    average_rating   REAL NOT NULL DEFAULT 5.0,
    completed_jobs   INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(contractor_id, category)
);

CREATE TABLE IF NOT EXISTS escalation_hierarchy (
    id                            INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id                    INTEGER NOT NULL REFERENCES societies(id),
    role_name                     TEXT NOT NULL,
    person_name                   TEXT NOT NULL,
    phone                         TEXT,
    whatsapp_enabled              INTEGER NOT NULL DEFAULT 1,
    email                         TEXT,
    escalation_level              INTEGER NOT NULL,
    response_time_target_minutes  INTEGER NOT NULL DEFAULT 60,
    active                        INTEGER NOT NULL DEFAULT 1,
    created_at                    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS category_sla_config (
    id                           INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id                   INTEGER NOT NULL REFERENCES societies(id),
    category                     TEXT NOT NULL,
    target_response_time_minutes INTEGER NOT NULL,
    target_resolution_time_hours INTEGER NOT NULL,
    priority_high_multiplier     REAL NOT NULL DEFAULT 0.5,
    escalation_levels            TEXT NOT NULL DEFAULT '{}',
    updated_at                   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(society_id, category)
);

CREATE TABLE IF NOT EXISTS weekly_summaries_sent (
    society_id      INTEGER NOT NULL REFERENCES societies(id),
    week_start_date TEXT NOT NULL,
    sent_at         TEXT NOT NULL DEFAULT (datetime('now')),
    recipient_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (society_id, week_start_date)
);

CREATE TABLE IF NOT EXISTS role_permission_overrides (
    society_id  INTEGER NOT NULL REFERENCES societies(id),
    role        TEXT NOT NULL,
    permission  TEXT NOT NULL,
    granted     INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (society_id, role, permission)
);
INSERT OR IGNORE INTO system_config (config_key, config_value) VALUES
    ('max_pending_jobs_per_contractor', '10'),
    ('load_balancing_enabled', 'true'),
    ('cron_last_tick_at', '1970-01-01T00:00:00+00:00');

INSERT OR IGNORE INTO categories (name, sla_hours) VALUES
    ('AC/Cooling', 4),
    ('Plumbing', 8),
    ('Electrical', 6),
    ('Elevator', 2),
    ('Housekeeping', 24),
    ('Security', 2),
    ('Other', 24),
    -- E1 expanded categories
    ('Fire Safety', 1),
    ('Generator/Power Backup', 4),
    ('Water Supply', 4),
    ('Sewage/Drainage', 4),
    ('Lighting', 12),
    ('Garbage/Waste', 8),
    ('Pest Control', 24),
    ('Gardening', 48),
    ('Carpentry', 24),
    ('Painting', 48),
    ('Civil/Structural', 72),
    ('CCTV/Intercom', 24),
    ('Swimming Pool', 24),
    ('Sports/Gym/Clubhouse', 48),
    ('Children''s Play Area', 24),
    ('Parking Management', 24),
    ('Noise/Visitor', 4);

-- P1 (parking vertical): per-society vehicle registry.
-- Plate is unique WITHIN a society (different societies may register
-- the same plate (not a global identity). active is a soft-delete flag.
CREATE TABLE IF NOT EXISTS vehicles (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id        INTEGER NOT NULL REFERENCES societies(id),
    plate_number      TEXT NOT NULL,
    owner_unit_number TEXT,
    owner_name        TEXT,
    owner_phone       TEXT,
    vehicle_type      TEXT,
    make_model        TEXT,
    color             TEXT,
    registered_at     TEXT,
    active            INTEGER NOT NULL DEFAULT 1,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(society_id, plate_number)
);
CREATE INDEX IF NOT EXISTS idx_vehicles_society
    ON vehicles(society_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_plate
    ON vehicles(society_id, plate_number);

-- P2 (parking vertical): parking-specific columns on complaints.
-- sqlite ships with a version older than 3.35 here, so ALTER TABLE
-- ADD COLUMN IF NOT EXISTS is unavailable. Inline the columns into
-- the CREATE TABLE complaints above instead (which we patch below
-- via a helper migration block). For prod the pg migration uses
-- IF NOT EXISTS ALTERs.
--
-- Workaround: tests create fresh DBs (conftest tmp_path) so the
-- complaints table is built from CREATE TABLE IF NOT EXISTS above.
-- We add the parking columns there by re-creating the table only
-- if it doesn't already include them. The simplest safe approach
-- is a DROP-and-recreate at the bottom — but tests have rows by
-- then. Cleanest: edit the original CREATE TABLE itself (done in
-- a separate edit), and leave this block as a no-op for clarity.
