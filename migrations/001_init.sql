-- AIBuildCare Phase 1 — initial schema (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS societies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    address       TEXT,
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
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contractors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    phone         TEXT,
    specialty     TEXT,
    average_rating REAL NOT NULL DEFAULT 5.0,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
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
    estimated_completion_date TEXT,
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
INSERT OR IGNORE INTO system_config (config_key, config_value) VALUES
    ('max_pending_jobs_per_contractor', '10'),
    ('load_balancing_enabled', 'true');

INSERT OR IGNORE INTO categories (name, sla_hours) VALUES
    ('AC/Cooling', 4),
    ('Plumbing', 8),
    ('Electrical', 6),
    ('Elevator', 2),
    ('Housekeeping', 24),
    ('Security', 2),
    ('Other', 24);
