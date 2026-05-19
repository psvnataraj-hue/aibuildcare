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
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS contractors (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    specialty   TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
);

CREATE TABLE IF NOT EXISTS categories (
    id        SERIAL PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
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
    created_at      TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    updated_at      TEXT NOT NULL DEFAULT to_char((now() at time zone 'utc'), 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
    resolved_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at);

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

INSERT INTO categories (name, sla_hours) VALUES
    ('AC/Cooling', 4),
    ('Plumbing', 8),
    ('Electrical', 6),
    ('Elevator', 2),
    ('Housekeeping', 24),
    ('Security', 2),
    ('Other', 24)
ON CONFLICT (name) DO NOTHING;
