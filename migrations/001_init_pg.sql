-- AIBuildCare Phase 1 - Postgres schema (Supabase).
-- Mirrors migrations/001_init.sql (SQLite) 1:1. Timestamps are stored as
-- TEXT in ISO-8601 UTC so application behaviour is byte-identical across
-- both backends (the code inserts datetime.now(timezone.utc).isoformat()).

CREATE TABLE IF NOT EXISTS societies (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    address     TEXT,
    created_at  TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS units (
    id          SERIAL PRIMARY KEY,
    society_id  INTEGER NOT NULL REFERENCES societies(id),
    unit_number TEXT NOT NULL,
    owner_name  TEXT,
    phone       TEXT,
    created_at  TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    UNIQUE(society_id, unit_number)
);

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL DEFAULT 'staff',
    society_id    INTEGER REFERENCES societies(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS contractors (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    specialty   TEXT,
    average_rating NUMERIC(3,2) NOT NULL DEFAULT 5.0,
    society_id  INTEGER REFERENCES societies(id),
    is_active   INTEGER NOT NULL DEFAULT 1,
    available_for_personal_jobs INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS categories (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    society_id INTEGER REFERENCES societies(id),
    sla_hours INTEGER NOT NULL DEFAULT 24
);

CREATE TABLE IF NOT EXISTS complaints (
    id              SERIAL PRIMARY KEY,
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
    created_at      TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    updated_at      TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    resolved_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at);
-- additive migrations for already-provisioned prod tables (idempotent)
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS official_summaries TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS society_id INTEGER REFERENCES societies(id);
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS society_id INTEGER REFERENCES societies(id);
ALTER TABLE categories ADD COLUMN IF NOT EXISTS society_id INTEGER REFERENCES societies(id);
-- E1a: enterprise escalation/assignment columns on complaints
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS assigned_staff_id INTEGER;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS escalated_to_manager_at TEXT;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS escalated_to_sr_manager_at TEXT;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS escalated_to_secretary_at TEXT;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS escalated_to_chairman_at TEXT;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS last_complainant_update_at TEXT;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS last_assigned_staff_update_at TEXT;
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS reminder_sent_count INTEGER NOT NULL DEFAULT 0;
-- E1b': vendor directory opt-out
ALTER TABLE contractors ADD COLUMN IF NOT EXISTS available_for_personal_jobs INTEGER NOT NULL DEFAULT 1;
-- E2b: staff reminder throttling
ALTER TABLE complaints ADD COLUMN IF NOT EXISTS last_reminder_sent_at TEXT;

CREATE TABLE IF NOT EXISTS complaint_messages (
    id           SERIAL PRIMARY KEY,
    complaint_id INTEGER NOT NULL REFERENCES complaints(id),
    sender       TEXT NOT NULL,
    body         TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS complaint_status_history (
    id           SERIAL PRIMARY KEY,
    complaint_id INTEGER NOT NULL REFERENCES complaints(id),
    from_status  TEXT,
    to_status    TEXT NOT NULL,
    changed_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS complaint_ratings (
    id           SERIAL PRIMARY KEY,
    complaint_id INTEGER NOT NULL UNIQUE REFERENCES complaints(id),
    rating       INTEGER NOT NULL,
    feedback     TEXT,
    created_at   TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    token_jti  TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS system_config (
    config_key   TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);
INSERT INTO system_config (config_key, config_value) VALUES
    ('max_pending_jobs_per_contractor', '10'),
    ('load_balancing_enabled', 'true')
ON CONFLICT (config_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS staff_members (
    id            SERIAL PRIMARY KEY,
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
    created_at      TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS staff_categories (
    id               SERIAL PRIMARY KEY,
    staff_id         INTEGER NOT NULL REFERENCES staff_members(id),
    category         TEXT NOT NULL,
    primary_category INTEGER NOT NULL DEFAULT 0,
    skill_level      TEXT NOT NULL DEFAULT 'junior',
    UNIQUE(staff_id, category)
);

CREATE TABLE IF NOT EXISTS contractor_categories (
    id               SERIAL PRIMARY KEY,
    contractor_id    INTEGER NOT NULL REFERENCES contractors(id),
    category         TEXT NOT NULL,
    primary_category INTEGER NOT NULL DEFAULT 0,
    average_rating   NUMERIC(3,2) NOT NULL DEFAULT 5.0,
    completed_jobs   INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    UNIQUE(contractor_id, category)
);

CREATE TABLE IF NOT EXISTS escalation_hierarchy (
    id                            SERIAL PRIMARY KEY,
    society_id                    INTEGER NOT NULL REFERENCES societies(id),
    role_name                     TEXT NOT NULL,
    person_name                   TEXT NOT NULL,
    phone                         TEXT,
    whatsapp_enabled              INTEGER NOT NULL DEFAULT 1,
    email                         TEXT,
    escalation_level              INTEGER NOT NULL,
    response_time_target_minutes  INTEGER NOT NULL DEFAULT 60,
    active                        INTEGER NOT NULL DEFAULT 1,
    created_at                    TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS category_sla_config (
    id                           SERIAL PRIMARY KEY,
    society_id                   INTEGER NOT NULL REFERENCES societies(id),
    category                     TEXT NOT NULL,
    target_response_time_minutes INTEGER NOT NULL,
    target_resolution_time_hours INTEGER NOT NULL,
    priority_high_multiplier     NUMERIC(4,2) NOT NULL DEFAULT 0.5,
    escalation_levels            TEXT NOT NULL DEFAULT '{}',
    updated_at                   TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    UNIQUE(society_id, category)
);

CREATE TABLE IF NOT EXISTS role_permission_overrides (
    society_id  INTEGER NOT NULL REFERENCES societies(id),
    role        TEXT NOT NULL,
    permission  TEXT NOT NULL,
    granted     INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    PRIMARY KEY (society_id, role, permission)
);

INSERT INTO categories (name, sla_hours) VALUES
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
    ('Noise/Visitor', 4)
ON CONFLICT (name) DO NOTHING;
