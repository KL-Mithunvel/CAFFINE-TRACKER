-- Caffeine Tracker schema (source of truth — see project/SCHEMA.md for the annotated version)
-- Applied automatically on first run if data/caffeine.db does not exist.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS drinks (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE COLLATE NOCASE,
    caffeine_per_100ml  REAL CHECK (caffeine_per_100ml >= 0),
    default_serving_ml  REAL CHECK (default_serving_ml > 0),
    is_preset           INTEGER NOT NULL DEFAULT 0,
    source              TEXT NOT NULL DEFAULT 'seed'
                        CHECK (source IN ('seed', 'internet', 'reference', 'user')),
    lookup_status       TEXT NOT NULL DEFAULT 'resolved'
                        CHECK (lookup_status IN ('resolved', 'pending', 'failed')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS entries (
    id           INTEGER PRIMARY KEY,
    drink_id     INTEGER NOT NULL REFERENCES drinks(id) ON DELETE RESTRICT,
    volume_ml    REAL NOT NULL CHECK (volume_ml > 0),
    caffeine_mg  REAL CHECK (caffeine_mg >= 0),
    consumed_at  TEXT NOT NULL,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_entries_consumed_at ON entries (consumed_at);
CREATE INDEX IF NOT EXISTS idx_entries_drink_id    ON entries (drink_id);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Seed: daily limit default (400 mg, FDA guidance for healthy adults)
INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_limit_mg', '400');

-- Seed: preset drinks (quick-entry buttons), values per REQUIREMENTS.md section 5
INSERT OR IGNORE INTO drinks (name, caffeine_per_100ml, default_serving_ml, is_preset, source, lookup_status) VALUES
    ('Brewed Coffee', 40.0,  240.0, 1, 'seed', 'resolved'),
    ('Espresso',      212.0,  30.0, 1, 'seed', 'resolved'),
    ('Black Tea',     20.0,  240.0, 1, 'seed', 'resolved'),
    ('Green Tea',     12.0,  240.0, 1, 'seed', 'resolved'),
    ('Pepsi',         10.7,  355.0, 1, 'seed', 'resolved'),
    ('Coca-Cola',      9.6,  355.0, 1, 'seed', 'resolved'),
    ('Red Bull',      32.0,  250.0, 1, 'seed', 'resolved'),
    ('Monster',       33.8,  473.0, 1, 'seed', 'resolved');
